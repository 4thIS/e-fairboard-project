// 자동 생성 — 수정하지 말 것. tools/gen_templates.py 로 재생성한다.
// 원본: server/backend/app/protocol/templates.py (단일 기준 소스)
#pragma once

#include <stddef.h>
#include <stdint.h>

namespace node {

constexpr int16_t CANVAS_W = 1304;  // 가로 기본. 템플릿별 canvas_w/h 가 우선.
constexpr int16_t CANVAS_H = 984;

constexpr size_t TEMPLATE_COUNT = 4;
constexpr size_t TEMPLATE_MAX_FIELDS = 6;
constexpr size_t TEMPLATE_MAX_DECOS = 7;
constexpr size_t TEMPLATE_MAX_LABELS = 4;

// 색: 0=검정 1=빨강 2=종이(빨강밴드 위 흰글자=두 플레인 knockout)
// 장식 fill/stroke: 0=none 1=검정 2=빨강

struct FieldDef {
    uint8_t id;
    const char* name;
    int16_t x;
    int16_t y;
    uint8_t font_size;
    uint8_t color;
    uint8_t max_bytes;  // UTF-8 바이트 (파생)
    int16_t w;          // 명시 폭(0=QR/캔버스 자동)
};

struct Label {  // 고정 텍스트
    int16_t x;
    int16_t y;
    uint8_t font_size;
    uint8_t color;
    const char* text;
};

struct Deco {  // 장식 사각형 (선=얇은 fill)
    int16_t x;
    int16_t y;
    int16_t w;
    int16_t h;
    uint8_t fill;
    uint8_t stroke;
    uint8_t stroke_w;
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
    uint8_t deco_count;
    Deco decos[TEMPLATE_MAX_DECOS];
    uint8_t label_count;
    Label labels[TEMPLATE_MAX_LABELS];
    int16_t canvas_w;
    int16_t canvas_h;
};

constexpr TemplateDef TEMPLATES[TEMPLATE_COUNT] = {
    // 행사 안내
    {0, "행사 안내", 4, {
        {0, "제목", 48, 100, 72, 2, 48, 1208},
        {1, "일시", 240, 408, 56, 0, 33, 664},
        {2, "장소", 240, 560, 56, 0, 33, 664},
        {3, "주최", 240, 712, 56, 0, 33, 664},
        {0, nullptr, 0, 0, 0, 0, 0, 0},
        {0, nullptr, 0, 0, 0, 0, 0, 0},
    }, {968, 452, 272},
    6, {
        {0, 0, 1304, 200, 2, 0, 0},
        {48, 360, 856, 4, 1, 0, 0},
        {48, 512, 856, 4, 1, 0, 0},
        {48, 664, 856, 4, 1, 0, 0},
        {48, 816, 856, 4, 1, 0, 0},
        {952, 436, 304, 304, 0, 2, 6},
        {0, 0, 0, 0, 0, 0, 0},
    },
    4, {
        {48, 44, 40, 2, "행사 안내"},
        {48, 416, 40, 1, "일시"},
        {48, 568, 40, 1, "장소"},
        {48, 720, 40, 1, "주최"},
    },
    1304, 984},
    // 일정표
    {1, "일정표", 6, {
        {0, "시간1", 84, 352, 56, 1, 12, 270},
        {1, "세션1", 408, 352, 56, 0, 45, 840},
        {2, "시간2", 84, 482, 56, 1, 12, 270},
        {3, "세션2", 408, 482, 56, 0, 45, 840},
        {4, "시간3", 84, 612, 56, 1, 12, 270},
        {5, "세션3", 408, 612, 56, 0, 45, 840},
    }, {1060, 760, 180},
    7, {
        {0, 0, 1304, 200, 2, 0, 0},
        {48, 240, 1208, 480, 0, 1, 4},
        {48, 240, 1208, 90, 2, 0, 0},
        {360, 240, 4, 480, 1, 0, 0},
        {48, 330, 1208, 4, 1, 0, 0},
        {48, 460, 1208, 4, 1, 0, 0},
        {48, 590, 1208, 4, 1, 0, 0},
    },
    3, {
        {48, 64, 72, 2, "일정표"},
        {84, 262, 40, 2, "시간"},
        {408, 262, 40, 2, "세션"},
        {0, 0, 0, 0, nullptr},
    },
    1304, 984},
    // 프로젝트 소개
    {2, "프로젝트 소개", 3, {
        {0, "프로젝트명", 48, 100, 72, 2, 48, 1160},
        {1, "태그라인", 48, 268, 56, 1, 39, 740},
        {2, "설명", 48, 396, 56, 0, 39, 740},
        {0, nullptr, 0, 0, 0, 0, 0, 0},
        {0, nullptr, 0, 0, 0, 0, 0, 0},
        {0, nullptr, 0, 0, 0, 0, 0, 0},
    }, {912, 392, 284},
    4, {
        {0, 0, 1304, 200, 2, 0, 0},
        {824, 260, 4, 664, 1, 0, 0},
        {48, 360, 740, 4, 1, 0, 0},
        {884, 364, 340, 340, 0, 2, 6},
        {0, 0, 0, 0, 0, 0, 0},
        {0, 0, 0, 0, 0, 0, 0},
        {0, 0, 0, 0, 0, 0, 0},
    },
    2, {
        {48, 44, 40, 2, "프로젝트 소개"},
        {884, 728, 40, 1, "스캔하면 상세 →"},
        {0, 0, 0, 0, nullptr},
        {0, 0, 0, 0, nullptr},
    },
    1304, 984},
    // 프로젝트 소개(세로)
    {3, "프로젝트 소개(세로)", 3, {
        {0, "프로젝트명", 48, 108, 72, 2, 36, 888},
        {1, "태그라인", 48, 284, 56, 1, 45, 888},
        {2, "설명", 48, 412, 56, 0, 45, 888},
        {0, nullptr, 0, 0, 0, 0, 0, 0},
        {0, nullptr, 0, 0, 0, 0, 0, 0},
        {0, nullptr, 0, 0, 0, 0, 0, 0},
    }, {268, 776, 448},
    3, {
        {0, 0, 984, 220, 2, 0, 0},
        {48, 384, 888, 4, 1, 0, 0},
        {252, 760, 480, 480, 0, 2, 6},
        {0, 0, 0, 0, 0, 0, 0},
        {0, 0, 0, 0, 0, 0, 0},
        {0, 0, 0, 0, 0, 0, 0},
        {0, 0, 0, 0, 0, 0, 0},
    },
    2, {
        {48, 48, 40, 2, "프로젝트 소개"},
        {292, 1252, 40, 1, "자세히 보기 →"},
        {0, 0, 0, 0, nullptr},
        {0, 0, 0, 0, nullptr},
    },
    984, 1304},
};

// 없으면 nullptr.
inline const TemplateDef* find_template(int16_t template_id) {
    for (size_t i = 0; i < TEMPLATE_COUNT; ++i) {
        if (TEMPLATES[i].id == template_id) return &TEMPLATES[i];
    }
    return nullptr;
}

}  // namespace node
