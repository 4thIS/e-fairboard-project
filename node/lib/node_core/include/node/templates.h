// 자동 생성 — 수정하지 말 것. tools/gen_templates.py 로 재생성한다.
// 원본: server/backend/app/protocol/templates.py (좌표·폰트의 단일 기준 소스)
#pragma once

#include <stddef.h>
#include <stdint.h>

namespace node {

// e-Paper 7.5" 기본(가로) 캔버스. 세로 템플릿은 TemplateDef.canvas_w/h 로 덮어쓴다.
// layout.cpp 는 아직 이 전역을 쓴다 — 템플릿별 캔버스로 옮겨야 한다(준표).
constexpr int16_t CANVAS_W = 800;
constexpr int16_t CANVAS_H = 480;

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
    int16_t canvas_w;   // 가로 800 / 세로 480
    int16_t canvas_h;   // 가로 480 / 세로 800
};

constexpr TemplateDef TEMPLATES[TEMPLATE_COUNT] = {
    // 행사 안내
    {0, "행사 안내", 4, {
        {0, "제목", 24, 32, 48, 48},
        {1, "일시", 24, 110, 32, 72},
        {2, "장소", 24, 158, 32, 72},
        {3, "비고", 24, 206, 32, 72},
    }, {616, 296, 160}, 800, 480},
    // 부스 지도
    {1, "부스 지도", 2, {
        {0, "구역명", 24, 40, 64, 36},
        {1, "부스번호", 24, 150, 64, 36},
        {0, nullptr, 0, 0, 0, 0},
        {0, nullptr, 0, 0, 0, 0},
    }, {616, 296, 160}, 800, 480},
    // 모집 공고
    {2, "모집 공고", 3, {
        {0, "제목", 24, 32, 48, 48},
        {1, "마감", 24, 110, 32, 72},
        {2, "대상", 24, 158, 32, 72},
        {0, nullptr, 0, 0, 0, 0},
    }, {616, 296, 160}, 800, 480},
    // 일정표
    {3, "일정표", 4, {
        {0, "날짜", 24, 32, 48, 48},
        {1, "세션1", 24, 110, 32, 72},
        {2, "세션2", 24, 158, 32, 72},
        {3, "세션3", 24, 206, 32, 72},
    }, {616, 296, 160}, 800, 480},
    // 팀 소개
    {4, "팀 소개", 4, {
        {0, "팀명", 24, 40, 48, 27},
        {1, "주제1", 24, 140, 32, 42},
        {2, "주제2", 24, 200, 32, 42},
        {3, "주제3", 24, 260, 32, 42},
    }, {112, 504, 256}, 480, 800},
};

// 없으면 nullptr.
inline const TemplateDef* find_template(int16_t template_id) {
    for (size_t i = 0; i < TEMPLATE_COUNT; ++i) {
        if (TEMPLATES[i].id == template_id) return &TEMPLATES[i];
    }
    return nullptr;
}

}  // namespace node
