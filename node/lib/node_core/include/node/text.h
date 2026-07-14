#pragma once

#include <stddef.h>
#include <stdint.h>

namespace node {

// 글립은 전부 16x16 셀에 32바이트 고정 (16행 x 2바이트, MSB first).
// ASCII 는 왼쪽 8비트만 쓰고 advance 만 8px — 한글은 16px 전각.
constexpr uint8_t GLYPH_CELL = 16;
constexpr size_t GLYPH_BYTES = 32;

// 폰트 데이터를 어디에 두든(플래시 PROGMEM / LittleFS / 호스트 파일) 렌더러는 모른다.
struct IGlyphSource {
    virtual ~IGlyphSource() = default;
    // 없는 글자면 false. advance_px 는 8(ASCII) 또는 16(한글).
    virtual bool glyph(uint32_t codepoint, uint8_t out[GLYPH_BYTES], uint8_t& advance_px) = 0;
};

struct ICanvas {
    virtual ~ICanvas() = default;
    virtual void pixel(int16_t x, int16_t y) = 0;  // 검은 점 하나
};

// UTF-8 문자열을 (x, y) 왼쪽-위 기준으로 그린다.
//
// scale 은 정수 배율 — 16x16 글립 하나로 16px(x1)과 32px(x2)을 모두 덮는다.
// max_w 를 넘는 글자는 그리지 않는다(잘라냄) — 296x128 캔버스를 밟지 않기 위해.
// 잘린 UTF-8 시퀀스는 버린다 — 무선에서 페이로드가 깨져도 버퍼를 밟으면 안 된다.
//
// 반환값: 실제로 그린 폭(px).
int16_t draw_utf8(ICanvas& canvas, IGlyphSource& font, int16_t x, int16_t y, const char* utf8,
                  uint8_t scale, int16_t max_w);

}  // namespace node
