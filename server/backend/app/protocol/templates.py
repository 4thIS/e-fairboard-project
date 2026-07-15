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
    # 캔버스는 템플릿의 속성이다 — 세로 템플릿은 패널을 세워 128×296 을 쓴다.
    # 기본값이 있어 기존 가로 템플릿 정의는 한 글자도 안 바뀐다.
    canvas_w: int = 296
    canvas_h: int = 128


# 가로 템플릿의 기본 캔버스. 세로 템플릿은 TemplateDef 에서 128×296 으로 덮어쓴다.
CANVAS_W = 296
CANVAS_H = 128

# 296×128 기준 좌표 — 프론트 미리보기와 노드 펌웨어 상수의 단일 기준 소스 (스펙 §5.1)
#
# font_size 는 16 또는 32 만 쓴다 (이슈 #12).
# 노드 폰트가 16×16 비트맵(efb_hangul16)이라 정수 배율만 가능하다 — 12/14/20/24px 은
# 렌더러가 32px 로 올려 그려서 글자가 잘린다. "임베디드 SW 경진대회"가 실제로 잘렸다.
#
# max_bytes 는 페이로드 한도(198B)가 아니라 **화면 폭**에서 나온다. 한글 1자 = 16px(3B),
# QR 박스와 y 가 겹치는 행은 가용 폭이 QR.x - 8 로 줄어든다:
#   겹치지 않는 행 = 288px → 18자(54B) / QR(224) 겹침 = 216px → 13자(39B)
#   QR(240) 겹침(템플릿 3) = 232px → 14자(42B) / 32px 글자는 위 글자수의 절반
TEMPLATES: dict[int, TemplateDef] = {
    0: TemplateDef(0, "행사 안내", (
        FieldDef(0, "제목", 8, 8, 16, 54),
        FieldDef(1, "일시", 8, 48, 16, 39),
        FieldDef(2, "장소", 8, 72, 16, 39),
        FieldDef(3, "비고", 8, 100, 16, 54),
    ), QrDef(224, 32, 64)),
    # 부스 지도만 32px — 부스번호는 멀리서 식별하는 게 목적이라 16px 이면 쓸모가 없다.
    # 구역명 6자 제한은 빡빡해 보이나 "창업지원구역"이 정확히 들어간다.
    1: TemplateDef(1, "부스 지도", (
        FieldDef(0, "구역명", 8, 12, 32, 18),
        FieldDef(1, "부스번호", 8, 60, 32, 18),
    ), QrDef(224, 32, 64)),
    2: TemplateDef(2, "모집 공고", (
        FieldDef(0, "제목", 8, 8, 16, 54),
        FieldDef(1, "마감", 8, 52, 16, 39),
        FieldDef(2, "대상", 8, 80, 16, 39),
    ), QrDef(224, 32, 64)),
    3: TemplateDef(3, "일정표", (
        FieldDef(0, "날짜", 8, 8, 16, 30),
        FieldDef(1, "세션1", 8, 44, 16, 42),
        FieldDef(2, "세션2", 8, 72, 16, 54),
        FieldDef(3, "세션3", 8, 100, 16, 54),
    ), QrDef(240, 8, 48)),
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
