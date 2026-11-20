// State shared with the portal: recent alerts, connection status, mutes. Serialised as JSON.
#pragma once
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>

#include "alert.h"
#include "config.h"
#include "pipeline.h"

class StateStore {
 public:
  static constexpr int kHistory = 20;
  static constexpr uint32_t kConnectedMs = 3000;
  static constexpr uint32_t kCurrentMs = 6000;

  void on_pcm(uint32_t now_ms) {
    last_pcm_ms_ = now_ms;
    has_pcm_ = true;
  }

  void on_window(const WindowResult& r, uint32_t /*now_ms*/) {
    if (r.outcome == OUT_NONE) return;
    bool is_muted = r.outcome == OUT_MUTED;
    if (!is_muted) {
      seq_++;
      cur_ = r.ev;
      has_cur_ = true;
    }
    Entry& e = hist_[head_];
    e.t_ms = r.ev.ms;
    e.cls = r.ev.cls;
    e.level = r.ev.level;
    e.muted = is_muted;
    head_ = (head_ + 1) % kHistory;
    if (count_ < kHistory) count_++;
  }

  void set_muted(int cls, bool m) {
    if (cls > 0 && cls < kNumClasses) muted_[cls] = m;
  }

  // Returns bytes written (excluding NUL), or 0 if the buffer was too small.
  size_t to_json(char* buf, size_t cap, uint32_t now_ms) const {
    Out o{buf, cap, 0, true};
    bool connected = has_pcm_ && (now_ms - last_pcm_ms_) < kConnectedMs;
    o.add("{\"input\":\"synthetic\",\"connected\":%s,\"uptime_ms\":%lu,\"seq\":%lu,\"current\":",
          connected ? "true" : "false", (unsigned long)now_ms, (unsigned long)seq_);
    if (has_cur_ && (now_ms - cur_.ms) < kCurrentMs) {
      o.add("{\"sound\":\"%s\",\"label\":\"%s\",\"level\":\"%s\",\"age_ms\":%lu}", kClassNames[cur_.cls],
            kClassLabels[cur_.cls], level_name(cur_.level), (unsigned long)(now_ms - cur_.ms));
    } else {
      o.add("null");
    }
    o.add(",\"history\":[");
    for (int i = 0; i < count_; i++) {
      const Entry& e = hist_[(head_ - 1 - i + 2 * kHistory) % kHistory];  // newest first
      o.add("%s{\"t_ms\":%lu,\"sound\":\"%s\",\"level\":\"%s\",\"muted\":%s}", i ? "," : "",
            (unsigned long)e.t_ms, kClassNames[e.cls], level_name(e.level), e.muted ? "true" : "false");
    }
    o.add("],\"muted\":[");
    bool first = true;
    for (int c = 1; c < kNumClasses; c++) {
      if (!muted_[c]) continue;
      o.add("%s\"%s\"", first ? "" : ",", kClassNames[c]);
      first = false;
    }
    o.add("]}");
    return o.ok ? o.n : 0;
  }

 private:
  struct Entry {
    uint32_t t_ms;
    int cls;
    Level level;
    bool muted;
  };
  struct Out {
    char* p;
    size_t cap, n;
    bool ok;
    void add(const char* fmt, ...) {
      if (!ok) return;
      va_list ap;
      va_start(ap, fmt);
      int w = vsnprintf(p + n, cap - n, fmt, ap);
      va_end(ap);
      if (w < 0 || (size_t)w >= cap - n) ok = false;
      else n += (size_t)w;
    }
  };
  Entry hist_[kHistory] = {};
  int head_ = 0, count_ = 0;
  uint32_t seq_ = 0, last_pcm_ms_ = 0;
  bool has_pcm_ = false, has_cur_ = false;
  AlertEvent cur_ = {0, LEVEL_NONE, 0};
  bool muted_[kNumClasses] = {false};
};
