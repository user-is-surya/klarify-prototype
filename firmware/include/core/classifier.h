// Wraps the generated decision tree (model.h). Silence is handled here: the tree never saw it in training.
#pragma once
#include "config.h"
#include "model.h"

// features: kNumFeatures floats -> class index (0..kNumClasses-1), 0 = background.
inline int classify(const float* features) {
  if (features[4] == 0.0f) return 0;  // duty == 0 only happens for silence
  int c = model_predict(features);
  return (c >= 0 && c < kNumClasses) ? c : 0;
}
