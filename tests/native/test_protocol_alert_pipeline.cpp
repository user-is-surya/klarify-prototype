// Native tests for protocol.h, alert.h, pipeline.h. Usage: test_protocol_alert_pipeline <stream.bin>
#include <cstdio>
#include <cstring>
#include <vector>

#include "core/alert.h"
#include "core/config.h"
#include "core/pipeline.h"
#include "core/protocol.h"

static int g_fail = 0;
#define CHECK(cond, name)                                      \
  do {                                                         \
    if (!(cond)) { printf("FAIL %s (line %d)\n", name, __LINE__); g_fail++; } \
    else printf("ok   %s\n", name);                            \
  } while (0)

enum { BG = 0, WHISTLE = 1, DOORBELL = 2, CRY = 3, ALARM = 4, MICRO = 5 };

static void parser_resyncs_after_garbage(const char* path) {
  FILE* f = fopen(path, "rb");
  std::vector<uint8_t> bytes;
  if (f) { int c; while ((c = fgetc(f)) != EOF) bytes.push_back((uint8_t)c); fclose(f); }
  FrameParser p;
  Frame fr;
  std::vector<Frame> got;
  for (uint8_t b : bytes) {
    if (p.feed(b, fr)) {
      do { got.push_back(fr); } while (p.drain(fr));
    }
  }
  bool ok = got.size() == 3 && got[0].type == 0x02 && got[0].len == 0 && got[1].type == 0x01 &&
            got[1].len == 802 && got[2].type == 0x01 && got[2].len == 802;
  if (ok) {
    uint16_t s1 = got[1].payload[0] | (got[1].payload[1] << 8);
    uint16_t s2 = got[2].payload[0] | (got[2].payload[1] << 8);
    ok = s1 == 7 && s2 == 8;
  }
  printf("   (parsed %zu frames from %zu bytes)\n", got.size(), bytes.size());
  CHECK(ok, "parser_resyncs_after_garbage");
}

static void alert_tests() {
  AlertEvent ev;
  {
    AlertEngine e;
    CHECK(e.update(WHISTLE, 0, ev) == OUT_NONE, "two_in_a_row_required: first window no alert");
    Outcome o = e.update(WHISTLE, 500, ev);
    CHECK(o == OUT_ALERT && ev.cls == WHISTLE && ev.level == LEVEL_URGENT && ev.ms == 500,
          "two_in_a_row_required: second window alerts");
  }
  {
    AlertEngine e;
    e.update(WHISTLE, 0, ev);
    e.update(BG, 500, ev);
    CHECK(e.update(WHISTLE, 1000, ev) == OUT_NONE, "two_in_a_row_required: interrupted streak does not alert");
  }
  {
    AlertEngine e;
    bool any = false;
    for (int i = 0; i < 20; i++) any |= (e.update(BG, i * 500, ev) != OUT_NONE);
    CHECK(!any, "background_never_alerts");
  }
  {
    AlertEngine e;
    e.update(ALARM, 0, ev);
    CHECK(e.update(ALARM, 500, ev) == OUT_ALERT, "refire: first alert");
    bool early = false;
    for (int t = 1000; t < 4500; t += 500) early |= (e.update(ALARM, t, ev) != OUT_NONE);
    CHECK(!early, "refire_same_label_only_after_4s: nothing before 4 s");
    CHECK(e.update(ALARM, 4500, ev) == OUT_ALERT, "refire_same_label_only_after_4s: fires at >= 4 s");
  }
  {
    AlertEngine e;
    e.update(WHISTLE, 0, ev);
    e.update(WHISTLE, 500, ev);
    e.update(CRY, 1000, ev);
    CHECK(e.update(CRY, 1500, ev) == OUT_ALERT && ev.cls == CRY,
          "label_change_fires_immediately_after_confirmation");
  }
  {
    AlertEngine e;
    e.set_muted(DOORBELL, true);
    e.update(DOORBELL, 0, ev);
    Outcome o = e.update(DOORBELL, 500, ev);
    CHECK(o == OUT_MUTED && ev.cls == DOORBELL, "muted_returns_muted_not_alert");
    CHECK(e.is_muted(DOORBELL) && !e.is_muted(WHISTLE), "is_muted reflects set_muted");
    e.set_muted(DOORBELL, false);
    CHECK(!e.is_muted(DOORBELL), "set_muted false unmutes");
  }
}

