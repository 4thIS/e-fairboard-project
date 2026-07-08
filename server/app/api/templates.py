from dataclasses import asdict

from fastapi import APIRouter

from app.core.templates import TEMPLATES

router = APIRouter(tags=["templates"])


@router.get("/templates")
def list_templates():
    return [asdict(t) for t in TEMPLATES.values()]
