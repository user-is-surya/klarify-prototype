// Alert engine: two consecutive windows with the same non-background label confirm an alert.
#pragma once
#include <stdint.h>

#include "config.h"

enum Outcome { OUT_NONE = 0, OUT_ALERT = 1, OUT_MUTED = 2 };

struct AlertEvent {
  int cls;
  Level level;
  uint32_t ms;
};

class AlertEngine {
 public:
  static constexpr uint32_t kRefireMs = 4000;

  // Call once per classified window. On OUT_ALERT / OUT_MUTED, `ev` is filled in.
  Outcome update(int cls, uint32_t now_ms, AlertEvent& ev) {
    if (cls <= 0 || cls >= kNumClasses) {
      prev_ = 0;
      streak_ = 0;
      return OUT_NONE;
    }
    streak_ = (cls == prev_) ? streak_ + 1 : 1;
    prev_ = cls;
    if (streak_ < 2) return OUT_NONE;
    bool fresh = (cls != last_event_cls_) || (now_ms - last_event_ms_ >= kRefireMs);
    if (!fresh) return OUT_NONE;
    last_event_cls_ = cls;
    last_event_ms_ = now_ms;
    ev.cls = cls;
    ev.level = kClassLevel[cls];
    ev.ms = now_ms;
    return muted_[cls] ? OUT_MUTED : OUT_ALERT;
  }

  // Forget the running streak and last alert (mutes are kept). Called when the audio input stops.
  void reset() {
    prev_ = 0;
    streak_ = 0;
    last_event_cls_ = -1;
    last_event_ms_ = 0;
  }

  void set_muted(int cls, bool m) {
    if (cls > 0 && cls < kNumClasses) muted_[cls] = m;
  }
  bool is_muted(int cls) const { return cls > 0 && cls < kNumClasses && muted_[cls]; }

 private:
  int prev_ = 0;
  int streak_ = 0;
  int last_event_cls_ = -1;
  uint32_t last_event_ms_ = 0;
  bool muted_[kNumClasses] = {false};
};
