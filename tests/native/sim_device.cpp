// Board-less stand-in for the ESP32: reads serial frames on stdin, runs the SAME core code as the firmware,
// prints the same lines the firmware prints. Time is derived from the sample count (deterministic).
#include <cstdio>

#ifdef _WIN32
#include <fcntl.h>
#include <io.h>
#endif

#include "core/alert.h"
#include "core/config.h"
#include "core/pipeline.h"
#include "core/protocol.h"

int main() {
#ifdef _WIN32
  _setmode(_fileno(stdin), _O_BINARY);
  _setmode(_fileno(stdout), _O_BINARY);
#endif
  AlertEngine engine;
  Pipeline pipeline(engine);
  FrameParser parser;
  Frame fr;
  uint64_t total = 0;
  int c;
  while ((c = fgetc(stdin)) != EOF) {
    if (!parser.feed((uint8_t)c, fr)) continue;
    do {
      if (fr.type == kFramePing) {
        printf("PONG klarify-fw %s\n", kFirmwareVersion);
        fflush(stdout);
      } else if (fr.type == kFramePcm && fr.len >= 2) {
        size_t n = (fr.len - 2) / 2;
        int16_t samples[kHop];
        if (n > (size_t)kHop) n = kHop;
        for (size_t i = 0; i < n; i++) samples[i] = (int16_t)(fr.payload[2 + 2 * i] | (fr.payload[3 + 2 * i] << 8));
        total += n;
        uint32_t now_ms = (uint32_t)(total * 1000 / kSampleRate);
        WindowResult r;
        if (pipeline.push_samples(samples, n, now_ms, r)) {
          const char* o = r.outcome == OUT_ALERT ? "alert" : (r.outcome == OUT_MUTED ? "muted" : "none");
          printf("CLS %s %s %u\n", kClassNames[r.cls], o, (unsigned)now_ms);
          fflush(stdout);
        }
      }
    } while (parser.drain(fr));
  }
  return 0;
}
