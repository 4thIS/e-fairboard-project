#include <efb/cobs.h>

namespace efb {

size_t cobs_encode(const uint8_t* in, size_t len, uint8_t* out, size_t out_cap) {
    if (out_cap == 0) return 0;
    size_t code_index = 0;  // 코드 바이트 자리 예약
    size_t w = 1;
    uint8_t code = 1;

    for (size_t i = 0; i < len; ++i) {
        if (in[i] == 0) {
            out[code_index] = code;
            code_index = w;
            if (w >= out_cap) return 0;
            ++w;
            code = 1;
        } else {
            if (w >= out_cap) return 0;
            out[w++] = in[i];
            ++code;
            if (code == 0xFF) {  // 254 논제로 블록이 참 → 그룹 분할
                out[code_index] = code;
                code_index = w;
                if (w >= out_cap) return 0;
                ++w;
                code = 1;
            }
        }
    }
    out[code_index] = code;
    return w;
}

size_t cobs_decode(const uint8_t* in, size_t len, uint8_t* out, size_t out_cap) {
    size_t w = 0;
    size_t i = 0;
    while (i < len) {
        const uint8_t code = in[i];
        if (code == 0) return COBS_ERROR;  // 인코딩 스트림에 0x00은 있을 수 없다
        const size_t block = code - 1u;
        if (i + 1 + block > len) return COBS_ERROR;  // 잘린 블록
        if (w + block > out_cap) return COBS_ERROR;
        for (size_t k = 0; k < block; ++k) {
            const uint8_t b = in[i + 1 + k];
            if (b == 0) return COBS_ERROR;  // 유효한 COBS 스트림에는 0x00이 없다
            out[w++] = b;
        }
        i += code;
        if (code != 0xFF && i < len) {
            if (w >= out_cap) return COBS_ERROR;
            out[w++] = 0;
        }
    }
    return w;
}

}  // namespace efb
