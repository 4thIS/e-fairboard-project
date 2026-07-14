// 자동 생성 — 수정하지 말 것. tools/gen_templates.py 로 재생성한다.
// 원본: server/backend/app/protocol/templates.py (좌표·폰트의 단일 기준 소스)
#pragma once

#include <stddef.h>
#include <stdint.h>

namespace node {

// e-Paper 2.9" 296x128 기준 좌표.
constexpr int16_t CANVAS_W = 296;
constexpr int16_t CANVAS_H = 128;

constexpr size_t TEMPLATE_COUNT = 4;
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
};

constexpr TemplateDef TEMPLATES[TEMPLATE_COUNT] = {
    // 행사 안내
    {0, "행사 안내", 4, {
        {0, "제목", 8, 8, 24, 60},
        {1, "일시", 8, 48, 16, 45},
        {2, "장소", 8, 72, 16, 45},
        {3, "비고", 8, 100, 12, 60},
    }, {224, 32, 64}},
    // 부스 지도
    {1, "부스 지도", 2, {
        {0, "구역명", 8, 12, 24, 45},
        {1, "부스번호", 8, 60, 32, 24},
        {0, nullptr, 0, 0, 0, 0},
        {0, nullptr, 0, 0, 0, 0},
    }, {224, 32, 64}},
    // 모집 공고
    {2, "모집 공고", 3, {
        {0, "제목", 8, 8, 24, 60},
        {1, "마감", 8, 52, 16, 45},
        {2, "대상", 8, 80, 16, 60},
        {0, nullptr, 0, 0, 0, 0},
    }, {224, 32, 64}},
    // 일정표
    {3, "일정표", 4, {
        {0, "날짜", 8, 8, 20, 30},
        {1, "세션1", 8, 44, 14, 66},
        {2, "세션2", 8, 72, 14, 66},
        {3, "세션3", 8, 100, 14, 66},
    }, {240, 8, 48}},
};

// 없으면 nullptr.
inline const TemplateDef* find_template(int16_t template_id) {
    for (size_t i = 0; i < TEMPLATE_COUNT; ++i) {
        if (TEMPLATES[i].id == template_id) return &TEMPLATES[i];
    }
    return nullptr;
}

}  // namespace node
