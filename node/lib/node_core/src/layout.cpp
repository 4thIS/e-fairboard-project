#include <node/layout.h>

namespace node {

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
