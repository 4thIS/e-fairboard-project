from dataclasses import asdict

from fastapi import APIRouter, Request

router = APIRouter(tags=["stats"])


@router.get("/stats")
def get_stats(request: Request):
    store = request.app.state.store
    total = store.stats.deploy_success + store.stats.deploy_fail
    return {
        **asdict(store.stats),
        "success_rate": store.stats.deploy_success / total if total else None,
        "nodes_online": sum(1 for n in store.nodes.values() if n.online),
        "nodes_total": len(store.nodes),
    }
