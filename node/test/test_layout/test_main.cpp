#include <unity.h>

#include <node/layout.h>
#include <node/templates.h>

void setUp() {}
void tearDown() {}

// QR 박스와 세로로 겹치는 행만 가용 폭이 QR 앞까지로 줄어든다.
// 안 겹치는 행은 캔버스 오른쪽 끝까지 쓴다 — 이슈 #12에서 우진이 지적한 규칙.
// 행 높이는 font_size px 그대로다 (폰트 렌더 V2 — 정수 배율 없음).
void test_row_overlapping_qr_stops_at_qr() {
    const node::QrDef qr = {224, 32, 64};       // y 32~95
    const node::FieldDef f = {1, "일시", 8, 48, 16, 0, 45, 0};  // y 48~63 → 겹침

    TEST_ASSERT_EQUAL_INT16(216, node::field_avail_w(f, qr, 296));  // 224 - 8
}

void test_row_above_qr_uses_full_width() {
    const node::QrDef qr = {224, 32, 64};       // y 32~95
    const node::FieldDef f = {0, "제목", 8, 8, 16, 0, 60, 0};  // y 8~23 → 안 겹침

    TEST_ASSERT_EQUAL_INT16(288, node::field_avail_w(f, qr, 296));  // 296 - 8
}

void test_row_below_qr_uses_full_width() {
    const node::QrDef qr = {224, 32, 64};        // y 32~95
    const node::FieldDef f = {3, "비고", 8, 100, 16, 0, 60, 0};  // y 100~115 → 안 겹침

    TEST_ASSERT_EQUAL_INT16(288, node::field_avail_w(f, qr, 296));
}

// QR이 위쪽이면 겹치는 행이 다르다 — 규칙 하나로 전부 처리돼야 한다.
void test_higher_qr_makes_top_rows_overlap() {
    const node::QrDef qr = {240, 8, 48};        // y 8~55
    const node::FieldDef date = {0, "날짜", 8, 8, 16, 0, 30, 0};    // y 8~23 → 겹침
    const node::FieldDef s1 = {1, "세션1", 8, 44, 16, 0, 66, 0};    // y 44~59 → 겹침
    const node::FieldDef s2 = {2, "세션2", 8, 72, 16, 0, 66, 0};    // y 72~87 → 안 겹침

    TEST_ASSERT_EQUAL_INT16(232, node::field_avail_w(date, qr, 296));  // 240 - 8
    TEST_ASSERT_EQUAL_INT16(232, node::field_avail_w(s1, qr, 296));
    TEST_ASSERT_EQUAL_INT16(288, node::field_avail_w(s2, qr, 296));
}

// 명시 폭(f.w)이 있으면 QR 겹침 계산을 건너뛴다 — 격자 셀처럼 QR 로 표현 안 되는 경계.
// templates.py 의 field_avail_w 와 같은 규칙이라 서버·미리보기와 잘리는 지점이 같아야 한다.
void test_explicit_width_wins_over_qr_rule() {
    const node::QrDef qr = {224, 32, 64};
    const node::FieldDef cell = {0, "시간1", 8, 48, 16, 0, 12, 120};  // QR 과 겹치지만 w 명시

    TEST_ASSERT_EQUAL_INT16(120, node::field_avail_w(cell, qr, 296));
}

// font_size 가 커지면 행이 세로로 길어져 겹침 판정이 바뀐다 — px 그대로, 배율 없음.
void test_bigger_font_makes_the_row_taller_and_can_start_overlapping() {
    const node::QrDef qr = {224, 32, 64};
    const node::FieldDef f24 = {0, "제목", 8, 8, 24, 0, 60, 0};  // y 8~31 → 안 겹침 (32 미도달)
    const node::FieldDef f48 = {0, "제목", 8, 8, 48, 0, 60, 0};  // y 8~55 → 겹침

    TEST_ASSERT_EQUAL_INT16(288, node::field_avail_w(f24, qr, 296));
    TEST_ASSERT_EQUAL_INT16(216, node::field_avail_w(f48, qr, 296));
}

// 어떤 필드도 캔버스 밖으로 못 나간다 — 화면 밖 오버플로 방어 (우진 요청).
// canvas_w 는 템플릿의 것을 쓴다 — 세로 템플릿(984x1304)이 전역 폭을 쓰면 새어 나간다.
void test_no_field_can_exceed_canvas() {
    for (size_t t = 0; t < node::TEMPLATE_COUNT; ++t) {
        const node::TemplateDef& tpl = node::TEMPLATES[t];
        for (uint8_t i = 0; i < tpl.field_count; ++i) {
            const node::FieldDef& f = tpl.fields[i];
            const int16_t w = node::field_avail_w(f, tpl.qr, tpl.canvas_w);
            TEST_ASSERT_GREATER_THAN_INT16(0, w);
            TEST_ASSERT_LESS_OR_EQUAL_INT16(tpl.canvas_w, f.x + w);
        }
    }
}

int main() {
    UNITY_BEGIN();
    RUN_TEST(test_row_overlapping_qr_stops_at_qr);
    RUN_TEST(test_row_above_qr_uses_full_width);
    RUN_TEST(test_row_below_qr_uses_full_width);
    RUN_TEST(test_higher_qr_makes_top_rows_overlap);
    RUN_TEST(test_explicit_width_wins_over_qr_rule);
    RUN_TEST(test_bigger_font_makes_the_row_taller_and_can_start_overlapping);
    RUN_TEST(test_no_field_can_exceed_canvas);
    return UNITY_END();
}
