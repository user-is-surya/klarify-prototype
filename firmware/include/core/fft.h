// Tiny radix-2 FFT (512 points) and Hann window, no external libraries.
#pragma once
#include <math.h>
#include <stdint.h>

#include "config.h"

struct FftTables {
  float cos_t[kFrame / 2];
  float sin_t[kFrame / 2];
  float hann[kFrame];
  uint16_t rev[kFrame];
  FftTables() {
    const double two_pi = 6.283185307179586;
    for (int i = 0; i < kFrame / 2; i++) {
      cos_t[i] = (float)cos(two_pi * i / kFrame);
      sin_t[i] = (float)sin(two_pi * i / kFrame);
    }
    for (int n = 0; n < kFrame; n++) hann[n] = (float)(0.5 * (1.0 - cos(two_pi * n / kFrame)));
    int bits = 0;
    while ((1 << bits) < kFrame) bits++;
    for (int i = 0; i < kFrame; i++) {
      int r = 0;
      for (int b = 0; b < bits; b++)
        if (i & (1 << b)) r |= 1 << (bits - 1 - b);
      rev[i] = (uint16_t)r;
    }
  }
};

inline const FftTables& fft_tables() {
  static const FftTables t;
  return t;
}

// In-place forward FFT of kFrame complex points.
inline void fft512(float* re, float* im) {
  const FftTables& t = fft_tables();
  for (int i = 0; i < kFrame; i++) {
    int j = t.rev[i];
    if (j > i) {
      float a = re[i]; re[i] = re[j]; re[j] = a;
      a = im[i]; im[i] = im[j]; im[j] = a;
    }
  }
  for (int len = 2; len <= kFrame; len <<= 1) {
    int half = len >> 1, step = kFrame / len;
    for (int i = 0; i < kFrame; i += len) {
      for (int k = 0; k < half; k++) {
        float wr = t.cos_t[k * step], wi = -t.sin_t[k * step];
        int a = i + k, b = a + half;
        float xr = re[b] * wr - im[b] * wi;
        float xi = re[b] * wi + im[b] * wr;
        re[b] = re[a] - xr; im[b] = im[a] - xi;
        re[a] += xr; im[a] += xi;
      }
    }
  }
}
