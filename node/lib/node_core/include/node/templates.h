// 자동 생성 — 수정하지 말 것. tools/gen_templates.py 로 재생성한다.
// 원본: server/backend/app/protocol/templates.py (좌표·폰트의 단일 기준 소스)
#pragma once

#include <stddef.h>
#include <stdint.h>

namespace node {

// e-Paper 12.48" 기본(가로) 캔버스. 세로 템플릿은 TemplateDef.canvas_w/h 로 덮어쓴다.
// layout.cpp 는 아직 이 전역을 쓴다 — 템플릿별 캔버스로 옮겨야 한다(준표/hm).
constexpr int16_t CANVAS_W = 1304;
constexpr int16_t CANVAS_H = 984;

constexpr size_t TEMPLATE_COUNT = 5;
constexpr size_t TEMPLATE_MAX_FIELDS = 4;

struct FieldDef {
    uint8_t id;
    const char* name;
    int16_t x;
    int16_t y;
    uint8_t font_size;
    uint8_t max_bytes;  // UTF-8 바이트 기준
};

struct QrDef {
    int16_t x;
    int16_t y;
    int16_t size;
};

struct TemplateDef {
    uint8_t id;
    const char* name;
    uint8_t field_count;
    FieldDef fields[TEMPLATE_MAX_FIELDS];
    QrDef qr;
    int16_t canvas_w;   // 가로 1304 / 세로 984
    int16_t canvas_h;   // 가로 984 / 세로 1304
};

constexpr TemplateDef TEMPLATES[TEMPLATE_COUNT] = {
    // 행사 안내
    {0, "행사 안내", 4, {
        {0, "제목", 48, 48, 80, 45},
        {1, "일시", 48, 240, 48, 78},
        {2, "장소", 48, 340, 48, 78},
        {3, "비고", 48, 440, 48, 78},
    }, {968, 648, 288}, 1304, 984},
    // 부스 지도
    {1, "부스 지도", 2, {
        {0, "구역명", 48, 100, 128, 27},
        {1, "부스번호", 48, 360, 128, 27},
        {0, nullptr, 0, 0, 0, 0},
        {0, nullptr, 0, 0, 0, 0},
    }, {968, 648, 288}, 1304, 984},
    // 모집 공고
    {2, "모집 공고", 3, {
        {0, "제목", 48, 48, 80, 45},
        {1, "마감", 48, 240, 48, 78},
        {2, "대상", 48, 340, 48, 78},
        {0, nullptr, 0, 0, 0, 0},
    }, {968, 648, 288}, 1304, 984},
    // 일정표
    {3, "일정표", 4, {
        {0, "날짜", 48, 48, 80, 45},
        {1, "세션1", 48, 240, 48, 78},
        {2, "세션2", 48, 340, 48, 78},
        {3, "세션3", 48, 440, 48, 78},
    }, {968, 648, 288}, 1304, 984},
    // 팀 소개
    {4, "팀 소개", 4, {
        {0, "팀명", 48, 64, 80, 33},
        {1, "주제1", 48, 300, 48, 57},
        {2, "주제2", 48, 400, 48, 57},
        {3, "주제3", 48, 500, 48, 57},
    }, {252, 776, 480}, 984, 1304},
};

// 없으면 nullptr.
inline const TemplateDef* find_template(int16_t template_id) {
    for (size_t i = 0; i < TEMPLATE_COUNT; ++i) {
        if (TEMPLATES[i].id == template_id) return &TEMPLATES[i];
    }
    return nullptr;
}

}  // namespace node
