from pydantic import BaseModel, field_validator, model_validator

from .protocol.templates import TEMPLATES

_MAX_TEXT_BYTES = 198  # SET_FIELD/SET_QR text 한도 (Task 4와 동일)


class PostCreate(BaseModel):
    title: str
    template_id: int
    fields: dict[str, str] = {}
    qr_url: str = ""

    @field_validator("template_id")
    @classmethod
    def template_must_exist(cls, v: int) -> int:
        if v not in TEMPLATES:
            raise ValueError(f"unknown template_id {v}")
        return v

    @field_validator("qr_url")
    @classmethod
    def qr_url_fits_payload(cls, v: str) -> str:
        if len(v.encode("utf-8")) > _MAX_TEXT_BYTES:
            raise ValueError("qr_url too long")
        return v

    @model_validator(mode="after")
    def fields_match_template(self) -> "PostCreate":
        tpl = TEMPLATES[self.template_id]
        defs = {str(f.id): f for f in tpl.fields}
        for key, text in self.fields.items():
            if key not in defs:
                raise ValueError(f"template {self.template_id} has no field {key}")
            if len(text.encode("utf-8")) > defs[key].max_bytes:
                raise ValueError(f"field {key} exceeds {defs[key].max_bytes} bytes")
        return self
