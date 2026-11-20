// Serial frame parser. Frame: 'K' 'L' type len_lo len_hi payload checksum (XOR of type,len,payload).
// Resyncs on garbage, truncated frames and bad checksums by re-scanning buffered bytes.
#pragma once
#include <stdint.h>
#include <string.h>

constexpr uint8_t kMagic0 = 0x4B;
constexpr uint8_t kMagic1 = 0x4C;
constexpr uint8_t kFramePcm = 0x01;
constexpr uint8_t kFramePing = 0x02;
constexpr int kMaxPayload = 820;

struct Frame {
  uint8_t type;
  uint16_t len;
  uint8_t payload[kMaxPayload];
};

class FrameParser {
 public:
  // Push one byte. True when a complete valid frame is in `out`.
  // After a true result call drain() until it returns false: more frames may already be buffered.
  bool feed(uint8_t b, Frame& out) {
    buf_[n_++] = b;
    return scan(out);
  }
  bool drain(Frame& out) { return scan(out); }

 private:
  static constexpr int kBuf = 5 + kMaxPayload + 1;
  uint8_t buf_[kBuf];
  int n_ = 0;

  void drop_first() {
    memmove(buf_, buf_ + 1, (size_t)(n_ - 1));
    n_--;
  }

  bool scan(Frame& out) {
    while (n_ > 0) {
      if (buf_[0] != kMagic0) { drop_first(); continue; }
      if (n_ >= 2 && buf_[1] != kMagic1) { drop_first(); continue; }
      if (n_ < 5) return false;
      int len = buf_[3] | (buf_[4] << 8);
      if (len > kMaxPayload) { drop_first(); continue; }
      int total = 5 + len + 1;
      if (n_ < total) return false;
      uint8_t cs = 0;
      for (int i = 2; i < 5 + len; i++) cs ^= buf_[i];
      if (cs != buf_[5 + len]) { drop_first(); continue; }
      out.type = buf_[2];
      out.len = (uint16_t)len;
      memcpy(out.payload, buf_ + 5, (size_t)len);
      memmove(buf_, buf_ + total, (size_t)(n_ - total));
      n_ -= total;
      return true;
    }
    return false;
  }
};
