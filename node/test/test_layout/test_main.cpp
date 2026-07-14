#include <unity.h>

#include <node/layout.h>
#include <node/templates.h>

void setUp() {}
void tearDown() {}

// QR 박스와 세로로 겹치는 행만 가용 폭이 QR 앞까지로 줄어든다.
// 안 겹치는 행은 캔버스 오른쪽 끝까지 쓴다 — 이슈 #12에서 우진이 지적한 규칙.
void test_row_overlapping_qr_stops_at_qr() {
    const node::QrDef qr = {224, 32, 64};       // y 32~95
    const node::FieldDef f = {1, "일시", 8, 48, 16, 45};  // y 48~63 → 겹침

    TEST_ASSERT_EQUAL_INT16(216, node::field_avail_w(f, qr, 1));  // 224 - 8
}

void test_row_above_qr_uses_full_width() {
    const node::QrDef qr = {224, 32, 64};       // y 32~95
    const node::FieldDef f = {0, "제목", 8, 8, 16, 60};  // y 8~23 → 안 겹침

    TEST_ASSERT_EQUAL_INT16(288, node::field_avail_w(f, qr, 1));  // 296 - 8
}

void test_row_below_qr_uses_full_width() {
    const node::QrDef qr = {224, 32, 64};        // y 32~95
    const node::FieldDef f = {3, "비고", 8, 100, 16, 60};  // y 100~115 → 안 겹침

    TEST_ASSERT_EQUAL_INT16(288, node::field_avail_w(f, qr, 1));
}

// 템플릿 3은 QR이 위쪽(y 8~55)이라 겹치는 행이 다르다.
void test_template3_qr_is_higher_so_top_rows_overlap() {
    const node::QrDef qr = {240, 8, 48};        // y 8~55
    const node::FieldDef date = {0, "날짜", 8, 8, 16, 30};    // y 8~23 → 겹침
    const node::FieldDef s1 = {1, "세션1", 8, 44, 16, 66};    // y 44~59 → 겹침
    const node::FieldDef s2 = {2, "세션2", 8, 72, 16, 66};    // y 72~87 → 안 겹침

    TEST_ASSERT_EQUAL_INT16(232, node::field_avail_w(date, qr, 1));  // 240 - 8
    TEST_ASSERT_EQUAL_INT16(232, node::field_avail_w(s1, qr, 1));
    TEST_ASSERT_EQUAL_INT16(288, node::field_avail_w(s2, qr, 1));
}

// 배율이 커지면 행이 세로로 길어져 겹침 판정이 바뀐다.
void test_scale_widens_the_row_and_can_start_overlapping() {
    const node::QrDef qr = {224, 32, 64};
    const node::FieldDef f = {0, "제목", 8, 8, 24, 60};  // x1: y 8~23 안겹침 / x2: y 8~39 겹침

    TEST_ASSERT_EQUAL_INT16(288, node::field_avail_w(f, qr, 1));
    TEST_ASSERT_EQUAL_INT16(216, node::field_avail_w(f, qr, 2));
}

// 어떤 필드도 캔버스 밖으로 못 나간다 — 화면 밖 오버플로 방어 (우진 요청).
void test_no_field_can_exceed_canvas() {
    for (size_t t = 0; t < node::TEMPLATE_COUNT; ++t) {
        const node::TemplateDef& tpl = node::TEMPLATES[t];
        for (uint8_t i = 0; i < tpl.field_count; ++i) {
            const node::FieldDef& f = tpl.fields[i];
            const int16_t w = node::field_avail_w(f, tpl.qr, 1);
            TEST_ASSERT_GREATER_THAN_INT16(0, w);
            TEST_ASSERT_LESS_OR_EQUAL_INT16(node::CANVAS_W, f.x + w);
        }
    }
}

int main() {
    UNITY_BEGIN();
    RUN_TEST(test_row_overlapping_qr_stops_at_qr);
    RUN_TEST(test_row_above_qr_uses_full_width);
    RUN_TEST(test_row_below_qr_uses_full_width);
    RUN_TEST(test_template3_qr_is_higher_so_top_rows_overlap);
    RUN_TEST(test_scale_widens_the_row_and_can_start_overlapping);
    RUN_TEST(test_no_field_can_exceed_canvas);
    return UNITY_END();
}
