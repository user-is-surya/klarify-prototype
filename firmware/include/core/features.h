// C++ twin of tools/features.py. Keep the two in lock-step (see plan, Task 2 definition).
#pragma once
#include <math.h>
#include <stdint.h>

#include "config.h"
#include "fft.h"

constexpr float kBinHz = (float)kSampleRate / (float)kFrame;  // 15.625

// window: kWindow int16 samples -> out: kNumFeatures floats.
inline void extract_features(const int16_t* window, float* out) {
  for (int i = 0; i < kNumFeatures; i++) out[i] = 0.0f;
  out[2] = 1.0f;  // flatness default (silence)

  const FftTables& t = fft_tables();
  float rms[kNumFrames];
  float max_rms = 0.0f;
  for (int i = 0; i < kNumFrames; i++) {
    const int16_t* s = window + i * kFrameStep;
    float acc = 0.0f;
    for (int n = 0; n < kFrame; n++) {
      float x = (float)s[n] / 32768.0f;
      acc += x * x;
    }
    rms[i] = sqrtf(acc / (float)kFrame);
    if (rms[i] > max_rms) max_rms = rms[i];
  }
  if (max_rms < 1e-4f) return;

  static float re[kFrame], im[kFrame], mag[kNumBins + 1];  // static: keep the ESP32 loop-task stack small
  bool active[kNumFrames];
  float peaks[kNumFrames];
  int n_active = 0, pulses = 0;
  float sum_cent = 0, sum_flat = 0, sum_bw = 0, sum_pr = 0, sum_h = 0;

  for (int i = 0; i < kNumFrames; i++) active[i] = rms[i] >= 0.5f * max_rms;

  for (int i = 0; i < kNumFrames; i++) {
    if (!active[i]) continue;
    if (i == 0 || !active[i - 1]) pulses++;
    const int16_t* s = window + i * kFrameStep;
    for (int n = 0; n < kFrame; n++) {
      re[n] = ((float)s[n] / 32768.0f) * t.hann[n];
      im[n] = 0.0f;
    }
    fft512(re, im);
    float tot = 1e-12f, wsum = 0.0f, lsum = 0.0f, msum = 0.0f, best = -1.0f;
    int p = 1;
    for (int k = 1; k <= kNumBins; k++) {
      float m = sqrtf(re[k] * re[k] + im[k] * im[k]);
      mag[k] = m;
      tot += m;
      wsum += (float)k * m;
      lsum += logf(m + 1e-9f);
      msum += m;
      if (m > best) { best = m; p = k; }
    }
    float c = wsum / tot;
    float var = 0.0f;
    for (int k = 1; k <= kNumBins; k++) var += ((float)k - c) * ((float)k - c) * mag[k];
    sum_cent += c;
    sum_flat += expf(lsum / (float)kNumBins) / (msum / (float)kNumBins + 1e-9f);
    sum_bw += sqrtf(var / tot);
    sum_pr += mag[p] / tot;
    int lo = 2 * p - 1 < kNumBins ? 2 * p - 1 : kNumBins;
    int hi = 2 * p + 1 < kNumBins ? 2 * p + 1 : kNumBins;
    float hm = 0.0f;
    for (int k = lo; k <= hi; k++) if (mag[k] > hm) hm = mag[k];
    sum_h += hm / (mag[p] + 1e-9f);
    peaks[n_active++] = (float)p;
  }

  // lower median of peak bins (insertion sort on a copy)
  float sorted[kNumFrames];
  for (int i = 0; i < n_active; i++) {
    float v = peaks[i];
    int j = i - 1;
    while (j >= 0 && sorted[j] > v) { sorted[j + 1] = sorted[j]; j--; }
    sorted[j + 1] = v;
  }
  float mean_pk = 0.0f;
  for (int i = 0; i < n_active; i++) mean_pk += peaks[i] * kBinHz;
  mean_pk /= (float)n_active;
  float var_pk = 0.0f;
  for (int i = 0; i < n_active; i++) {
    float d = peaks[i] * kBinHz - mean_pk;
    var_pk += d * d;
  }

  float mean_rms = 0.0f;
  for (int i = 0; i < kNumFrames; i++) mean_rms += rms[i];
  mean_rms /= (float)kNumFrames;
  float var_rms = 0.0f;
  for (int i = 0; i < kNumFrames; i++) var_rms += (rms[i] - mean_rms) * (rms[i] - mean_rms);

  float na = (float)n_active;
  out[0] = sorted[(n_active - 1) / 2] * kBinHz;
  out[1] = (sum_cent / na) * kBinHz;
  out[2] = sum_flat / na;
  out[3] = (sum_bw / na) * kBinHz;
  out[4] = na / (float)kNumFrames;
  out[5] = (float)pulses;
  out[6] = sqrtf(var_pk / na);
  out[7] = sum_pr / na;
  out[8] = sqrtf(var_rms / (float)kNumFrames) / (mean_rms + 1e-9f);
  out[9] = sum_h / na;
}
