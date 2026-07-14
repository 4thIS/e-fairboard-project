#pragma once

#include <node/templates.h>
#include <node/text.h>

namespace node {

// 글립은 16x16 하나뿐이라 정수 배율만 가능하다 — templates.py 는 16/32px 만 쓴다 (이슈 #12).
// 16px 이 아닌 크기(12/14/20/24)는 내림한다. 예전 임시 코드는 24px 을 x2(=32px)로 올려 그려서
// "임베디드 SW 경진대회"의 뒤가 잘렸다. 넘쳐서 잘리는 것보다 작게 그리는 게 낫다.
uint8_t scale_for(uint8_t font_px);

// 필드 한 행이 실제로 쓸 수 있는 가로 폭.
//
// QR 박스와 **세로로 겹치는 행만** QR 앞까지로 줄어든다. 안 겹치는 행은 캔버스 끝까지 쓴다.
// 템플릿 3은 QR이 위쪽(y 8~55)이라 겹치는 행이 다른데, 이 규칙 하나로 전부 처리된다.
//
// 반환값은 항상 0 이상이고 f.x + 반환값 <= CANVAS_W 를 보장한다 — 화면 밖으로 못 나간다.
int16_t field_avail_w(const FieldDef& f, const QrDef& qr, uint8_t scale);

}  // namespace node
