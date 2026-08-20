#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unity.h>

#include <node/text.h>

void setUp() {}
void tearDown() {}

namespace {

// 실제 bin(assets/efb_common*.bin)을 읽어 진짜 데이터를 검증한다 — 가짜 폰트로는
// 헤더 파싱·이진탐색·서브셋 커버리지를 못 잡는다. pio test 는 node/ 에서 돈다.
uint8_t* g_bin40 = nullptr;
uint8_t* g_bin72 = nullptr;
node::BakedFont g_font;

uint8_t* load(const char* path, size_t& len) {
    FILE* f = fopen(path, "rb");
    if (!f) return nullptr;
    fseek(f, 0, SEEK_END);
    len = (size_t)ftell(f);
    fseek(f, 0, SEEK_SET);
    uint8_t* buf = (uint8_t*)malloc(len);
    const bool ok = buf && fread(buf, 1, len, f) == len;
    fclose(f);
    return ok ? buf : nullptr;
}

struct Canvas : node::ICanvas {
    static constexpr int16_t W = 512;
    static constexpr int16_t H = 160;
    bool px[H][W] = {};
    int count = 0;

    void pixel(int16_t x, int16_t y) override {
        if (x < 0 || y < 0 || x >= W || y >= H) return;
        px[y][x] = true;
        ++count;
    }
    int16_t filled_width() const {
        int16_t w = 0;
        for (int16_t y = 0; y < H; ++y)
            for (int16_t x = 0; x < W; ++x)
                if (px[y][x] && x + 1 > w) w = x + 1;
        return w;
    }
    int16_t max_row() const {
        int16_t m = -1;
        for (int16_t y = 0; y < H; ++y)
            for (int16_t x = 0; x < W; ++x)
                if (px[y][x] && y > m) m = y;
        return m;
    }
};

int16_t width_of(const char* s, uint8_t px) {
    Canvas c;
    return node::draw_utf8(c, g_font, 0, 0, s, px, Canvas::W);
}

}  // namespace

// 폰트 로드는 그 자체가 테스트다 — 실패하면 나머지는 의미가 없어 여기서 멈춘다.
void test_font_bins_load() {
    size_t n40 = 0, n72 = 0;
    g_bin40 = load("../assets/efb_common40.bin", n40);
    g_bin72 = load("../assets/efb_common72.bin", n72);
    TEST_ASSERT_NOT_NULL_MESSAGE(g_bin40, "efb_common40.bin 열기 실패 — node/ 에서 실행했는가?");
    TEST_ASSERT_NOT_NULL_MESSAGE(g_bin72, "efb_common72.bin 열기 실패");
    TEST_ASSERT_TRUE(g_font.add(g_bin40, n40));
    TEST_ASSERT_TRUE(g_font.add(g_bin72, n72));
}

// 깨진 헤더(길이 부족·자기모순)는 add 가 거부한다 — 글립 밖을 읽으면 안 된다.
void test_corrupt_bin_is_rejected() {
    node::BakedFont f;
    const uint8_t junk[8] = {32, 0, 128, 0, 95, 0, 0x2E, 9};  // 표·글립이 없는 길이
    TEST_ASSERT_FALSE(f.add(junk, sizeof(junk)));
    const uint8_t bad_cell[8] = {33, 0, 128, 0, 95, 0, 0, 0};  // cell 이 8의 배수가 아님
    TEST_ASSERT_FALSE(f.add(bad_cell, sizeof(bad_cell)));
}

// 한글은 UTF-8 3바이트다 — 바이트 단위로 잘리면 안 된다 (이슈 #12의 원인).
// 고정폭: 한글 = 전각(advance = px).
void test_hangul_is_fullwidth_native() {
    Canvas c;
    const int16_t w = node::draw_utf8(c, g_font, 0, 0, "\xED\x95\x9C", 72, c.W);  // "한"

    TEST_ASSERT_EQUAL_INT16(72, w);
    TEST_ASSERT_GREATER_THAN_INT(0, c.count);
    TEST_ASSERT_LESS_THAN_INT16(72, c.max_row());  // px 셀 안에 들어온다
}

// ASCII = 반각(advance = px/2) — 서버 field_avail_w·웹 clip() 폭 모델과 동기.
void test_ascii_is_halfwidth() {
    TEST_ASSERT_EQUAL_INT16(36, width_of("A", 72));
    TEST_ASSERT_EQUAL_INT16(72, width_of("AB", 72));
    TEST_ASSERT_EQUAL_INT16(108, width_of("A\xED\x95\x9C", 72));  // 36 + 72
}

// 요청 px 셋이 없으면 px 이하 최대 셋으로 낮춰 native 로 그린다 — 화면이 비지 않게.
void test_missing_size_falls_back_to_smaller_native() {
    TEST_ASSERT_EQUAL_INT16(40, width_of("\xED\x95\x9C", 56));  // 56 미등록 → 40 셋
    TEST_ASSERT_EQUAL_INT16(72, width_of("\xED\x95\x9C", 128));  // 128 → 72 셋
}

// 필드 폭을 넘는 텍스트는 잘라낸다 — 캔버스를 밟으면 안 된다.
void test_text_wider_than_field_is_clipped() {
    Canvas c;
    node::draw_utf8(c, g_font, 0, 0, "가가가가가가가가", 72, /*max_w=*/200);

    TEST_ASSERT_LESS_OR_EQUAL_INT16(144, c.filled_width());  // 72×2 까지만
}

// 서브셋 밖 글자('뷁' — KS X 1001 상용 밖)는 자리도 주지 않는다. 1차 방어는 서버 입력검증.
void test_glyph_outside_subset_is_skipped() {
    TEST_ASSERT_EQUAL_INT16(width_of("AA", 72), width_of("A\xEB\xB7\x81" "A", 72));  // "A뷁A"
}

// 잘린 UTF-8(무선에서 페이로드가 깨진 경우)에 버퍼를 밟으면 안 된다.
void test_truncated_utf8_does_not_overrun() {
    TEST_ASSERT_EQUAL_INT16(width_of("A", 72), width_of("A\xED\x95", 72));  // 3바이트 중 2개만
}

int main() {
    UNITY_BEGIN();
    RUN_TEST(test_font_bins_load);
    RUN_TEST(test_corrupt_bin_is_rejected);
    if (!g_bin40 || !g_bin72) return UNITY_END();
    RUN_TEST(test_hangul_is_fullwidth_native);
    RUN_TEST(test_ascii_is_halfwidth);
    RUN_TEST(test_missing_size_falls_back_to_smaller_native);
    RUN_TEST(test_text_wider_than_field_is_clipped);
    RUN_TEST(test_glyph_outside_subset_is_skipped);
    RUN_TEST(test_truncated_utf8_does_not_overrun);
    return UNITY_END();
}
