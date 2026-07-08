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


# 296×128 기준 좌표 — 프론트 미리보기와 노드 펌웨어 상수의 단일 기준 소스 (스펙 §5.1)
TEMPLATES: dict[int, TemplateDef] = {
    0: TemplateDef(0, "행사 안내", (
        FieldDef(0, "제목", 8, 8, 24, 60),
        FieldDef(1, "일시", 8, 48, 16, 45),
        FieldDef(2, "장소", 8, 72, 16, 45),
        FieldDef(3, "비고", 8, 100, 12, 60),
    ), QrDef(224, 32, 64)),
    1: TemplateDef(1, "부스 지도", (
        FieldDef(0, "구역명", 8, 12, 24, 45),
        FieldDef(1, "부스번호", 8, 60, 32, 24),
    ), QrDef(224, 32, 64)),
    2: TemplateDef(2, "모집 공고", (
        FieldDef(0, "제목", 8, 8, 24, 60),
        FieldDef(1, "마감", 8, 52, 16, 45),
        FieldDef(2, "대상", 8, 80, 16, 60),
    ), QrDef(224, 32, 64)),
    3: TemplateDef(3, "일정표", (
        FieldDef(0, "날짜", 8, 8, 20, 30),
        FieldDef(1, "세션1", 8, 44, 14, 66),
        FieldDef(2, "세션2", 8, 72, 14, 66),
        FieldDef(3, "세션3", 8, 100, 14, 66),
    ), QrDef(240, 8, 48)),
}


def as_dict() -> list[dict]:
    return [asdict(tpl) for tpl in TEMPLATES.values()]
