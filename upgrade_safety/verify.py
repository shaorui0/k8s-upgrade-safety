"""`verify`: version x health, diff against the baseline file, rollback advice."""
from . import checks

ALERT_FLOOD = 5            # new alerts versus baseline
PODS_NOT_RUNNING_LIMIT = 0.5

ROLLBACK_ACTIONS = {
    "control_plane": ["restore the etcd snapshot taken in this run (data)",
                      "downgrade the control-plane binaries on the touched masters (the snapshot does not restore binaries)"],
    "workers": ["stop the ASG instance refresh",
                "revert the Launch Template to the previous AMI (instances already replaced stay until a human decides)"],
    "addons": ["kubectl rollout undo for the failed addon"],
}


def version_state(snap, target, target_ami):
    """'target' only if every component reports the target version; 'old' if none do; else 'mixed'."""
    v = snap["versions"]
    seen = []
    for m in v["masters"]:
        seen += [m["apiserver"], m["controller_manager"], m["scheduler"], m["kubelet"]]
    seen += v["worker_kubelets"] + list(v["addons"].values())
    seen += [target if a == target_ami else "old-ami" for a in v["worker_amis"] + [v["asg_ami"]]]
    if all(x == target for x in seen):
        return "target"
    if all(x != target for x in seen):
        return "old"
    return "mixed"


def quadrant(version, healthy):
    """target+healthy -> proceed; old/mixed+healthy -> rerun; anything unhealthy -> human."""
    v = "target" if version == "target" else "old"
    if not healthy:
        decision = "human"
    elif v == "target":
        decision = "proceed"
    else:
        decision = "rerun"
    return {"version": v, "healthy": bool(healthy), "decision": decision}


def diff_snapshots(pre, post):
    """What changed since the baseline, and which changes are regressions."""
    changed, regressions = [], []
    pm = {m["name"]: m for m in pre["versions"]["masters"]}
    for m in post["versions"]["masters"]:
        for comp in ("apiserver", "controller_manager", "scheduler", "kubelet"):
            if pm[m["name"]][comp] != m[comp]:
                changed.append(f"{m['name']}.{comp}: {pm[m['name']][comp]} -> {m[comp]}")
    for key in ("worker_kubelets", "worker_amis", "asg_ami"):
        if pre["versions"][key] != post["versions"][key]:
            changed.append(f"workers.{key}: {pre['versions'][key]} -> {post['versions'][key]}")
    for a, ver in post["versions"]["addons"].items():
        if pre["versions"]["addons"][a] != ver:
            changed.append(f"addon.{a}: {pre['versions']['addons'][a]} -> {ver}")
    new_alerts = sorted(set(post["alerts"]) - set(pre["alerts"]))
    if new_alerts:
        regressions.append(f"new alerts since baseline: {', '.join(new_alerts)}")
    if post["nodes"]["ready"] < pre["nodes"]["ready"]:
        regressions.append(f"Ready nodes {pre['nodes']['ready']} -> {post['nodes']['ready']}")
    if post["workload"]["pods_running"] < pre["workload"]["pods_running"]:
        regressions.append(f"Running pods {pre['workload']['pods_running']} -> {post['workload']['pods_running']}")
    if post["etcd"]["online"] < pre["etcd"]["online"]:
        regressions.append(f"etcd members online {pre['etcd']['online']} -> {post['etcd']['online']}")
    if post["workload"]["unreachable"]:
        regressions.append(f"critical services unreachable: {', '.join(post['workload']['unreachable'])}")
    return {"changed": changed, "regressions": regressions}


def verify_cluster(post_snap, baseline_snap, target, target_ami):
    """The full verdict: criteria + baseline diff + quadrant."""
    results = checks.evaluate(post_snap)
    diff = diff_snapshots(baseline_snap, post_snap)
    healthy = not checks.failures(results) and not diff["regressions"]
    vs = version_state(post_snap, target, target_ami)
    q = quadrant(vs, healthy)
    return {"version_state": vs, "criteria": results, "diff": diff, "quadrant": q,
            "failed_criteria": [r["id"] for r in checks.failures(results)]}


def rollback_triggers(snap, baseline, failed_layer):
    """Triggers declared before execution; any one fires the advice."""
    fired = []
    if failed_layer == "control_plane":
        fired.append("master_upgrade_failed")
    if snap["workload"]["running_ratio"] < PODS_NOT_RUNNING_LIMIT:
        fired.append("pods_not_running_over_50pct")
    if snap["workload"]["unreachable"]:
        fired.append("critical_service_unreachable")
    if len(set(snap["alerts"]) - set(baseline["alerts"])) >= ALERT_FLOOD:
        fired.append("alert_flood")
    return fired


def rollback_advice(layer, failed_step, reason, snap, baseline):
    fired = rollback_triggers(snap, baseline, layer)
    return {
        "failed_step": failed_step, "layer": layer, "reason": reason, "fired_triggers": fired,
        "recommended": bool(fired),
        "actions": (ROLLBACK_ACTIONS if layer == "verify" else ROLLBACK_ACTIONS.get(layer, [])) if fired else [],
        "note": ("Declared trigger(s) fired: a human decides and executes; the system never rolls back on its own."
                 if fired else
                 "No declared rollback trigger fired. The cluster is in a known state; fix the cause and resume. "
                 "Actions if a human still chooses to roll back: "
                 + "; ".join(ROLLBACK_ACTIONS.get(layer, sum(ROLLBACK_ACTIONS.values(), [])))),
    }
