// Sliding 1 s window over the incoming PCM stream, classified every 0.5 s.
#pragma once
#include <stddef.h>
#include <stdint.h>

#include "alert.h"
#include "classifier.h"
#include "config.h"
#include "features.h"

struct WindowResult {
  int cls;
  float features[kNumFeatures];
  Outcome outcome;
  AlertEvent ev;
};

class Pipeline {
 public:
  explicit Pipeline(AlertEngine& engine) : engine_(engine) {}

  // Push samples (any n). True if at least one window completed; `r` holds the latest one.
  // now_ms is the time at the end of the pushed samples.
  bool push_samples(const int16_t* s, size_t n, uint32_t now_ms, WindowResult& r) {
    bool done = false;
    for (size_t i = 0; i < n; i++) {
      ring_[pos_] = s[i];
      pos_ = (pos_ + 1) % kWindow;
      if (filled_ < kWindow) filled_++;
      since_++;
      if (filled_ >= kWindow && since_ >= (size_t)kHop) {
        since_ = 0;
        for (int k = 0; k < kWindow; k++) scratch_[k] = ring_[(pos_ + k) % kWindow];
        extract_features(scratch_, r.features);
        r.cls = classify(r.features);
        r.outcome = engine_.update(r.cls, now_ms, r.ev);
        done = true;
      }
    }
    return done;
  }

 private:
  AlertEngine& engine_;
  int16_t ring_[kWindow] = {0};
  int16_t scratch_[kWindow] = {0};
  int pos_ = 0;
  int filled_ = 0;
  size_t since_ = 0;
};
