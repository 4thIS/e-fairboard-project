#pragma once

#include <stddef.h>
#include <stdint.h>

namespace node {

// 크기별(32/48/64px) native 베이크 폰트 — 확대 없음 (폰트 렌더 V2 §A).
// 가장 큰 셀 64px = 512B. 고정폭: 한글 = 전각(advance=셀), ASCII = 반각(advance=셀/2).
constexpr size_t MAX_GLYPH_BYTES = 512;
constexpr uint8_t FONT_SET_MAX = 3;

// 폰트 데이터를 어디에 두든(플래시 rodata / 호스트 파일) 렌더러는 모른다.
struct IGlyphSource {
    virtual ~IGlyphSource() = default;
    // px 크기 셋에서 cp 글립. 없는 글자면 false. cell_px 는 실제 선택된 셀(요청 px 에 맞는
    // 셋이 없으면 작은 셋으로 대체될 수 있다), advance_px 는 cell(한글)/cell÷2(ASCII).
    virtual bool glyph(uint8_t px, uint32_t cp, uint8_t out[MAX_GLYPH_BYTES], uint8_t& cell_px,
                       uint8_t& advance_px) = 0;
};

// tools/gen_font.py 가 만든 efb_common*.bin 을 읽는 글립 소스. 크기별 bin 을 add() 로
// 등록한다 (ESP32 rodata 는 그냥 포인터로 읽힌다 — pgmspace 불필요).
//
// bin 포맷 (리틀엔디언 u16): cell, glyph_bytes, ascii_n, hangul_n,
//   hangul_cps[hangul_n](오름차순), glyphs[(ascii_n+hangul_n)×glyph_bytes].
// 상용 2,350자 서브셋 — 밖의 희귀 음절은 서버 입력검증(schemas.py)이 1차 방어.
class BakedFont : public IGlyphSource {
public:
    // 헤더가 어긋나면 false — 잘못된 bin 으로 글립 밖을 읽지 않기 위해.
    bool add(const uint8_t* bin, size_t len);

    // 요청 px 와 같은 셀을 쓰고, 없으면 px 이하 최대 셋으로 낮춘다 — 서버 플립 전
    // 과도기(96/128 요청)에도 화면이 비지 않게 (넘쳐서 잘리는 것보다 작게, 이슈 #12).
    bool glyph(uint8_t px, uint32_t cp, uint8_t out[MAX_GLYPH_BYTES], uint8_t& cell_px,
               uint8_t& advance_px) override;

private:
    struct Set {
        const uint8_t* cps;     // u16 LE × hangul_n
        const uint8_t* glyphs;
        size_t glyphs_len;
        uint16_t cell, glyph_bytes, ascii_n, hangul_n;
    };
    const Set* pick(uint8_t px) const;
    Set sets_[FONT_SET_MAX];
    uint8_t set_count_ = 0;
};

struct ICanvas {
    virtual ~ICanvas() = default;
    virtual void pixel(int16_t x, int16_t y) = 0;  // 검은 점 하나
};

// UTF-8 문자열을 (x, y) 왼쪽-위 기준, px 높이(=templates.py font_size)로 그린다.
//
// 확대가 없다 — px 에 맞는 native 글립을 그대로 찍는다 (계단 없음).
// max_w 를 넘는 글자는 그리지 않는다(잘라냄) — 캔버스를 밟지 않기 위해.
// 잘린 UTF-8 시퀀스는 버린다 — 무선에서 페이로드가 깨져도 버퍼를 밟으면 안 된다.
//
// 반환값: 실제로 그린 폭(px).
int16_t draw_utf8(ICanvas& canvas, IGlyphSource& font, int16_t x, int16_t y, const char* utf8,
                  uint8_t px, int16_t max_w);

}  // namespace node
