#pragma once
// NanumGothic20 UTF-8 렌더러
// 반드시 NanumGothic20.h 이후에 include

#include "NanumGothic20.h"

// UTF-8 → 다음 코드포인트 디코딩 (포인터 자동 전진)
static uint32_t ngNextCP(const uint8_t*& p) {
    if (!*p) return 0;
    if (*p < 0x80)              return *p++;
    if ((*p & 0xE0) == 0xC0) {
        uint32_t c = ((*p & 0x1F) << 6) | (p[1] & 0x3F);
        p += 2; return c;
    }
    if ((*p & 0xF0) == 0xE0) {
        uint32_t c = ((*p & 0x0F) << 12) | ((p[1] & 0x3F) << 6) | (p[2] & 0x3F);
        p += 3; return c;
    }
    p++; return '?';
}

// 코드포인트 → 비트맵 인덱스 (-1 = 지원 안 함)
static int ngIdx(uint32_t cp) {
    if (cp >= 0x20 && cp <= 0x7E)   return (int)(cp - 0x20);
    if (cp >= 0xAC00 && cp <= 0xD7A3) return 95 + (int)(cp - 0xAC00);
    return -1;
}

// 한 글자 그리기
template<typename GFX>
void ngDrawChar(GFX& d, uint32_t cp, int16_t x, int16_t y,
                uint16_t color = GxEPD_BLACK) {
    int idx = ngIdx(cp);
    if (idx < 0) return;
    uint32_t off = (uint32_t)idx * NG20_BPG;
    for (int row = 0; row < NG20_H; row++) {
        for (int bi = 0; bi < NG20_BPR; bi++) {
            uint8_t byte = pgm_read_byte(&NanumGothic20_bitmaps[off + row * NG20_BPR + bi]);
            for (int bit = 0; bit < 8; bit++) {
                int col = bi * 8 + bit;
                if (col < NG20_W && (byte & (0x80 >> bit)))
                    d.drawPixel(x + col, y + row, color);
            }
        }
    }
}

// UTF-8 문자열 한 줄 그리기 (maxX 초과 시 잘라냄, y 고정)
template<typename GFX>
void ngPrintLine(GFX& d, const char* text, int16_t x, int16_t y,
                 int16_t maxX = 800, uint16_t color = GxEPD_BLACK) {
    int16_t cx = x;
    const uint8_t* p = (const uint8_t*)text;
    while (*p) {
        uint32_t cp = ngNextCP(p);
        if (cp == '\n' || cp == '\r') break;
        if (cx + NG20_W > maxX) break;
        ngDrawChar(d, cp, cx, y, color);
        cx += NG20_W;
    }
}

// UTF-8 문자열 그리기 (자동 줄바꿈 + \n 지원), 다음 y 반환
template<typename GFX>
int16_t ngPrint(GFX& d, const char* text, int16_t x, int16_t y,
                int16_t maxX = 800, uint16_t color = GxEPD_BLACK) {
    int16_t cx = x;
    const uint8_t* p = (const uint8_t*)text;
    while (*p) {
        uint32_t cp = ngNextCP(p);
        if (cp == '\n') { cx = x; y += NG20_H + 2; continue; }
        if (cx + NG20_W > maxX) { cx = x; y += NG20_H + 2; }
        ngDrawChar(d, cp, cx, y, color);
        cx += NG20_W;
    }
    return y + NG20_H;
}