static void pipeline_tests() {
  static int16_t silence[kHop];
  memset(silence, 0, sizeof(silence));
  AlertEngine e;
  Pipeline p(e);
  WindowResult r;
  uint32_t now = 0;
  bool early = p.push_samples(silence, 4000, now += 500, r);
  early |= p.push_samples(silence, 3999, now += 500, r);
  CHECK(!early, "pipeline_first_window_after_8000_samples: not before 8000");
  bool first = p.push_samples(silence, 1, now += 1, r);
  CHECK(first && r.cls == 0 && r.outcome == OUT_NONE, "pipeline_first_window_after_8000_samples: at 8000, silence -> background");
  bool mid = p.push_samples(silence, 3999, now += 500, r);
  CHECK(!mid, "pipeline_hop_is_4000_samples: not at 3999");
  bool hop = p.push_samples(silence, 1, now += 1, r);
  CHECK(hop, "pipeline_hop_is_4000_samples: at 4000");
}

static void reset_and_gap_tests() {
  AlertEvent ev;
  {
    AlertEngine e;
    e.update(WHISTLE, 0, ev);
    e.reset();
    CHECK(e.update(WHISTLE, 500, ev) == OUT_NONE, "alert_reset_clears_streak");
  }
  {
    AlertEngine e;
    e.set_muted(DOORBELL, true);
    e.reset();
    CHECK(e.is_muted(DOORBELL), "alert_reset_keeps_mutes");
  }
  static int16_t silence[kHop];
  memset(silence, 0, sizeof(silence));
  {
    AlertEngine e;
    Pipeline p(e);
    WindowResult r;
    uint32_t now = 0;
    p.push_samples(silence, 4000, now += 500, r);
    bool first = p.push_samples(silence, 4000, now += 500, r);
    CHECK(first, "gap setup: first window completes");
    now += 1500;  // input stopped for 1.5 s (feeder quit / restarted)
    bool after_gap = p.push_samples(silence, 4000, now, r);
    CHECK(!after_gap, "pipeline_gap_discards_stale_audio: needs a fresh full window after a gap");
    bool fresh = p.push_samples(silence, 4000, now += 500, r);
    CHECK(fresh, "pipeline_gap: next window after 8000 fresh samples");
  }
  {
    AlertEngine e;
    Pipeline p(e);
    WindowResult r;
    p.push_samples(silence, 400, 1000, r);
    e.update(WHISTLE, 1000, ev);  // streak 1
    p.push_samples(silence, 400, 2500, r);  // 1.5 s gap
    CHECK(e.update(WHISTLE, 2500, ev) == OUT_NONE, "pipeline_gap_resets_alert_streak");
  }
  {
    AlertEngine e;
    Pipeline p(e);
    WindowResult r;
    p.push_samples(silence, 400, 1000, r);
    e.update(WHISTLE, 1000, ev);
    p.push_samples(silence, 400, 1050, r);  // normal 50 ms cadence: no reset
    CHECK(e.update(WHISTLE, 1500, ev) == OUT_ALERT, "continuous_input_does_not_reset_streak");
  }
}

int main(int argc, char** argv) {
  if (argc >= 2) parser_resyncs_after_garbage(argv[1]);
  else { printf("FAIL missing stream.bin arg\n"); g_fail++; }
  alert_tests();
  pipeline_tests();
  reset_and_gap_tests();
  printf(g_fail ? "FAILED: %d\n" : "ALL PASSED\n", g_fail);
  return g_fail ? 1 : 0;
}
