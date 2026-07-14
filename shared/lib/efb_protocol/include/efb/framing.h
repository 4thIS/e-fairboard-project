#pragma once

#include <stddef.h>
#include <stdint.h>

#include <efb/cobs.h>
#include <efb/packet.h>

namespace efb {

// 프레임 = COBS(논리패킷) + 0x00 (PROTOCOL.md §7).
constexpr size_t MAX_FRAME = COBS_MAX_ENCODED;

// 프레임 길이(구분자 포함). out_cap 부족이면 0.
size_t encode_frame(const uint8_t* packet_bytes, size_t len, uint8_t* out, size_t out_cap);

// 바이트 스트림에서 0x00 구분 프레임을 뽑아낸다. 서버 FrameAccumulator 와 같은 역할.
//
// 파이썬 레퍼런스와 다른 점: 내부 버퍼가 고정 크기다. 구분자 없는 쓰레기가 계속 들어와
// MAX_FRAME 을 넘으면 그 구간을 버린다 — 게이트웨이는 24/7 도는데 힙이 없다.
class FrameAccumulator {
public:
    void feed(const uint8_t* chunk, size_t len);

    // 완성된 프레임 하나를 COBS 디코딩해 out 에 넣고 길이를 반환. 없으면 0.
    // 깨진 프레임은 조용히 버리고 다음 것을 찾는다 — 최종 방어선은 상위 CRC.
    size_t next(uint8_t* out, size_t out_cap);

    void reset();

private:
    uint8_t buf_[MAX_FRAME] = {};
    size_t len_ = 0;
    bool overflow_ = false;  // 구분자를 만날 때까지 버리는 중
};

}  // namespace efb
