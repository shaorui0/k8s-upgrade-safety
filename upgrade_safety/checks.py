"""Observed state (snapshot contract) and the fixed `check` criteria.

`snapshot()` is the read side of the execution plane: it flattens a cluster into
the shape `contracts/snapshot.schema.json` describes. Everything the control
plane decides, it decides from this shape and nothing else.

The criteria are constants, not judgement: the threshold for raft lag is 1000
and a follower beyond it fails the gate even though quorum may exist on paper.
"""
from . import model
from .evidence import now

RAFT_LAG_LIMIT = 1000
COLLECTOR_VERSION = "sim-1"


def snapshot(c, role="baseline", target="", target_ami=None):
    """A snapshot-contract dict of one (simulated) cluster."""
    lags = model.raft_lag(c["etcd"])
    members = c["etcd"]["members"]
    wl = c["workload"]
    asg = c["workers"]["asg"]
    lt = asg["launch_template"]
    return {
        "meta": {
            "cluster": c["name"], "stage": c["stage"], "cluster_type": c["cluster_type"],
            "captured_at": now(), "role": role, "collector_version": COLLECTOR_VERSION,
            "target_version": target, "target_ami": target_ami,
        },
        "flags": dict(c["flags"]),
        "masters": [{k: m[k] for k in ("name", "apiserver", "controller_manager", "scheduler", "kubelet",
                                      "ready", "readyz", "lb_member")} for m in c["masters"]],
        "etcd": {
            "count": len(members), "online": sum(1 for m in members if m["online"]),
            "max_lag": max(lags.values()), "leaders": list(c["etcd"]["leaders"]),
            "members": [{"name": m["name"], "online": m["online"], "raft_index": m["raft_index"],
                         "lag": lags[m["name"]]} for m in members],
        },
        "workers": {
            "asg": {"name": asg["name"], "ami": asg["ami"]},
            "launch_template": {"id": lt["id"], "version": lt["version"], "ami": lt["ami"],
                                "pending": dict(lt.get("pending", {}))},
            "nodes": [{"name": n["name"], "ami": n["ami"], "kubelet": n["kubelet"], "ready": n["ready"],
                       "db": n.get("db"), "eviction_s": n["eviction_s"]} for n in c["workers"]["nodes"]],
        },
        "pdbs": [{k: p[k] for k in ("name", "workload", "nodes", "min_available", "current_healthy")}
                 for p in c["pdbs"]],
        "addons": {k: {"version": v["version"], "healthy": v["healthy"]} for k, v in c["addons"].items()},
        "kube_system": {"pods_total": c["kube_system"]["pods_total"], "pods_running": c["kube_system"]["pods_running"]},
        "workload": {
            "pods_total": wl["pods_total"], "pods_running": wl["pods_running"],
            "running_ratio": round(wl["pods_running"] / wl["pods_total"], 4) if wl["pods_total"] else 1.0,
            "unreachable": [s["name"] for s in wl["critical_services"] if not s["reachable"]],
        },
        "alerts": list(c["external"]["alerts"]),
        "monitor": dict(c["monitor"]),
        "backups": {"etcd_snapshot": c.get("backups", {}).get("etcd_snapshot")},
    }


def node_summary(snap):
    """Masters and workers together: total, ready, names not ready."""
    nodes = [(m["name"], m["ready"]) for m in snap["masters"]] + [(n["name"], n["ready"]) for n in snap["workers"]["nodes"]]
    not_ready = [n for n, ok in nodes if not ok]
    return {"total": len(nodes), "ready": len(nodes) - len(not_ready), "not_ready": not_ready}


def evaluate(snap):
    """Apply the fixed criteria. Returns a list of {id, ok, detail}."""
    e, ks = snap["etcd"], snap["kube_system"]
    n = node_summary(snap)
    lags = {m["name"]: m["lag"] for m in e["members"]}
    worst = max(lags, key=lags.get)
    unhealthy = sorted(k for k, a in snap["addons"].items() if not a["healthy"])
    mon = snap["monitor"]
    cross = (mon["nodes_ready"] == n["ready"] and mon["etcd_members_up"] == e["online"])
    return [
        _c("etcd_odd_members", e["count"] % 2 == 1, f"{e['count']} members"),
        _c("etcd_all_online", e["online"] == e["count"], f"{e['online']}/{e['count']} online"),
        _c("etcd_raft_lag", e["max_lag"] <= RAFT_LAG_LIMIT,
           f"worst follower {worst} is {e['max_lag']} entries behind (limit {RAFT_LAG_LIMIT})"),
        _c("etcd_single_leader", len(e["leaders"]) == 1, f"leaders: {', '.join(e['leaders']) or 'none'}"),
        _c("nodes_ready", not n["not_ready"],
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


def _c(cid, ok, detail):
    return {"id": cid, "ok": bool(ok), "detail": detail}


def failures(results):
    return [r for r in results if not r["ok"]]
