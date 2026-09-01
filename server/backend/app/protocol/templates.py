from dataclasses import asdict, dataclass

from .packet import FIELD_MAX_TEXT

# 색 이름 — 3색 e-Paper. paper = 종이(빨강 밴드 위 흰 글자 = 두 플레인 knockout).
BLACK, RED, PAPER, NONE = "black", "red", "paper", "none"


@dataclass(frozen=True)
class FieldDef:
    """편집 가능한 텍스트 자리. color 는 글자색, w 는 명시 폭(0=QR/캔버스에서 자동),
    h 는 멀티라인 텍스트영역 높이(0=한 줄)."""
    id: int
    name: str
    x: int
    y: int
    font_size: int
    color: str = BLACK   # black|red|paper
    w: int = 0           # 명시 폭(px). 0 이면 field_avail_w 가 QR/캔버스로 계산.
    h: int = 0           # 0=한 줄. >0 이면 폭 w·높이 h 영역에서 줄바꿈(명시 \n + 단어 wrap).


@dataclass(frozen=True)
class Label:
    """고정 텍스트(비편집) — 노드가 templates.h 문자열로 그린다. '일시'·'SCAN' 같은 라벨."""
    x: int
    y: int
    font_size: int
    color: str
    text: str


@dataclass(frozen=True)
class Deco:
    """장식 사각형 하나 — 채움(fill)/테두리(stroke). 선은 얇은 fill 사각형으로 표현.
    밴드·박스·룰선·격자·코너를 이 하나로. 색: none|black|red."""
    x: int
    y: int
    w: int
    h: int
    fill: str = NONE
    stroke: str = NONE
    stroke_w: int = 0


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
    decorations: tuple[Deco, ...] = ()
    labels: tuple[Label, ...] = ()
    canvas_w: int = 1304
    canvas_h: int = 984


# 가로 템플릿의 기본 캔버스. 세로 템플릿은 984×1304 로 덮어쓴다.
CANVAS_W = 1304
CANVAS_H = 984


# ── 장식 헬퍼 (선 = 얇은 사각형) ─────────────────────────────────────────
def band(x, y, w, h, color=RED): return Deco(x, y, w, h, fill=color)
def hrule(x, y, w, color=BLACK, t=4): return Deco(x, y, w, t, fill=color)
def vrule(x, y, h, color=BLACK, t=4): return Deco(x, y, t, h, fill=color)
def box(x, y, w, h, color=RED, sw=6): return Deco(x, y, w, h, stroke=color, stroke_w=sw)


