#include <string.h>
#include <unity.h>

#include <node/text.h>

void setUp() {}
void tearDown() {}

namespace {

// 오른쪽 절반이 빈 8px 글립(ASCII)과 꽉 찬 16px 글립(한글)만 아는 가짜 폰트.
// 실제 폰트 데이터 없이 배치·배율·advance 만 검증한다.
struct FakeFont : node::IGlyphSource {
    bool glyph(uint32_t cp, uint8_t out[node::GLYPH_BYTES], uint8_t& advance_px) override {
        memset(out, 0, node::GLYPH_BYTES);
        if (cp == '?') return false;  // 없는 글자

        if (cp < 0x80) {
            advance_px = 8;
            for (int y = 0; y < 16; ++y) out[y * 2] = 0xFF;  // 왼쪽 8px 만 채움
        } else {
            advance_px = 16;
            for (int y = 0; y < 16; ++y) {
                out[y * 2] = 0xFF;
                out[y * 2 + 1] = 0xFF;  // 16px 전부 채움
            }
        }
        return true;
    }
};

struct Canvas : node::ICanvas {
    static constexpr int16_t W = 128;
    static constexpr int16_t H = 64;
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
};

}  // namespace

// 한글은 UTF-8 3바이트다 — 바이트 단위로 잘리면 안 된다 (이슈 #12의 원인).
void test_hangul_is_decoded_as_one_glyph() {
    FakeFont font;
    Canvas c;
    const int16_t w = node::draw_utf8(c, font, 0, 0, "\xED\x95\x9C", 1, c.W);  // "한"

    TEST_ASSERT_EQUAL_INT16(16, w);  // 3바이트가 글립 하나 = advance 16px
    TEST_ASSERT_EQUAL_INT(16 * 16, c.count);
}

void test_ascii_advances_half_width() {
    FakeFont font;
    Canvas c;
    const int16_t w = node::draw_utf8(c, font, 0, 0, "AB", 1, c.W);

    TEST_ASSERT_EQUAL_INT16(16, w);  // 8px x 2
    TEST_ASSERT_TRUE(c.px[0][0]);
    TEST_ASSERT_TRUE(c.px[0][8]);    // 두 번째 글자는 8px 옆
    TEST_ASSERT_FALSE(c.px[0][16]);
}

void test_mixed_ascii_and_hangul() {
    FakeFont font;
    Canvas c;
    // "A한B" — 8 + 16 + 8
    const int16_t w = node::draw_utf8(c, font, 0, 0, "A\xED\x95\x9C" "B", 1, c.W);
    TEST_ASSERT_EQUAL_INT16(32, w);
    TEST_ASSERT_EQUAL_INT16(32, c.filled_width());
}

// 32px 필드는 16x16 글립을 2배 정수 스케일로 그린다 — 폰트 데이터 하나로 두 크기를 덮는다.
void test_scale_two_doubles_everything() {
    FakeFont font;
    Canvas c;
    const int16_t w = node::draw_utf8(c, font, 0, 0, "\xED\x95\x9C", 2, c.W);  // "한"

    TEST_ASSERT_EQUAL_INT16(32, w);
    TEST_ASSERT_EQUAL_INT(32 * 32, c.count);
    TEST_ASSERT_TRUE(c.px[31][31]);
    TEST_ASSERT_FALSE(c.px[32][32]);
}

void test_origin_offset_is_honored() {
    FakeFont font;
    Canvas c;
    node::draw_utf8(c, font, 8, 4, "A", 1, c.W);

    TEST_ASSERT_FALSE(c.px[3][8]);
    TEST_ASSERT_TRUE(c.px[4][8]);
    TEST_ASSERT_TRUE(c.px[19][8]);   // 16행
    TEST_ASSERT_FALSE(c.px[20][8]);
}

// 필드 폭을 넘는 텍스트는 잘라낸다 — 296x128 캔버스를 밟으면 안 된다.
void test_text_wider_than_field_is_clipped() {
    FakeFont font;
    Canvas c;
    const int16_t w = node::draw_utf8(c, font, 0, 0, "AAAAAAAA", 1, /*max_w=*/20);

    TEST_ASSERT_EQUAL_INT16(16, w);  // 8px 글자 2개까지만 (3번째는 24px 초과)
    TEST_ASSERT_EQUAL_INT16(16, c.filled_width());
}

void test_missing_glyph_is_skipped_not_drawn_as_garbage() {
    FakeFont font;
    Canvas c;
    const int16_t w = node::draw_utf8(c, font, 0, 0, "A?A", 1, c.W);

    TEST_ASSERT_EQUAL_INT16(16, w);  // '?' 는 폰트에 없다 → 자리도 차지하지 않는다
    TEST_ASSERT_EQUAL_INT(2 * 8 * 16, c.count);
}

// 잘린 UTF-8(무선에서 페이로드가 깨진 경우)에 버퍼를 밟으면 안 된다.
void test_truncated_utf8_does_not_overrun() {
    FakeFont font;
    Canvas c;
    const int16_t w = node::draw_utf8(c, font, 0, 0, "A\xED\x95", 1, c.W);  // 3바이트 중 2개만

    TEST_ASSERT_EQUAL_INT16(8, w);  // 'A' 만 그려지고 잘린 시퀀스는 버린다
}

int main() {
    UNITY_BEGIN();
    RUN_TEST(test_hangul_is_decoded_as_one_glyph);
    RUN_TEST(test_ascii_advances_half_width);
    RUN_TEST(test_mixed_ascii_and_hangul);
    RUN_TEST(test_scale_two_doubles_everything);
    RUN_TEST(test_origin_offset_is_honored);
    RUN_TEST(test_text_wider_than_field_is_clipped);
    RUN_TEST(test_missing_glyph_is_skipped_not_drawn_as_garbage);
    RUN_TEST(test_truncated_utf8_does_not_overrun);
    return UNITY_END();
}
