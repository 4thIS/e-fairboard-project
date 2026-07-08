"""노드 템플릿 정의 (PROTOCOL §8). 좌표·폰트는 펌웨어 상수, 서버는 값만 검증·전송.

max_len은 서버 잠정치 — e-Paper 렌더 실측 후 펌웨어와 동기화할 것.
"""
from dataclasses import dataclass

MAX_TEXT_BYTES = 198   # SET_FIELD payload 한도: 200 - field_id(1) - text_len(1)


@dataclass(frozen=True)
class FieldDef:
    field_id: int
    label: str
    max_len: int   # 글자 수


@dataclass(frozen=True)
class TemplateDef:
    template_id: int
    name: str
    fields: tuple[FieldDef, ...]
    qr_slots: int = 1


TEMPLATES: dict[int, TemplateDef] = {
    0: TemplateDef(0, "행사 안내", (
        FieldDef(0, "제목", 32), FieldDef(1, "일시", 24),
        FieldDef(2, "장소", 24), FieldDef(3, "비고", 40))),
    1: TemplateDef(1, "부스 지도", (
        FieldDef(0, "구역명", 16), FieldDef(1, "부스번호", 8))),
    2: TemplateDef(2, "모집 공고", (
        FieldDef(0, "제목", 32), FieldDef(1, "마감", 24), FieldDef(2, "대상", 24))),
    3: TemplateDef(3, "일정표", (
        FieldDef(0, "날짜", 16), FieldDef(1, "세션1", 32),
        FieldDef(2, "세션2", 32), FieldDef(3, "세션3", 32))),
}


def validate_fields(template_id: int, fields: dict[int, str]) -> None:
    tpl = TEMPLATES.get(template_id)
    if tpl is None:
        raise ValueError(f"알 수 없는 템플릿 {template_id}")
    defs = {f.field_id: f for f in tpl.fields}
    for fid, text in fields.items():
        f = defs.get(fid)
        if f is None:
            raise ValueError(f"템플릿 {template_id}에 없는 필드 {fid}")
        if len(text) > f.max_len:
            raise ValueError(f"{f.label}: {f.max_len}자 초과")
        if len(text.encode()) > MAX_TEXT_BYTES:
            raise ValueError(f"{f.label}: {MAX_TEXT_BYTES}B 초과")
