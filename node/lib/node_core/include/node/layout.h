#pragma once

#include <node/templates.h>

namespace node {

// 필드 한 행이 실제로 쓸 수 있는 가로 폭.
//
// f.w 가 있으면 그 값(격자 셀·분할 영역처럼 QR 로 표현 안 되는 경계).
// 아니면 QR 박스와 **세로로 겹치는 행만** QR 앞까지, 안 겹치면 캔버스 끝까지 쓴다.
// 행 높이는 f.font_size px 그대로다 (폰트 렌더 V2 — 정수 배율 없음).
//
// canvas_w 는 **템플릿의 것**(TemplateDef.canvas_w)을 넘긴다 — 세로 템플릿에서 전역 폭을
// 쓰면 노드는 자르는데 미리보기는 안 자르는 거짓말이 된다.
//
// server/backend/app/protocol/templates.py 의 field_avail_w() 와 **같은 식**이다 —
// 한쪽만 고치면 다른 쪽이 터진다. 세 번째 구현을 만들지 말 것.
// 반환값은 항상 0 이상이고 f.x + 반환값 <= canvas_w 를 보장한다 — 화면 밖으로 못 나간다.
int16_t field_avail_w(const FieldDef& f, const QrDef& qr, int16_t canvas_w);

}  // namespace node
