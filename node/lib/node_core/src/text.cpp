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

inline uint16_t rd16(const uint8_t* p) {
    return static_cast<uint16_t>(p[0] | (p[1] << 8));  // 리틀엔디언
}

}  // namespace

bool BakedFont::add(const uint8_t* bin, size_t len) {
    if (set_count_ >= FONT_SET_MAX || !bin || len < 8) return false;

    Set s;
    s.cell = rd16(bin);
    s.glyph_bytes = rd16(bin + 2);
    s.ascii_n = rd16(bin + 4);
    s.hangul_n = rd16(bin + 6);
    // 헤더 자기모순·크기 초과·파일 길이 부족이면 거부 — 글립 밖을 읽지 않는다.
    if (s.cell == 0 || s.cell % 8 != 0 || s.glyph_bytes != (size_t)s.cell * s.cell / 8 ||
        s.glyph_bytes > MAX_GLYPH_BYTES) {
        return false;
    }
    const size_t table = (size_t)s.hangul_n * 2;
    const size_t glyphs = (size_t)(s.ascii_n + s.hangul_n) * s.glyph_bytes;
    if (len < 8 + table + glyphs) return false;
    s.cps = bin + 8;
    s.glyphs = bin + 8 + table;
    s.glyphs_len = glyphs;

    sets_[set_count_++] = s;
    return true;
}

const BakedFont::Set* BakedFont::pick(uint8_t px) const {
    // px 이하 최대 셀 — 없으면 제일 작은 셀. (서버 플립 전 과도기 방어)
    const Set* best = nullptr;
    const Set* smallest = nullptr;
    for (uint8_t i = 0; i < set_count_; ++i) {
        const Set& s = sets_[i];
        if (!smallest || s.cell < smallest->cell) smallest = &s;
        if (s.cell <= px && (!best || s.cell > best->cell)) best = &s;
    }
    return best ? best : smallest;
}

bool BakedFont::glyph(uint8_t px, uint32_t cp, uint8_t out[MAX_GLYPH_BYTES], uint8_t& cell_px,
                      uint8_t& advance_px) {
    const Set* s = pick(px);
    if (!s) return false;

    size_t index;
    if (cp >= 0x20 && cp < 0x20u + s->ascii_n) {
        index = cp - 0x20;
        advance_px = static_cast<uint8_t>(s->cell / 2);  // ASCII 반각
    } else {
        // 상용 한글 — 오름차순 코드포인트 표를 이진탐색
        size_t lo = 0, hi = s->hangul_n;
        while (lo < hi) {
            const size_t mid = (lo + hi) / 2;
            const uint16_t v = rd16(s->cps + mid * 2);
            if (v < cp) {
                lo = mid + 1;
            } else {
                hi = mid;
            }
        }
        if (lo >= s->hangul_n || rd16(s->cps + lo * 2) != cp) return false;
        index = (size_t)s->ascii_n + lo;
        advance_px = static_cast<uint8_t>(s->cell);  // 한글 전각
    }

    const size_t off = index * s->glyph_bytes;
    if (off + s->glyph_bytes > s->glyphs_len) return false;
    for (size_t i = 0; i < s->glyph_bytes; ++i) out[i] = s->glyphs[off + i];
    cell_px = static_cast<uint8_t>(s->cell);
    return true;
}

int16_t draw_utf8(ICanvas& canvas, IGlyphSource& font, int16_t x, int16_t y, const char* utf8,
                  uint8_t px, int16_t max_w) {
    if (!utf8 || px == 0) return 0;

    int16_t pen = 0;
    uint8_t bits[MAX_GLYPH_BYTES];
    uint8_t cell = 0;
    uint8_t advance = 0;

    for (const char* p = utf8; *p;) {
        uint32_t cp = 0;
        if (!next_codepoint(p, cp)) break;  // 잘린 시퀀스 — 나머지는 믿을 수 없다
        if (!font.glyph(px, cp, bits, cell, advance)) continue;  // 없는 글자는 자리도 안 준다

        const int16_t w = advance;
        if (pen + w > max_w) break;  // 필드 폭 초과 — 잘라낸다

        const uint8_t row_bytes = cell / 8;
        for (uint8_t gy = 0; gy < cell; ++gy) {
            for (uint8_t gx = 0; gx < advance; ++gx) {
                const uint8_t byte = bits[(size_t)gy * row_bytes + (gx >> 3)];
                if (!(byte & (0x80 >> (gx & 7)))) continue;
                canvas.pixel(x + pen + gx, y + gy);
            }
        }
        pen += w;
    }
    return pen;
}

}  // namespace node
