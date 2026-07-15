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
    # 캔버스는 템플릿의 속성이다 — 세로 템플릿은 패널을 세워 480×800 을 쓴다.
    # 기본값이 있어 가로 템플릿 정의는 캔버스를 명시하지 않아도 된다.
    canvas_w: int = 800
    canvas_h: int = 480


# 가로 템플릿의 기본 캔버스. 세로 템플릿은 TemplateDef 에서 480×800 으로 덮어쓴다.
CANVAS_W = 800
CANVAS_H = 480

# 296×128 기준 좌표 — 프론트 미리보기와 노드 펌웨어 상수의 단일 기준 소스 (스펙 §5.1)
#
# font_size 는 16 또는 32 만 쓴다 (이슈 #12).
# 노드 폰트가 16×16 비트맵(efb_hangul16)이라 정수 배율만 가능하다 — 12/14/20/24px 은
# 렌더러가 32px 로 올려 그려서 글자가 잘린다. "임베디드 SW 경진대회"가 실제로 잘렸다.
#
# 800×480 기준 좌표 (스펙 2026-07-15-800x480-web-redesign-design.md §5).
# 비례 확대: 여백 x=24, 제목/헤더 48px, 본문 32px, 부스 강조 64px, QR 160px(가로)·256px(세로).
# 폰트는 16×16 비트맵의 정수배. max_bytes = (avail_w // font_px) × 3 (한글 3B).
# QR 을 우하단(가로)·가운데하단(세로)에 둬 어떤 필드 행과도 겹치지 않는다 → 모든 행 avail_w = 캔버스폭 - 24.
TEMPLATES: dict[int, TemplateDef] = {
    0: TemplateDef(0, "행사 안내", (
        FieldDef(0, "제목", 24, 32, 48, 48),
        FieldDef(1, "일시", 24, 110, 32, 72),
        FieldDef(2, "장소", 24, 158, 32, 72),
        FieldDef(3, "비고", 24, 206, 32, 72),
    ), QrDef(616, 296, 160)),
    1: TemplateDef(1, "부스 지도", (
        FieldDef(0, "구역명", 24, 40, 64, 36),
        FieldDef(1, "부스번호", 24, 150, 64, 36),
    ), QrDef(616, 296, 160)),
    2: TemplateDef(2, "모집 공고", (
        FieldDef(0, "제목", 24, 32, 48, 48),
        FieldDef(1, "마감", 24, 110, 32, 72),
        FieldDef(2, "대상", 24, 158, 32, 72),
    ), QrDef(616, 296, 160)),
    3: TemplateDef(3, "일정표", (
        FieldDef(0, "날짜", 24, 32, 48, 48),
        FieldDef(1, "세션1", 24, 110, 32, 72),
        FieldDef(2, "세션2", 24, 158, 32, 72),
        FieldDef(3, "세션3", 24, 206, 32, 72),
    ), QrDef(616, 296, 160)),
    # 세로 팜플렛 — 패널을 세워 480×800. 폭 456px, 상세 소개는 QR 너머 웹페이지.
    4: TemplateDef(4, "팀 소개", (
        FieldDef(0, "팀명", 24, 40, 48, 27),
        FieldDef(1, "주제1", 24, 140, 32, 42),
        FieldDef(2, "주제2", 24, 200, 32, 42),
        FieldDef(3, "주제3", 24, 260, 32, 42),
    ), QrDef(112, 504, 256), canvas_w=480, canvas_h=800),
}


def field_avail_w(f: FieldDef, qr: QrDef, canvas_w: int) -> int:
    """필드 한 행이 실제로 쓸 수 있는 가로 폭(px).

    QR 박스와 **세로로 겹치는 행만** QR 앞까지로 줄어든다. 안 겹치는 행은 캔버스 끝까지 쓴다.

    canvas_w 는 **템플릿의 것**을 넘긴다 — 전역 상수를 쓰면 세로 템플릿(128)에서 296 이
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
