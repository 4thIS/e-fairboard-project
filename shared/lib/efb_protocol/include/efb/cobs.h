#pragma once

#include <stddef.h>
#include <stdint.h>

namespace efb {

// 논리 패킷 최대 209B(7+200+2). COBS 최악 오버헤드 = ceil(n/254) + 1.
constexpr size_t COBS_MAX_ENCODED = 512;

// cobs_decode 실패 표식. 길이 0은 "빈 입력을 정상 디코딩"이라 에러로 못 쓴다.
constexpr size_t COBS_ERROR = static_cast<size_t>(-1);

// 인코딩 결과 길이. out_cap 부족이면 0 (파이썬 레퍼런스에 없는 방어 — C++는 밟으면 끝).
size_t cobs_encode(const uint8_t* in, size_t len, uint8_t* out, size_t out_cap);

// 디코딩 결과 길이. 스트림에 0x00이 있거나 블록이 잘렸거나 out_cap 부족이면 COBS_ERROR.
size_t cobs_decode(const uint8_t* in, size_t len, uint8_t* out, size_t out_cap);

}  // namespace efb
