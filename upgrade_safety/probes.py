"""Probes: named, read-only questions asked of snapshots.

An assertion in a step is `{probe, args, op, expected}`. The engine evaluates it
against the snapshot(s) it holds; it never reaches into the cluster. Unary
probes take one snapshot. Baseline-relative probes (name ends `_delta` or
`_new_count`) take (baseline, after): they assert "no NEW breakage", not
"everything is healthy".

`expected` may be a literal or `$target` / `$target_ami`, resolved from the
snapshot's own meta so a snapshot is self-describing about what it is judged against.
"""
import operator

from . import model

RAFT_LAG_LIMIT = 1000     # same constant as checks.py; duplicated on purpose to keep probes import-light
OPS = {"==": operator.eq, "!=": operator.ne, "<": operator.lt, "<=": operator.le, ">": operator.gt, ">=": operator.ge}
COMPONENTS = ("apiserver", "controller_manager", "scheduler", "kubelet")
ADDON_KEY = {"ccm": "ccm", "cni": "cni", "ca": "cluster_autoscaler"}

UNARY, DIFF = {}, {}


def unary(name):
    def reg(fn):
        UNARY[name] = fn
        return fn
    return reg


def diff(name):
    def reg(fn):
        DIFF[name] = fn
        return fn
    return reg


def _master(s, name):
    return next(m for m in s["masters"] if m["name"] == name)


def _nodes(s, names):
    wanted = set(names)
    return [n for n in s["workers"]["nodes"] if n["name"] in wanted]


def blocking_pdbs(s, node):
    """PDBs covering `node` that allow zero (or fewer) disruptions."""
    return [p for p in s["pdbs"] if node in p["nodes"] and p["current_healthy"] - p["min_available"] <= 0]


# ---- etcd -----------------------------------------------------------------
@unary("etcd.max_raft_lag")
def _(s, a):
    return s["etcd"]["max_lag"], ""


@unary("etcd.members_online_all")
def _(s, a):
    e = s["etcd"]
    return e["online"] == e["count"], f"{e['online']}/{e['count']} online"


@unary("etcd.leader_count")
def _(s, a):
    return len(s["etcd"]["leaders"]), ", ".join(s["etcd"]["leaders"])


@unary("etcd.quorum_survives_taking")
def _(s, a):
    e = s["etcd"]
    others = sum(1 for m in e["members"] if m["online"] and m["name"] != a["master"])
    need = e["count"] // 2 + 1
    return others >= need, f"only {others} other etcd members online, quorum needs {need}"


@unary("etcd.member_online")
def _(s, a):
    m = next(m for m in s["etcd"]["members"] if m["name"] == a["master"])
    return m["online"], f"{a['master']} etcd member {'is' if m['online'] else 'is NOT'} online"


@unary("etcd.member_lag")
def _(s, a):
    return next(m["lag"] for m in s["etcd"]["members"] if m["name"] == a["master"]), ""


@unary("backup.etcd_snapshot_fresh")
def _(s, a):
    b = s["backups"]["etcd_snapshot"]
    if b is None:
        return False, "no etcd snapshot has been taken in this run"
    top = max(m["raft_index"] for m in s["etcd"]["members"])
    behind = top - b["max_raft_index"]
    return behind <= RAFT_LAG_LIMIT, f"snapshot {b['id']} is {behind} raft entries behind the live cluster"


# ---- masters --------------------------------------------------------------
@unary("master.component_version")
def _(s, a):
    return _master(s, a["master"])[a["component"]], ""


@unary("master.readyz")
def _(s, a):
    ok = _master(s, a["master"])["readyz"]
    return ok, f"{a['master']}: apiserver /readyz {'ok' if ok else 'failed'}"


@unary("master.lb_healthy")
def _(s, a):
    st = _master(s, a["master"])["lb_member"]
    return st == "healthy", f"{a['master']}: apiserver load-balancer membership is {st}"


@unary("master.ready")
def _(s, a):
    return _master(s, a["master"])["ready"], ""


@unary("master.apiserver_gate_passed")
def _(s, a):
    m = _master(s, a["master"])
    t = s["meta"]["target_version"]
    ok = m["apiserver"] == t and m["readyz"] and m["lb_member"] == "healthy"
    return ok, f"{a['master']}: apiserver {m['apiserver']}, /readyz {m['readyz']}, load-balancer {m['lb_member']}"


@unary("master.all_components_at_target")
def _(s, a):
    m = _master(s, a["master"])
    t = s["meta"]["target_version"]
    off = sorted(k for k in COMPONENTS if m[k] != t)
    return not off, f"not at {t}: {', '.join(off)}" if off else ""


@unary("master.kubelet_skew_ok")
def _(s, a):
    m = _master(s, a["master"])
    t = s["meta"]["target_version"]
    return model.skew_ok(t, "kubelet", m["kubelet"]), f"kubelet {m['kubelet']} against apiserver {t}"


@unary("masters.all_at_target")
def _(s, a):
    t = s["meta"]["target_version"]
    off = sorted(f"{m['name']}.{k}" for m in s["masters"] for k in COMPONENTS if m[k] != t)
    return not off, f"not at {t}: {', '.join(off[:4])}" if off else ""


# ---- workers --------------------------------------------------------------
@unary("lt.ami")
def _(s, a):
    return s["workers"]["launch_template"]["ami"], ""


