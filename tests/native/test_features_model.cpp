// Parity test: C++ features + classifier vs Python reference. Usage: test_features_model <fixture_dir>
#include <cmath>
#include <cstdio>
#include <string>
#include <vector>

#include "core/classifier.h"
#include "core/config.h"
#include "core/features.h"

template <typename T>
static std::vector<T> read_all(const std::string& path) {
  std::vector<T> v;
  FILE* f = fopen(path.c_str(), "rb");
  if (!f) { fprintf(stderr, "cannot open %s\n", path.c_str()); return v; }
  T buf[4096];
  size_t n;
  while ((n = fread(buf, sizeof(T), 4096, f)) > 0) v.insert(v.end(), buf, buf + n);
  fclose(f);
  return v;
}

int main(int argc, char** argv) {
  if (argc < 2) return 2;
  std::string dir = argv[1];
  auto clips = read_all<int16_t>(dir + "/clips.bin");
  auto feats = read_all<float>(dir + "/features.bin");
  auto pred = read_all<int32_t>(dir + "/pred.bin");
  size_t n = pred.size();
  if (n < 3 || clips.size() != n * kWindow || feats.size() != n * kNumFeatures) {
    fprintf(stderr, "fixture size mismatch\n");
    return 2;
  }
  int fails = 0;
  size_t pairs = 0, ok_pairs = 0, ok_cls = 0;
  for (size_t i = 0; i < n; i++) {
    float f[kNumFeatures];
    extract_features(&clips[i * kWindow], f);
    bool finite = true;
    for (int k = 0; k < kNumFeatures; k++) {
      if (!std::isfinite(f[k])) finite = false;
      float e = feats[i * kNumFeatures + k];
      float tol = std::fmax(1e-3f, 0.02f * std::fabs(e));
      pairs++;
      if (std::fabs(f[k] - e) <= tol) ok_pairs++;
    }
    if (!finite) { fprintf(stderr, "clip %zu: non-finite features\n", i); fails++; }
    int c = classify(f);
    if (c < 0 || c >= kNumClasses) { fprintf(stderr, "clip %zu: bad class %d\n", i, c); fails++; }
    if (c == pred[i]) ok_cls++;
    if (i == n - 2 && c != 0) { fprintf(stderr, "silent clip -> class %d, expected background\n", c); fails++; }
  }
  double pair_rate = (double)ok_pairs / (double)pairs;
  double cls_rate = (double)ok_cls / (double)n;
  printf("feature pairs within tol: %.3f, class agreement: %.3f\n", pair_rate, cls_rate);
  if (pair_rate < 0.95) { fprintf(stderr, "feature parity below 95%%\n"); fails++; }
  if (cls_rate < 0.98) { fprintf(stderr, "class agreement below 98%%\n"); fails++; }
  return fails == 0 ? 0 : 1;
}
