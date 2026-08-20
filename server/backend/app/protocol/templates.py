from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class FieldDef:
    id: int
    name: str
    x: int
    y: int
    font_size: int
    max_bytes: int  # UTF-8 바이트 기준 (SET_FIELD text ≤ 198B)


@dataclass(frozen=True)
class QrDef:
    x: int
    y: int
    size: int


@dataclass(frozen=True)
class TemplateDef:
    id: int
    name: str
    fields: tuple[FieldDef, ...]
    qr: QrDef
    # 캔버스는 템플릿의 속성이다 — 세로 템플릿은 패널을 세워 984×1304 를 쓴다.
    # 기본값이 있어 가로 템플릿 정의는 캔버스를 명시하지 않아도 된다.
    canvas_w: int = 1304
    canvas_h: int = 984


# 가로 템플릿의 기본 캔버스. 세로 템플릿은 TemplateDef 에서 984×1304 로 덮어쓴다.
CANVAS_W = 1304
CANVAS_H = 984

# 좌표는 프론트 미리보기와 노드 펌웨어 상수의 단일 기준 소스 (스펙 §5.1)
#
# font_size 는 실제 px 높이다. 노드가 자주쓰는 한글 2,000자를 40/56/72px 로 각각 구워
# (native 비트맵, 나눔고딕코딩 Bold) 확대 없이 그린다 (폰트 렌더 V2, HANDOFF_FONT_RENDER_V2.md).
# 세 크기(40/56/72)만 쓴다 — 노드도 이 셋으로 구워야 함(안 그러면 이하 최대 셋으로 폴백).
#
# 12.48" e-Paper 1304×984 기준 (팀 소개는 패널을 세워 984×1304). 7.5"(800×480)에서 이관.
# 폰트: 제목/헤더/강조 72px(큰), 본문 56px(중간), 40px(작은)은 예약. 대형 디스플레이용.
# 여백 x=48. QR 을 필드 행 아래(가로 우하단·세로 중앙하단)에 둬 어떤 행과도 안 겹침 → 모든 행 avail_w = 캔버스폭 - 48.
# max_bytes = (avail_w // font_px) × 3 (한글 3B). 가로 avail_w=1256, 세로 avail_w=936.
TEMPLATES: dict[int, TemplateDef] = {
    0: TemplateDef(0, "행사 안내", (
        FieldDef(0, "제목", 48, 48, 72, 51),
        FieldDef(1, "일시", 48, 240, 56, 66),
        FieldDef(2, "장소", 48, 340, 56, 66),
        FieldDef(3, "비고", 48, 440, 56, 66),
    ), QrDef(968, 648, 288)),
    1: TemplateDef(1, "부스 지도", (
        FieldDef(0, "구역명", 48, 100, 72, 51),
        FieldDef(1, "부스번호", 48, 360, 72, 51),
    ), QrDef(968, 648, 288)),
    2: TemplateDef(2, "모집 공고", (
        FieldDef(0, "제목", 48, 48, 72, 51),
        FieldDef(1, "마감", 48, 240, 56, 66),
        FieldDef(2, "대상", 48, 340, 56, 66),
    ), QrDef(968, 648, 288)),
    3: TemplateDef(3, "일정표", (
        FieldDef(0, "날짜", 48, 48, 72, 51),
        FieldDef(1, "세션1", 48, 240, 56, 66),
        FieldDef(2, "세션2", 48, 340, 56, 66),
        FieldDef(3, "세션3", 48, 440, 56, 66),
    ), QrDef(968, 648, 288)),
    # 세로 팜플렛 — 패널을 세워 984×1304. 상세 소개는 QR 너머 웹페이지.
    4: TemplateDef(4, "팀 소개", (
        FieldDef(0, "팀명", 48, 64, 72, 39),
        FieldDef(1, "주제1", 48, 300, 56, 48),
        FieldDef(2, "주제2", 48, 400, 56, 48),
        FieldDef(3, "주제3", 48, 500, 56, 48),
    ), QrDef(252, 776, 480), canvas_w=984, canvas_h=1304),
}


def field_avail_w(f: FieldDef, qr: QrDef, canvas_w: int) -> int:
    """필드 한 행이 실제로 쓸 수 있는 가로 폭(px).

    QR 박스와 **세로로 겹치는 행만** QR 앞까지로 줄어든다. 안 겹치는 행은 캔버스 끝까지 쓴다.

    canvas_w 는 **템플릿의 것**을 넘긴다 — 전역 상수를 쓰면 세로 템플릿에서 가로폭이
    새어 들어와, 노드는 자르는데 미리보기는 안 자르는 거짓말이 된다.

    node_core/layout.cpp 의 field_avail_w() 와 **같은 식**이다 — 한쪽만 고치면 다른 쪽이 터진다.
    프론트는 이 값을 API 로 받아쓴다. 세 번째 구현을 만들지 말 것.
    """
    overlaps = f.y < qr.y + qr.size and qr.y < f.y + f.font_size
    right = qr.x if overlaps else canvas_w
    return max(0, right - f.x)


def as_dict() -> list[dict]:
    out = []
    for tpl in TEMPLATES.values():
        d = asdict(tpl)
        d["canvas"] = {"w": d.pop("canvas_w"), "h": d.pop("canvas_h")}
        for fd, f in zip(d["fields"], tpl.fields):
            fd["avail_w"] = field_avail_w(f, tpl.qr, tpl.canvas_w)  # 스펙 §6.2
        out.append(d)
    return out
