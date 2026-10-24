"""Health snapshot and the fixed `check` criteria.

The criteria are constants, not judgement: the threshold for raft lag is 1000
and a follower beyond it fails the gate even though quorum may exist on paper.
"""
from . import model

RAFT_LAG_LIMIT = 1000


def snapshot(c):
    """A JSON-able health and version snapshot of one (simulated) cluster."""
    masters = [{k: m[k] for k in ("name", "apiserver", "controller_manager", "scheduler", "kubelet",
                                  "ready", "readyz", "lb_member")} for m in c["masters"]]
    nodes = c["workers"]["nodes"]
    members = c["etcd"]["members"]
    lags = model.raft_lag(c["etcd"])
    ready = [m["name"] for m in c["masters"] if m["ready"]] + [n["name"] for n in nodes if n["ready"]]
    not_ready = [m["name"] for m in c["masters"] if not m["ready"]] + [n["name"] for n in nodes if not n["ready"]]
    wl = c["workload"]
    return {
        "cluster": c["name"], "stage": c["stage"], "cluster_type": c["cluster_type"],
        "flags": dict(c["flags"]),
        "versions": {
            "masters": masters,
            "worker_kubelets": sorted({n["kubelet"] for n in nodes}),
            "worker_amis": sorted({n["ami"] for n in nodes}),
            "asg_ami": c["workers"]["asg"]["ami"],
            "addons": {k: v["version"] for k, v in c["addons"].items()},
        },
        "etcd": {
            "members": len(members), "online": sum(1 for m in members if m["online"]),
            "lags": lags, "max_lag": max(lags.values()), "leaders": list(c["etcd"]["leaders"]),
        },
        "nodes": {"total": len(ready) + len(not_ready), "ready": len(ready), "not_ready": not_ready},
        "kube_system": {
            "pods_total": c["kube_system"]["pods_total"], "pods_running": c["kube_system"]["pods_running"],
            "addons_healthy": {k: v["healthy"] for k, v in c["addons"].items()},
        },
        "workload": {
            "pods_total": wl["pods_total"], "pods_running": wl["pods_running"],
            "running_ratio": round(wl["pods_running"] / wl["pods_total"], 4) if wl["pods_total"] else 1.0,
            "unreachable": [s["name"] for s in wl["critical_services"] if not s["reachable"]],
        },
        "alerts": list(c["external"]["alerts"]),
        "monitor": dict(c["monitor"]),
    }


def evaluate(snap):
    """Apply the fixed criteria. Returns a list of {id, ok, detail}."""
    e, n, ks = snap["etcd"], snap["nodes"], snap["kube_system"]
    worst = max(e["lags"], key=e["lags"].get)
    unhealthy = sorted(k for k, ok in ks["addons_healthy"].items() if not ok)
    mon = snap["monitor"]
    cross = (mon["nodes_ready"] == n["ready"] and mon["etcd_members_up"] == e["online"])
    out = [
        _c("etcd_odd_members", e["members"] % 2 == 1, f"{e['members']} members"),
        _c("etcd_all_online", e["online"] == e["members"], f"{e['online']}/{e['members']} online"),
        _c("etcd_raft_lag", e["max_lag"] <= RAFT_LAG_LIMIT,
           f"worst follower {worst} is {e['max_lag']} entries behind (limit {RAFT_LAG_LIMIT})"),
        _c("etcd_single_leader", len(e["leaders"]) == 1, f"leaders: {', '.join(e['leaders']) or 'none'}"),
        _c("nodes_ready", not n["not_ready"] and n["ready"] == n["total"],
           f"{n['ready']}/{n['total']} Ready" + (f"; not ready: {', '.join(n['not_ready'])}" if n["not_ready"] else "")),
        _c("kube_system_healthy", ks["pods_running"] == ks["pods_total"] and not unhealthy,
           f"{ks['pods_running']}/{ks['pods_total']} pods Running"
           + (f"; unhealthy addons: {', '.join(unhealthy)}" if unhealthy else "")),
        _c("external_alerts_zero", not snap["alerts"],
           f"{len(snap['alerts'])} active" + (f": {', '.join(snap['alerts'])}" if snap["alerts"] else "")),
        _c("monitor_cross_check", cross,
           f"own view nodes_ready={n['ready']} etcd_online={e['online']}; monitor view "
           f"nodes_ready={mon['nodes_ready']} etcd_up={mon['etcd_members_up']}"
           + ("" if cross else " (disagree: the baseline itself may be wrong)")),
    ]
    return out


def _c(cid, ok, detail):
    return {"id": cid, "ok": bool(ok), "detail": detail}


def failures(results):
    return [r for r in results if not r["ok"]]
