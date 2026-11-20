// Klarify ESP32 firmware: thin wrapper. All logic lives in include/core/ (tested natively on a PC).
//   USB serial (921600) <- PCM frames from the laptop feeder
//   SoftAP "Klarify-Demo" + WebServer -> portal page, /api/state, /api/mute, /api/version
//   OTA: GET /update (upload page), POST /update?key=... (application image "klarify-ota.bin")
#include <Arduino.h>
#include <Update.h>
#include <WebServer.h>
#include <WiFi.h>

#include "core/alert.h"
#include "core/config.h"
#include "core/led.h"
#include "core/pipeline.h"
#include "core/protocol.h"
#include "core/state.h"
#include "portal.h"

static constexpr int kLedPin = 2;
static constexpr const char* kSsid = "Klarify-Demo";
// Casual gate for OTA on an open demo hotspot (not strong security; traffic is plain HTTP).
static constexpr const char* kOtaKey = "klarify";

static AlertEngine engine;
static Pipeline pipeline(engine);
static StateStore state;
static FrameParser parser;
static Frame frame;
static int16_t samples[kHop];
static char json_buf[2304];
static WebServer server(80);
static Level led_level = LEVEL_NONE;
static uint32_t led_event_ms = 0;

static bool ota_authorized = false;
static bool ota_ok = false;
static String ota_error;
static uint32_t ota_reboot_at = 0;

static void handle_frame(const Frame& f) {
  if (f.type == kFramePing) {
    Serial.print("PONG klarify-fw ");
    Serial.println(kFirmwareVersion);
    return;
  }
  if (f.type != kFramePcm || f.len < 2) return;
  size_t n = (f.len - 2) / 2;
  if (n > (size_t)kHop) n = kHop;
  for (size_t i = 0; i < n; i++) samples[i] = (int16_t)(f.payload[2 + 2 * i] | (f.payload[3 + 2 * i] << 8));
  uint32_t now = millis();
  state.on_pcm(now);
  WindowResult r;
  if (pipeline.push_samples(samples, n, now, r)) {
    state.on_window(r, now);
    if (r.outcome == OUT_ALERT) {
      led_level = r.ev.level;
      led_event_ms = now;
    }
    const char* o = r.outcome == OUT_ALERT ? "alert" : (r.outcome == OUT_MUTED ? "muted" : "none");
    Serial.printf("CLS %s %s %lu\n", kClassNames[r.cls], o, (unsigned long)now);
  }
}

static void route_state() {
  size_t n = state.to_json(json_buf, sizeof(json_buf), millis());
  server.sendHeader("Cache-Control", "no-store");
  server.send(200, "application/json", n ? json_buf : "{}");
}

static void route_version() {
  server.sendHeader("Cache-Control", "no-store");
  server.send(200, "application/json", String("{\"version\":\"") + kFirmwareVersion + "\"}");
}

static void route_mute() {
  String sound = server.arg("sound");
  bool on = server.arg("on") == "1";
  for (int c = 1; c < kNumClasses; c++) {
    if (sound == kClassNames[c]) {
      engine.set_muted(c, on);
      state.set_muted(c, on);
      server.send(200, "application/json", "{\"ok\":true}");
      return;
    }
  }
  server.send(400, "application/json", "{\"ok\":false}");
}

// ---- OTA -------------------------------------------------------------------------------------
static String json_safe(String s) {
  s.replace("\"", "'");
  s.replace("\\", "/");
  return s;
}

// Called for each chunk of the uploaded file. The password arrives in the URL (?key=...), which the
// WebServer parses before the file body, so it is known at UPLOAD_FILE_START.
static void ota_upload() {
  HTTPUpload& up = server.upload();
  if (up.status == UPLOAD_FILE_START) {
    ota_ok = false;
    ota_error = "";
    ota_authorized = server.arg("key") == kOtaKey;
    if (!ota_authorized) {
      ota_error = "Wrong password";
      return;
    }
    if (!Update.begin(UPDATE_SIZE_UNKNOWN)) ota_error = Update.errorString();
  } else if (up.status == UPLOAD_FILE_WRITE) {
    if (ota_authorized && ota_error.isEmpty()) {
      if (Update.write(up.buf, up.currentSize) != up.currentSize) {
        ota_error = Update.errorString();  // the Update library rejects a non-app image here (magic byte)
        Update.abort();
      }
    }
  } else if (up.status == UPLOAD_FILE_END) {
    if (ota_authorized && ota_error.isEmpty()) {
      if (Update.end(true)) ota_ok = true;
      else ota_error = Update.errorString();
    }
  } else if (up.status == UPLOAD_FILE_ABORTED) {
    if (ota_authorized) Update.abort();
    ota_error = "Upload interrupted";
  }
}

// Called once the whole request has been received.
static void ota_done() {
  server.sendHeader("Connection", "close");
  if (ota_ok) {
    server.send(200, "application/json", "{\"ok\":true}");
    ota_reboot_at = millis() + 1000;  // let the response reach the phone before restarting
    if (ota_reboot_at == 0) ota_reboot_at = 1;
  } else {
    String err = ota_error.isEmpty() ? String("No file received") : ota_error;
    server.send(ota_authorized || !ota_error.length() ? 500 : 403, "application/json",
                String("{\"ok\":false,\"error\":\"") + json_safe(err) + "\"}");
  }
  ota_authorized = false;
  ota_ok = false;
}

void setup() {
  pinMode(kLedPin, OUTPUT);
  digitalWrite(kLedPin, LOW);
  Serial.setRxBufferSize(8192);
  Serial.begin(921600);
  WiFi.mode(WIFI_AP);
  WiFi.softAP(kSsid, nullptr, 6, 0, 4);
  server.on("/", HTTP_GET, []() { server.send_P(200, "text/html; charset=utf-8", PORTAL_HTML); });
  server.on("/update", HTTP_GET, []() { server.send_P(200, "text/html; charset=utf-8", UPDATE_HTML); });
  server.on("/update", HTTP_POST, ota_done, ota_upload);
  server.on("/api/state", HTTP_GET, route_state);
  server.on("/api/version", HTTP_GET, route_version);
  server.on("/api/mute", HTTP_POST, route_mute);
  server.begin();
}

void loop() {
  int budget = 2048;  // bytes per pass so the web server keeps getting CPU time
  while (budget-- > 0 && Serial.available()) {
    if (parser.feed((uint8_t)Serial.read(), frame)) {
      do { handle_frame(frame); } while (parser.drain(frame));
    }
  }
  server.handleClient();
  digitalWrite(kLedPin, led_state(led_level, millis() - led_event_ms) ? HIGH : LOW);
  if (ota_reboot_at && (int32_t)(millis() - ota_reboot_at) >= 0) ESP.restart();
}
