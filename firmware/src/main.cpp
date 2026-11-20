// Klarify ESP32 firmware: thin wrapper. All logic lives in include/core/ (tested natively on a PC).
//   USB serial (921600) <- PCM frames from the laptop feeder
//   SoftAP "Klarify-Demo" + WebServer -> portal page, /api/state, /api/mute
#include <Arduino.h>
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
static constexpr const char* kVersion = "klarify-fw 1.0";

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

static void handle_frame(const Frame& f) {
  if (f.type == kFramePing) {
    Serial.print("PONG ");
    Serial.println(kVersion);
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

void setup() {
  pinMode(kLedPin, OUTPUT);
  digitalWrite(kLedPin, LOW);
  Serial.setRxBufferSize(8192);
  Serial.begin(921600);
  WiFi.mode(WIFI_AP);
  WiFi.softAP(kSsid, nullptr, 6, 0, 4);
  server.on("/", HTTP_GET, []() { server.send_P(200, "text/html; charset=utf-8", PORTAL_HTML); });
  server.on("/api/state", HTTP_GET, route_state);
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
}
