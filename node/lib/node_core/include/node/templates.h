// 자동 생성 — 수정하지 말 것. tools/gen_templates.py 로 재생성한다.
// 원본: server/backend/app/protocol/templates.py (좌표·폰트의 단일 기준 소스)
#pragma once

#include <stddef.h>
#include <stdint.h>

namespace node {

// e-Paper 2.9" 기본(가로) 캔버스. 세로 템플릿은 TemplateDef.canvas_w/h 로 덮어쓴다.
// layout.cpp 는 아직 이 전역을 쓴다 — 세로 지원 시 템플릿 값으로 옮겨야 한다(준표).
constexpr int16_t CANVAS_W = 296;
constexpr int16_t CANVAS_H = 128;

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
    int16_t canvas_w;   // 가로 296 / 세로 128
    int16_t canvas_h;   // 가로 128 / 세로 296
};

constexpr TemplateDef TEMPLATES[TEMPLATE_COUNT] = {
    // 행사 안내
    {0, "행사 안내", 4, {
        {0, "제목", 8, 8, 16, 54},
        {1, "일시", 8, 48, 16, 39},
        {2, "장소", 8, 72, 16, 39},
        {3, "비고", 8, 100, 16, 54},
    }, {224, 32, 64}, 296, 128},
    // 부스 지도
    {1, "부스 지도", 2, {
        {0, "구역명", 8, 12, 32, 18},
        {1, "부스번호", 8, 60, 32, 18},
        {0, nullptr, 0, 0, 0, 0},
        {0, nullptr, 0, 0, 0, 0},
    }, {224, 32, 64}, 296, 128},
    // 모집 공고
    {2, "모집 공고", 3, {
        {0, "제목", 8, 8, 16, 54},
        {1, "마감", 8, 52, 16, 39},
        {2, "대상", 8, 80, 16, 39},
        {0, nullptr, 0, 0, 0, 0},
    }, {224, 32, 64}, 296, 128},
    // 일정표
    {3, "일정표", 4, {
        {0, "날짜", 8, 8, 16, 30},
        {1, "세션1", 8, 44, 16, 42},
        {2, "세션2", 8, 72, 16, 54},
        {3, "세션3", 8, 100, 16, 54},
    }, {240, 8, 48}, 296, 128},
    // 팀 소개
    {4, "팀 소개", 4, {
        {0, "팀명", 8, 8, 16, 21},
        {1, "주제1", 8, 40, 16, 21},
        {2, "주제2", 8, 62, 16, 21},
        {3, "주제3", 8, 84, 16, 21},
    }, {16, 140, 96}, 128, 296},
};

// 없으면 nullptr.
inline const TemplateDef* find_template(int16_t template_id) {
    for (size_t i = 0; i < TEMPLATE_COUNT; ++i) {
        if (TEMPLATES[i].id == template_id) return &TEMPLATES[i];
    }
    return nullptr;
}

}  // namespace node
