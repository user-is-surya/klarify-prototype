// Shared constants for the Klarify core (portable C++, no Arduino includes).
#pragma once
#include <stddef.h>
#include <stdint.h>

constexpr int kSampleRate = 8000;
constexpr int kWindow = 8000;     // 1 s
constexpr int kHop = 4000;        // 0.5 s
constexpr int kFrame = 512;
constexpr int kFrameStep = 256;
constexpr int kNumFrames = (kWindow - kFrame) / kFrameStep + 1;  // 30
constexpr int kNumBins = 255;     // bins k = 1..255
constexpr int kNumFeatures = 10;
constexpr int kNumClasses = 6;
constexpr int kBlockSamples = 400;  // 50 ms per serial block

enum Level { LEVEL_NONE = 0, LEVEL_INFO = 1, LEVEL_IMPORTANT = 2, LEVEL_URGENT = 3 };

// Class order is identical to tools/sounds.py SOUNDS.
inline const char* const kClassNames[kNumClasses] = {
    "background", "cooker_whistle", "doorbell", "baby_cry", "smoke_alarm", "microwave_beep"};
inline const char* const kClassLabels[kNumClasses] = {
    "Background", "Cooker whistle", "Doorbell", "Baby crying", "Smoke alarm", "Microwave beep"};
inline const Level kClassLevel[kNumClasses] = {
    LEVEL_NONE, LEVEL_URGENT, LEVEL_INFO, LEVEL_IMPORTANT, LEVEL_URGENT, LEVEL_INFO};

inline const char* level_name(Level l) {
  switch (l) {
    case LEVEL_URGENT: return "urgent";
    case LEVEL_IMPORTANT: return "important";
    case LEVEL_INFO: return "info";
    default: return "none";
  }
}
