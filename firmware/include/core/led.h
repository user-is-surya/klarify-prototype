// Onboard LED blink patterns per alert level (pure function of time since the alert).
#pragma once
#include <stdint.h>

#include "config.h"

inline bool led_state(Level level, uint32_t ms_since_event) {
  switch (level) {
    case LEVEL_URGENT:  // fast continuous blink for 5 s
      return ms_since_event < 5000 && (ms_since_event % 200) < 100;
    case LEVEL_IMPORTANT:  // two 200 ms blinks
      return ms_since_event < 200 || (ms_since_event >= 400 && ms_since_event < 600);
    case LEVEL_INFO:  // one 300 ms blink
      return ms_since_event < 300;
    default:
      return false;
  }
}