@unary("asg.ami")
def _(s, a):
    return s["workers"]["asg"]["ami"], ""


@unary("lt.pending_non_ami_count")
def _(s, a):
    extra = sorted(k for k in s["workers"]["launch_template"]["pending"] if k != "ami")
    return len(extra), f"queued: {', '.join(extra)}" if extra else ""


@unary("workers.on_target_ami")
def _(s, a):
    t, ami = s["meta"]["target_version"], s["meta"]["target_ami"]
    off = [n["name"] for n in _nodes(s, a["nodes"]) if n["ami"] != ami or n["kubelet"] != t]
    return not off, f"not yet replaced: {', '.join(off)}" if off else ""


@unary("workers.nodes_ready")
def _(s, a):
    off = [n["name"] for n in _nodes(s, a["nodes"]) if not n["ready"]]
    return not off, f"not Ready: {', '.join(off)}" if off else ""


@unary("workers.all_on_target")
def _(s, a):
    t, ami = s["meta"]["target_version"], s["meta"]["target_ami"]
    off = [n["name"] for n in s["workers"]["nodes"] if n["ami"] != ami or n["kubelet"] != t or not n["ready"]]
    return not off, f"not on target AMI / kubelet / Ready: {', '.join(off)}" if off else ""


@unary("workers.drain_blockers")
def _(s, a):
    msgs = [f"drain of {n['name']} blocked by PDB {p['name']} (allows 0 disruptions); never forced: "
            f"a human must wait for the PDB or lower minAvailable explicitly"
            for n in _nodes(s, a["nodes"]) for p in blocking_pdbs(s, n["name"])]
    return len(msgs), "; ".join(msgs)


@unary("workers.slow_evictions")
def _(s, a):
    timeout = s["flags"].get("drain_timeout_s", 300)
    msgs = [f"eviction of {n['name']} takes {n['eviction_s']}s but the drain timeout is {timeout}s; never forced: "
            f"this cluster needs the per-cluster flag drain_timeout_s: 600 (a human decision)"
            for n in _nodes(s, a["nodes"]) if n["eviction_s"] > timeout]
    return len(msgs), "; ".join(msgs)


# ---- addons ---------------------------------------------------------------
@unary("addon.healthy")
def _(s, a):
    ok = s["addons"][ADDON_KEY[a["addon"]]]["healthy"]
    return ok, f"{a['addon']} is {'healthy' if ok else 'UNHEALTHY'}"


@unary("addon.version")
def _(s, a):
    return s["addons"][ADDON_KEY[a["addon"]]]["version"], ""


@unary("addon.at_target")
def _(s, a):
    ad = s["addons"][ADDON_KEY[a["addon"]]]
    return ad["version"] == s["meta"]["target_version"], f"{a['addon']} is at {ad['version']}"


# ---- baseline-relative ------------------------------------------------------
def _ready(s):
    return sum(1 for m in s["masters"] if m["ready"]) + sum(1 for n in s["workers"]["nodes"] if n["ready"])


@diff("pods.running_delta")
def _(b, s, a):
    d = s["workload"]["pods_running"] - b["workload"]["pods_running"]
    return d, f"Running pods {b['workload']['pods_running']} -> {s['workload']['pods_running']}"


@diff("nodes.ready_delta")
def _(b, s, a):
    d = _ready(s) - _ready(b)
    return d, f"Ready nodes {_ready(b)} -> {_ready(s)}"


@diff("alerts.new_count")
def _(b, s, a):
    new = sorted(set(s["alerts"]) - set(b["alerts"]))
    return len(new), ", ".join(new)


@diff("services.new_unreachable_count")
def _(b, s, a):
    new = sorted(set(s["workload"]["unreachable"]) - set(b["workload"]["unreachable"]))
    return len(new), ", ".join(new)


# ---- named assertions (referenced by id, e.g. backup_precondition) ---------
NAMED = {
    "etcd-snapshot-fresh": {
        "id": "etcd-snapshot-fresh", "probe": "backup.etcd_snapshot_fresh", "op": "==", "expected": True,
        "severity": "block", "why": "an irreversible control-plane step needs a restorable etcd snapshot"},
}


def evaluate(assertion, baseline, after, phase):
    """Evaluate one assertion. Returns an evidence-shaped result plus `why`."""
    name = assertion["probe"]
    args = assertion.get("args", {})
    if name in UNARY:
        measured, detail = UNARY[name](after, args)
    elif name in DIFF:
        measured, detail = DIFF[name](baseline, after, args)
    else:
        raise KeyError(f"unknown probe {name!r}; registered: {', '.join(sorted(list(UNARY) + list(DIFF)))}")
    expected = assertion["expected"]
    if expected == "$target":
        expected = after["meta"]["target_version"]
    elif expected == "$target_ami":
        expected = after["meta"]["target_ami"]
    passed = bool(OPS[assertion["op"]](measured, expected))
    return {"id": assertion["id"], "phase": phase, "probe": name, "measured": measured, "expected": expected,
            "op": assertion["op"], "passed": passed, "severity": assertion["severity"], "detail": detail,
            "why": assertion["why"]}


def explain(result):
    """One sentence for a failed assertion: the rule, then what was measured."""
    return f"{result['why']}" + (f" ({result['detail']})" if result["detail"] else
                                 f" (measured {result['measured']!r} {result['op']} {result['expected']!r})")
