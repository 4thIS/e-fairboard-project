import pytest

from app.core.templates import MAX_TEXT_BYTES, TEMPLATES, validate_fields


def test_템플릿_4종_정의():
    assert sorted(TEMPLATES) == [0, 1, 2, 3]
    assert TEMPLATES[0].name == "행사 안내"
    assert [f.field_id for f in TEMPLATES[0].fields] == [0, 1, 2, 3]


def test_정상_필드_통과():
    validate_fields(0, {0: "AI 경진대회", 1: "7/20 14:00", 2: "본관 101호"})


def test_없는_템플릿_거부():
    with pytest.raises(ValueError, match="템플릿"):
        validate_fields(9, {0: "x"})


def test_없는_필드id_거부():
    with pytest.raises(ValueError, match="필드"):
        validate_fields(1, {5: "x"})


def test_글자수_초과_거부():
    max_len = TEMPLATES[0].fields[0].max_len
    with pytest.raises(ValueError, match="초과"):
        validate_fields(0, {0: "가" * (max_len + 1)})


def test_UTF8_바이트_한도(monkeypatch):
    # 한글은 3B/자 — 글자수 제한과 별개로 198B 한도 검증
    from app.core import templates
    monkeypatch.setattr(
        templates, "TEMPLATES",
        {0: templates.TemplateDef(0, "테스트",
            (templates.FieldDef(0, "긴필드", 100),))})
    with pytest.raises(ValueError, match=str(MAX_TEXT_BYTES)):
        templates.validate_fields(0, {0: "가" * 70})   # 210B > 198B
