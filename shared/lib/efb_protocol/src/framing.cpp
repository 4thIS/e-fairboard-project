#include <efb/framing.h>

#include <string.h>

namespace efb {

size_t encode_frame(const uint8_t* packet_bytes, size_t len, uint8_t* out, size_t out_cap) {
    if (out_cap == 0) return 0;
    const size_t n = cobs_encode(packet_bytes, len, out, out_cap - 1);  // 구분자 자리 확보
    if (n == 0) return 0;
    out[n] = 0x00;
    return n + 1;
}

void FrameAccumulator::feed(const uint8_t* chunk, size_t len) {
    for (size_t i = 0; i < len; ++i) {
        const uint8_t b = chunk[i];
        if (b == 0x00) {
            if (overflow_) {  // 넘쳐서 버리던 구간이 끝났다 — 경계를 되찾는다
                overflow_ = false;
                len_ = 0;
                continue;
            }
            if (len_ < sizeof(buf_)) buf_[len_++] = 0x00;  // 구분자를 표식으로 남긴다
            continue;
        }
        if (overflow_) continue;
        if (len_ >= sizeof(buf_)) {  // 구분자 없이 MAX_FRAME 초과 → 이 구간은 프레임이 아니다
            overflow_ = true;
            len_ = 0;
            continue;
        }
        buf_[len_++] = b;
    }
}

size_t FrameAccumulator::next(uint8_t* out, size_t out_cap) {
    while (len_ > 0) {
        size_t sep = 0;
        while (sep < len_ && buf_[sep] != 0x00) ++sep;
        if (sep == len_) return 0;  // 아직 완성된 프레임 없음

        const size_t raw_len = sep;
        size_t decoded = 0;
        if (raw_len > 0) decoded = cobs_decode(buf_, raw_len, out, out_cap);

        const size_t consumed = sep + 1;  // 구분자까지
        len_ -= consumed;
        memmove(buf_, buf_ + consumed, len_);

        if (raw_len == 0) continue;                // 빈 프레임 무시
        if (decoded == COBS_ERROR) continue;       // 깨진 프레임 폐기, 다음 것 탐색
        return decoded;
    }
    return 0;
}

void FrameAccumulator::reset() {
    len_ = 0;
    overflow_ = false;
}

}  // namespace efb
