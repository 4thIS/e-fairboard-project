#include <node/layout.h>

namespace node {

int16_t field_avail_w(const FieldDef& f, const QrDef& qr, int16_t canvas_w) {
    const bool overlaps =
        f.y < qr.y + qr.size && qr.y < f.y + static_cast<int16_t>(f.font_size);
    const int16_t right = overlaps ? qr.x : canvas_w;

    const int16_t w = right - f.x;
    return w > 0 ? w : 0;
}

}  // namespace node
