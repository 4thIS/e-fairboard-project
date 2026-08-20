from dataclasses import asdict, dataclass

# 색 이름 — 3색 e-Paper. paper = 종이(빨강 밴드 위 흰 글자 = 두 플레인 knockout).
BLACK, RED, PAPER, NONE = "black", "red", "paper", "none"


@dataclass(frozen=True)
class FieldDef:
    """편집 가능한 텍스트 자리. color 는 글자색, w 는 명시 폭(0=QR/캔버스에서 자동)."""
    id: int
    name: str
    x: int
    y: int
    font_size: int
    color: str = BLACK   # black|red|paper
    w: int = 0           # 명시 폭(px). 0 이면 field_avail_w 가 QR/캔버스로 계산.


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
    # ── 0. 행사 안내 (가로) — 빨강 헤더밴드 + 룰 격자 ──
    0: TemplateDef(0, "행사 안내", (
        FieldDef(0, "제목", 48, 100, 72, PAPER),
        FieldDef(1, "일시", 240, 292, 56),
        FieldDef(2, "장소", 240, 416, 56),
        FieldDef(3, "주최", 240, 540, 56),
    ), QrDef(988, 660, 272), decorations=(
        band(0, 0, 1304, 200),
        hrule(48, 268, 1208), hrule(48, 392, 1208),
        hrule(48, 516, 1208), hrule(48, 640, 1208),
        box(972, 644, 304, 304),
    ), labels=(
        Label(48, 44, 40, PAPER, "행사 안내"),
        Label(48, 300, 40, RED, "일시"),
        Label(48, 424, 40, RED, "장소"),
        Label(48, 548, 40, RED, "주최"),
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
        Label(48, 44, 40, PAPER, "일정표"),
        Label(84, 262, 40, PAPER, "시간"),
        Label(408, 262, 40, PAPER, "세션"),
    )),

    # ── 2. 프로젝트 소개 (가로) — 분할형(설명 | QR) ──
    2: TemplateDef(2, "프로젝트 소개", (
        FieldDef(0, "프로젝트명", 48, 72, 72, BLACK, w=740),
        FieldDef(1, "태그라인", 48, 180, 56, RED, w=740),
        FieldDef(2, "설명", 48, 412, 56, BLACK, w=740),
    ), QrDef(912, 348, 284), decorations=(
        vrule(824, 60, 864),
        hrule(48, 376, 732),
        box(884, 320, 340, 340),
    ), labels=(
        Label(884, 700, 40, RED, "스캔하면 상세 →"),
    )),

    # ── 3. 프로젝트 소개 (세로) — 포스터형 ──
    3: TemplateDef(3, "프로젝트 소개(세로)", (
        FieldDef(0, "프로젝트명", 48, 108, 72, PAPER, w=888),
        FieldDef(1, "태그라인", 48, 284, 56, RED, w=888),
        FieldDef(2, "설명", 48, 412, 56, BLACK, w=888),
    ), QrDef(268, 776, 448), decorations=(
        band(0, 0, 984, 220),
        hrule(48, 384, 888),
        box(252, 760, 480, 480),
    ), labels=(
        Label(48, 48, 40, PAPER, "PROJECT"),
        Label(292, 1252, 40, RED, "자세히 보기 →"),
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


def field_max_bytes(f: FieldDef, qr: QrDef, canvas_w: int) -> int:
    """화면 폭에서 나오는 UTF-8 최대 바이트 (한글 3B/자, font_px 폭 기준 보수적).
    SET_FIELD text 한도 198 로 상한."""
    return min(198, (field_avail_w(f, qr, canvas_w) // f.font_size) * 3)


def as_dict() -> list[dict]:
    out = []
    for tpl in TEMPLATES.values():
        d = asdict(tpl)
        d["canvas"] = {"w": d.pop("canvas_w"), "h": d.pop("canvas_h")}
        for fd, f in zip(d["fields"], tpl.fields):
            fd["avail_w"] = field_avail_w(f, tpl.qr, tpl.canvas_w)      # 스펙 §6.2
            fd["max_bytes"] = field_max_bytes(f, tpl.qr, tpl.canvas_w)
        out.append(d)
    return out
