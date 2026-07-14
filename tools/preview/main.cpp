// e-Paper 미리보기 — 펌웨어가 쓸 렌더러(node_core/text.cpp)를 호스트에서 그대로 돌린다.
// 하드웨어가 없으니 296x128 캔버스를 PBM 으로 떨궈 눈으로 확인한다.
//
// 빌드·실행: tools/preview/build.sh

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <node/layout.h>
#include <node/templates.h>
#include <node/text.h>

namespace {

constexpr uint32_t ASCII_START = 0x20;
constexpr uint32_t ASCII_END = 0x7E;
constexpr uint32_t HANGUL_START = 0xAC00;
constexpr uint32_t HANGUL_END = 0xD7A3;
constexpr size_t ASCII_COUNT = ASCII_END - ASCII_START + 1;

// assets/efb_hangul16.bin — 펌웨어에서는 PROGMEM 이나 LittleFS 가 될 자리.
class FileFont : public node::IGlyphSource {
public:
    bool load(const char* path) {
        FILE* f = fopen(path, "rb");
        if (!f) return false;
        fseek(f, 0, SEEK_END);
        size_ = static_cast<size_t>(ftell(f));
        fseek(f, 0, SEEK_SET);
        data_ = static_cast<uint8_t*>(malloc(size_));
        const bool ok = data_ && fread(data_, 1, size_, f) == size_;
        fclose(f);
        return ok;
    }

    bool glyph(uint32_t cp, uint8_t out[node::GLYPH_BYTES], uint8_t& advance_px) override {
        size_t index;
        if (cp >= ASCII_START && cp <= ASCII_END) {
            index = cp - ASCII_START;
            advance_px = 8;
        } else if (cp >= HANGUL_START && cp <= HANGUL_END) {
            index = ASCII_COUNT + (cp - HANGUL_START);
            advance_px = 16;
        } else {
            return false;
        }
        const size_t off = index * node::GLYPH_BYTES;
        if (off + node::GLYPH_BYTES > size_) return false;
        memcpy(out, data_ + off, node::GLYPH_BYTES);
        return true;
    }

private:
    uint8_t* data_ = nullptr;
    size_t size_ = 0;
};

class Bitmap : public node::ICanvas {
public:
    void clear() { memset(px_, 0, sizeof(px_)); }
    void pixel(int16_t x, int16_t y) override {
        if (x < 0 || y < 0 || x >= node::CANVAS_W || y >= node::CANVAS_H) return;
        px_[y][x] = 1;
    }
    void rect(int16_t x, int16_t y, int16_t w, int16_t h) {
        for (int16_t j = 0; j < h; ++j)
            for (int16_t i = 0; i < w; ++i) pixel(x + i, y + j);
    }
    void save_pbm(const char* path) const {
        FILE* f = fopen(path, "wb");
        fprintf(f, "P1\n%d %d\n", node::CANVAS_W, node::CANVAS_H);
        for (int16_t y = 0; y < node::CANVAS_H; ++y) {
            for (int16_t x = 0; x < node::CANVAS_W; ++x) fprintf(f, "%d ", px_[y][x]);
            fprintf(f, "\n");
        }
        fclose(f);
    }

private:
    uint8_t px_[node::CANVAS_H][node::CANVAS_W] = {};
};

// 글립은 16x16 하나. 24px 이상 필드가 남아 있으면 x2 로 그린다.
// 이슈 #12에서 우진이 templates.py 를 16px 단일로 정리하기로 했으므로, 그 뒤엔 항상 x1 이다.
// FORCE_16 은 그 변경을 미리 적용해본 결과를 보기 위한 스위치다.
uint8_t scale_for(uint8_t font_px, bool force16) {
    if (force16) return 1;
    return font_px >= 24 ? 2 : 1;
}

}  // namespace

int main(int argc, char** argv) {
    if (argc < 3) {
        fprintf(stderr, "usage: preview <font.bin> <outdir> [--force16]\n");
        return 1;
    }
    const bool force16 = argc > 3 && strcmp(argv[3], "--force16") == 0;

    FileFont font;
    if (!font.load(argv[1])) {
        fprintf(stderr, "폰트를 읽을 수 없습니다: %s\n", argv[1]);
        return 1;
    }

    // 템플릿별 실제 게시물 내용 — 관리자가 칠 법한 한글.
    const char* content[node::TEMPLATE_COUNT][node::TEMPLATE_MAX_FIELDS] = {
        {"임베디드 SW 경진대회", "2026년 7월 20일 14시", "코엑스 3층 A홀", "사전등록 필수"},
        {"창업지원구역", "B-14", nullptr, nullptr},
        {"팀원 모집 공고", "7월 31일 마감", "재학생 누구나", nullptr},
        {"7월 20일", "10시 개회식", "14시 본선 발표", "17시 시상식"},
    };

    for (size_t t = 0; t < node::TEMPLATE_COUNT; ++t) {
        const node::TemplateDef& tpl = node::TEMPLATES[t];
        Bitmap bmp;
        bmp.clear();

        printf("[%zu] %s\n", t, tpl.name);
        for (uint8_t i = 0; i < tpl.field_count; ++i) {
            const node::FieldDef& f = tpl.fields[i];
            const char* text = content[t][i];
            if (!text) continue;

            const uint8_t scale = scale_for(f.font_size, force16);
            // QR과 세로로 겹치는 행만 폭이 줄어든다 — 펌웨어와 같은 규칙 (node_core/layout.cpp)
            const int16_t avail = node::field_avail_w(f, tpl.qr, scale);
            const int16_t drawn = node::draw_utf8(bmp, font, f.x, f.y, text, scale, avail);

            // 폰트 크기별 필요 폭 vs 실제로 그려진 폭 — 잘렸으면 여기서 드러난다.
            int16_t want = 0;
            for (const char* p = text; *p;) {
                const uint8_t b = static_cast<uint8_t>(*p);
                if (b < 0x80) { want += 8 * scale; p += 1; }
                else if ((b & 0xE0) == 0xC0) { want += 16 * scale; p += 2; }
                else { want += 16 * scale; p += 3; }
            }
            printf("    %-8s %2dpx(x%d)  %3d/%3dpx  %s%s\n", f.name, f.font_size, scale, drawn,
                   want, text, drawn < want ? "   <-- 잘림" : "");
        }

        // QR 자리 표시 (실제 QR 렌더는 펌웨어의 draw_qr)
        bmp.rect(tpl.qr.x, tpl.qr.y, tpl.qr.size, 1);
        bmp.rect(tpl.qr.x, tpl.qr.y + tpl.qr.size - 1, tpl.qr.size, 1);
        bmp.rect(tpl.qr.x, tpl.qr.y, 1, tpl.qr.size);
        bmp.rect(tpl.qr.x + tpl.qr.size - 1, tpl.qr.y, 1, tpl.qr.size);

        char path[512];
        snprintf(path, sizeof(path), "%s/template%zu.pbm", argv[2], t);
        bmp.save_pbm(path);
    }
    return 0;
}
