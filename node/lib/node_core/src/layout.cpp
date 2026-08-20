#include <node/layout.h>

namespace node {

int16_t field_avail_w(const FieldDef& f, const QrDef& qr, int16_t canvas_w) {
    if (f.w) return f.w;  // 명시 폭 — 격자 셀처럼 QR 로 표현 안 되는 경계

    const bool overlaps =
        f.y < qr.y + qr.size && qr.y < f.y + static_cast<int16_t>(f.font_size);
    const int16_t right = overlaps ? qr.x : canvas_w;

    const int16_t w = right - f.x;
    return w > 0 ? w : 0;
}

}  // namespace node
