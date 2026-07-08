from fastapi import APIRouter, Depends

from ..deps import get_store, require_token
from ..services.stats_service import summary
from ..store import Store

router = APIRouter(prefix="/api/stats", tags=["stats"],
                   dependencies=[Depends(require_token)])


@router.get("/summary")
def stats_summary(store: Store = Depends(get_store)) -> dict:
    return summary(store)
