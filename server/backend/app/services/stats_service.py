from ..store import Store


def summary(store: Store) -> dict:
    deployments = store.state.deployments.values()
    targets = [t for d in deployments for t in d.targets]
    success = [t for t in targets if t.status == "success"]
    nodes = store.state.nodes.values()
    return {
        "deployments_total": len(store.state.deployments),
        "targets_total": len(targets),
        "targets_success": len(success),
        "success_rate": (len(success) / len(targets)) if targets else 1.0,
        "paper_saved": len(success),  # 성공 갱신 1회 = 종이 1장 대체 (스펙 §5.4)
        "nodes_online": sum(1 for n in nodes if n.status == "online"),
        "nodes_total": len(store.state.nodes),
    }
