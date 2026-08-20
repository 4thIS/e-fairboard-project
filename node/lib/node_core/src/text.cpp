#include <node/text.h>

namespace node {

namespace {

// UTF-8 한 글자를 디코딩한다. 잘렸거나 부정한 시퀀스면 false 를 반환하고 in 은 끝으로 민다.
bool next_codepoint(const char*& in, uint32_t& cp) {
    const uint8_t b0 = static_cast<uint8_t>(*in);
    if (b0 == 0) return false;

    uint8_t extra;
    if (b0 < 0x80) {
        cp = b0;
        extra = 0;
    } else if ((b0 & 0xE0) == 0xC0) {
        cp = b0 & 0x1F;
        extra = 1;
    } else if ((b0 & 0xF0) == 0xE0) {  // 한글은 여기 — 3바이트
        cp = b0 & 0x0F;
        extra = 2;
    } else if ((b0 & 0xF8) == 0xF0) {
        cp = b0 & 0x07;
        extra = 3;
    } else {
        ++in;  // 연속 바이트가 홀로 왔다 — 버린다
        return false;
    }

    ++in;
    for (uint8_t i = 0; i < extra; ++i) {
        const uint8_t b = static_cast<uint8_t>(*in);
        if ((b & 0xC0) != 0x80) return false;  // 잘렸다 — 여기서 멈춘다
        cp = (cp << 6) | (b & 0x3F);
        ++in;
    }
    return true;
}

}  // namespace

int16_t draw_utf8(ICanvas& canvas, IGlyphSource& font, int16_t x, int16_t y, const char* utf8,
                  uint8_t scale, int16_t max_w) {
    if (!utf8 || scale < 1) return 0;

    int16_t pen = 0;
    uint8_t bits[GLYPH_BYTES];
    uint8_t advance = 0;

    for (const char* p = utf8; *p;) {
        uint32_t cp = 0;
        if (!next_codepoint(p, cp)) break;  // 잘린 시퀀스 — 나머지는 믿을 수 없다
        if (!font.glyph(cp, bits, advance)) continue;  // 없는 글자는 자리도 안 준다

        const int16_t w = static_cast<int16_t>(advance) * scale;
        if (pen + w > max_w) break;  // 필드 폭 초과 — 잘라낸다

        for (uint8_t gy = 0; gy < GLYPH_CELL; ++gy) {
            for (uint8_t gx = 0; gx < advance; ++gx) {
                const uint8_t byte = bits[gy * (GLYPH_CELL / 8) + (gx >> 3)];
                if (!(byte & (0x80 >> (gx & 7)))) continue;

                const int16_t px = x + pen + static_cast<int16_t>(gx) * scale;
                const int16_t py = y + static_cast<int16_t>(gy) * scale;
                for (uint8_t sy = 0; sy < scale; ++sy) {
                    for (uint8_t sx = 0; sx < scale; ++sx) {
                        canvas.pixel(px + sx, py + sy);
                    }
                }
            }
        }
        pen += w;
    }
    return pen;
}

}  // namespace node
