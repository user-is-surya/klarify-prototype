// Native tests for state.h and led.h.
#include <cstdio>
#include <cstring>
#include <string>

#include "core/led.h"
#include "core/state.h"

static int g_fail = 0;
#define CHECK(cond, name)                                      \
  do {                                                         \
    if (!(cond)) { printf("FAIL %s (line %d)\n", name, __LINE__); g_fail++; } \
    else printf("ok   %s\n", name);                            \
  } while (0)

static WindowResult alert(int cls, uint32_t ms) {
  WindowResult r;
  memset(&r, 0, sizeof(r));
  r.cls = cls;
  r.outcome = OUT_ALERT;
  r.ev = {cls, kClassLevel[cls], ms};
  return r;
}
static WindowResult muted(int cls, uint32_t ms) {
  WindowResult r = alert(cls, ms);
  r.outcome = OUT_MUTED;
  return r;
}
static bool has(const std::string& s, const char* needle) { return s.find(needle) != std::string::npos; }

int main() {
  char buf[4096];
  {
    StateStore s;
    s.on_pcm(1000);
    s.to_json(buf, sizeof(buf), 3999);
    CHECK(has(buf, "\"connected\":true"), "connected_true_within_3s");
    s.to_json(buf, sizeof(buf), 4000);
    CHECK(has(buf, "\"connected\":false"), "connected_false_after_3s_without_pcm");
    StateStore fresh;
    fresh.to_json(buf, sizeof(buf), 100);
    CHECK(has(buf, "\"connected\":false") && has(buf, "\"current\":null") && has(buf, "\"seq\":0"),
          "fresh_store_idle");
  }
  {
    StateStore s;
    s.on_pcm(0);
    s.on_window(alert(1, 1000), 1000);
    s.to_json(buf, sizeof(buf), 6999);
    CHECK(has(buf, "\"sound\":\"cooker_whistle\"") && has(buf, "\"level\":\"urgent\"") &&
              has(buf, "\"label\":\"Cooker whistle\"") && has(buf, "\"age_ms\":5999") && has(buf, "\"seq\":1"),
          "current_present_before_6s");
    s.to_json(buf, sizeof(buf), 7000);
    CHECK(has(buf, "\"current\":null"), "current_expires_after_6s");
  }
  {
    StateStore s;
    for (int i = 0; i < 25; i++) s.on_window(alert(1 + (i % 5), 1000 + i), 1000 + i);
    s.to_json(buf, sizeof(buf), 2000);
    std::string j = buf;
    size_t count = 0, pos = 0;
    while ((pos = j.find("\"t_ms\":", pos)) != std::string::npos) { count++; pos++; }
    CHECK(count == 20, "history_capped_at_20");
    CHECK(j.find("\"t_ms\":1024") < j.find("\"t_ms\":1005"), "history_newest_first");
  }
  {
    StateStore s;
    s.on_window(alert(2, 1000), 1000);
    s.on_window(muted(2, 2000), 2000);
    s.to_json(buf, sizeof(buf), 3000);
    CHECK(has(buf, "\"seq\":1") && has(buf, "\"muted\":true"),
          "muted_hit_recorded_with_muted_true_and_no_seq_increment");
  }
  {
    StateStore s;
    s.set_muted(2, true);
    s.set_muted(3, true);
    s.to_json(buf, sizeof(buf), 100);
    CHECK(has(buf, "\"muted\":[\"doorbell\",\"baby_cry\"]"), "muted_list_in_json");
    s.set_muted(2, false);
    s.to_json(buf, sizeof(buf), 100);
    CHECK(has(buf, "\"muted\":[\"baby_cry\"]"), "unmute_removes_from_list");
  }
  {
    StateStore s;
    s.on_pcm(4000000000u);
    for (int i = 0; i < 30; i++) s.on_window(alert(5, 4000000000u + i), 4000000000u + i);
    for (int i = 1; i < 6; i++) s.set_muted(i, true);
    size_t n = s.to_json(buf, 2048, 4000000100u);
    CHECK(n > 0 && n < 2048 && buf[n - 1] == '}', "json_fits_in_2048_bytes_when_history_full");
  }
  CHECK(led_state(LEVEL_URGENT, 50) && !led_state(LEVEL_URGENT, 150) && led_state(LEVEL_URGENT, 250) &&
            led_state(LEVEL_URGENT, 4850) && !led_state(LEVEL_URGENT, 5000) && !led_state(LEVEL_URGENT, 5050),
        "led_urgent_blinks_continuously_then_stops_after_5s");
  CHECK(led_state(LEVEL_IMPORTANT, 100) && !led_state(LEVEL_IMPORTANT, 300) && led_state(LEVEL_IMPORTANT, 500) &&
            !led_state(LEVEL_IMPORTANT, 700),
        "led_important_two_blinks");
  CHECK(led_state(LEVEL_INFO, 100) && !led_state(LEVEL_INFO, 350) && !led_state(LEVEL_NONE, 100),
        "led_info_one_blink");
  printf(g_fail ? "FAILED: %d\n" : "ALL PASSED\n", g_fail);
  return g_fail ? 1 : 0;
}
