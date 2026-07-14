#pragma once

#include <node/templates.h>
#include <node/text.h>

namespace node {

// 필드 한 행이 실제로 쓸 수 있는 가로 폭.
//
// QR 박스와 **세로로 겹치는 행만** QR 앞까지로 줄어든다. 안 겹치는 행은 캔버스 끝까지 쓴다.
// 템플릿 3은 QR이 위쪽(y 8~55)이라 겹치는 행이 다른데, 이 규칙 하나로 전부 처리된다.
//
// 반환값은 항상 0 이상이고 f.x + 반환값 <= CANVAS_W 를 보장한다 — 화면 밖으로 못 나간다.
int16_t field_avail_w(const FieldDef& f, const QrDef& qr, uint8_t scale);

}  // namespace node