# 좌표·장식·색은 프론트 미리보기와 노드 펌웨어의 단일 기준 소스 (스펙 §5.1).
#
# font_size 는 실제 px. 노드가 자주쓰는 한글 2,000자를 40/56/72px 나눔스퀘어 Bold(비례폭)로
# 구워 그린다 (폰트 V3). 글자별 폭 assets/font_advance.json. max_bytes 는 파생(field_max_bytes).
#
# 확정 4레이아웃(격자·빨강, 아티팩트 070b3721): 0 행사안내 · 1 일정표 · 2 프로젝트소개(가로) ·
# 3 프로젝트소개(세로). 색: 빨강 밴드/박스/시간강조, 종이(흰) = 밴드 위 제목.
# 12.48" 1304×984 (세로는 패널을 세워 984×1304). 여백 x=48.
TEMPLATES: dict[int, TemplateDef] = {
    # ── 0. 행사 안내 (가로) — 빨강 헤더밴드 + 룰 격자 + 우측 QR ──
    # 규격: 여백 48. 밴드 0~200. 콘텐츠(200~984)에 3행 그리드를 상하 대칭 중앙배치
    # (룰선 360/512/664/816, 피치 152). QR 박스(304)는 그리드에 세로중앙 정렬하고
    # 우측 여백(오른끝 1256)에 맞춘 뒤, 룰선은 x=904 에서 끊어 48px 거터로 겹침을 없앤다.
    0: TemplateDef(0, "행사 안내", (
        FieldDef(0, "제목", 48, 100, 72, PAPER, w=1208),
        FieldDef(1, "일시", 240, 408, 56, w=664),
        FieldDef(2, "장소", 240, 560, 56, w=664),
        FieldDef(3, "주최", 240, 712, 56, w=664),
    ), QrDef(968, 452, 272), decorations=(
        band(0, 0, 1304, 200),
        hrule(48, 360, 856), hrule(48, 512, 856),
        hrule(48, 664, 856), hrule(48, 816, 856),
        box(952, 436, 304, 304),
    ), labels=(
        Label(48, 44, 40, PAPER, "행사 안내"),
        Label(48, 416, 40, RED, "일시"),
        Label(48, 568, 40, RED, "장소"),
        Label(48, 720, 40, RED, "주최"),
    )),

    # ── 1. 일정표 (가로) — 격자 시간표 (레퍼런스 방식) ──
    1: TemplateDef(1, "일정표", (
        FieldDef(0, "시간1", 84, 352, 56, RED, w=270),
        FieldDef(1, "세션1", 408, 352, 56, BLACK, w=840),
        FieldDef(2, "시간2", 84, 482, 56, RED, w=270),
        FieldDef(3, "세션2", 408, 482, 56, BLACK, w=840),
        FieldDef(4, "시간3", 84, 612, 56, RED, w=270),
        FieldDef(5, "세션3", 408, 612, 56, BLACK, w=840),
    ), QrDef(1060, 760, 180), decorations=(
        band(0, 0, 1304, 200),
        box(48, 240, 1208, 480, BLACK, 4),
        band(48, 240, 1208, 90),              # 헤더 행 빨강
        vrule(360, 240, 480), hrule(48, 330, 1208),
        hrule(48, 460, 1208), hrule(48, 590, 1208),
    ), labels=(
        Label(48, 64, 72, PAPER, "일정표"),
        Label(84, 262, 40, PAPER, "시간"),
        Label(408, 262, 40, PAPER, "세션"),
    )),

    # ── 2. 프로젝트 소개 (가로) — 히어로 밴드 + 넓은 설명 + 우하단 QR (시안 A) ──
    # 밴드(250) 안: PROJECT 태그·제목·태그라인(모두 종이색). 아래 설명은 멀티라인(40px, h),
    # QR 은 208 로 작게 우하단(빨강 프레임) — 설명 공간을 넓게(w=920) 확보.
    2: TemplateDef(2, "프로젝트 소개", (
        FieldDef(0, "프로젝트명", 48, 104, 72, PAPER, w=1160),
        FieldDef(1, "태그라인", 48, 196, 40, PAPER, w=1160),
        FieldDef(2, "설명", 48, 320, 40, BLACK, w=920, h=560),
    ), QrDef(1032, 600, 208), decorations=(
        band(0, 0, 1304, 250),
        box(1016, 584, 240, 240),
    ), labels=(
        Label(48, 44, 40, PAPER, "PROJECT"),
        Label(1016, 848, 40, RED, "스캔하면 상세 →"),
    )),

    # ── 3. 프로젝트 소개 (세로) — 히어로 밴드 + 큰 설명 + 우하단 작은 QR (시안 A) ──
    # 밴드(260) 안: 태그·제목·태그라인. 설명은 넓고 크게 멀티라인(폭 888, h=660).
    # QR 을 448→208 로 줄여 우하단, "스캔하면 상세 →" 는 좌하단 — 설명을 더 많이 쓰게.
    3: TemplateDef(3, "프로젝트 소개(세로)", (
        FieldDef(0, "프로젝트명", 48, 112, 72, PAPER, w=888),
        FieldDef(1, "태그라인", 48, 204, 40, PAPER, w=888),
        FieldDef(2, "설명", 48, 320, 40, BLACK, w=888, h=660),
    ), QrDef(712, 1020, 208), decorations=(
        band(0, 0, 984, 260),
        box(696, 1004, 240, 240),
    ), labels=(
        Label(48, 48, 40, PAPER, "PROJECT"),
        Label(48, 1104, 40, RED, "스캔하면 상세 →"),
    ), canvas_w=984, canvas_h=1304),
}


def field_avail_w(f: FieldDef, qr: QrDef, canvas_w: int) -> int:
    """필드 한 행이 실제로 쓸 수 있는 가로 폭(px).

    f.w 가 명시되면 그 값(격자 셀·분할 영역처럼 QR 로 표현 안 되는 경계).
    아니면 QR 박스와 세로로 겹치는 행만 QR 앞까지, 안 겹치면 캔버스 끝까지.

    node_core/layout.cpp 의 field_avail_w() 와 **같은 식**이다. 세 번째 구현 금지.
    """
    if f.w:
        return f.w
    overlaps = f.y < qr.y + qr.size and qr.y < f.y + f.font_size
    right = qr.x if overlaps else canvas_w
    return max(0, right - f.x)


def line_h(font_px: int) -> int:
    """멀티라인 줄 높이(px) — 웹 미리보기·노드 렌더 공용 규칙(1.35배, 정수)."""
    return font_px * 27 // 20


def field_lines(f: FieldDef) -> int:
    """멀티라인 필드가 담는 최대 줄 수(h=0 이면 1)."""
    return max(1, f.h // line_h(f.font_size)) if f.h else 1


def field_max_bytes(f: FieldDef, qr: QrDef, canvas_w: int) -> int:
    """화면 폭×줄수에서 나오는 UTF-8 최대 바이트 (한글 3B/자, font_px 폭 기준 보수적).
    분할 SET_FIELD 재조립 한도 FIELD_MAX_TEXT 로 상한 (198B 초과분은 여러 패킷으로 전송)."""
    per_line = field_avail_w(f, qr, canvas_w) // f.font_size
    return min(FIELD_MAX_TEXT, per_line * field_lines(f) * 3)


def as_dict() -> list[dict]:
    out = []
    for tpl in TEMPLATES.values():
        d = asdict(tpl)
        d["canvas"] = {"w": d.pop("canvas_w"), "h": d.pop("canvas_h")}
        for fd, f in zip(d["fields"], tpl.fields):
            fd["avail_w"] = field_avail_w(f, tpl.qr, tpl.canvas_w)      # 스펙 §6.2
            fd["max_bytes"] = field_max_bytes(f, tpl.qr, tpl.canvas_w)
            fd["line_h"] = line_h(f.font_size)                          # 멀티라인 줄높이(px)
        out.append(d)
    return out
