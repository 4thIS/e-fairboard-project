#include <node/layout.h>

namespace node {

uint8_t scale_for(uint8_t font_px) {
    const uint8_t s = static_cast<uint8_t>(font_px / GLYPH_CELL);  // 16 -> 1, 32 -> 2
    return s < 1 ? 1 : s;  // 16 미만이면 0 이 되어 글자가 통째로 사라진다 — 최소 x1
}

int16_t field_avail_w(const FieldDef& f, const QrDef& qr, uint8_t scale) {
    if (scale < 1) scale = 1;

    const int16_t row_top = f.y;
    const int16_t row_bottom = f.y + static_cast<int16_t>(GLYPH_CELL) * scale - 1;
    const int16_t qr_top = qr.y;
    const int16_t qr_bottom = qr.y + qr.size - 1;

    const bool overlaps = !(row_bottom < qr_top || row_top > qr_bottom);
    const int16_t right = overlaps ? qr.x : CANVAS_W;

    const int16_t w = right - f.x;
    return w > 0 ? w : 0;
}

}  // namespace node
