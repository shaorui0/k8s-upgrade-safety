"""`plan`: a dry-run that can fail. Pure functions over a cluster dict."""
import math

from . import model

SERIAL = 1            # masters changed at a time
BATCH_PERCENT = 20    # ASG instance refresh batch size
ADDON_ORDER = ["ccm", "cni", "cluster_autoscaler"]


def make_batches(c, percent=BATCH_PERCENT):
    """Worker batches: stateful nodes first, each alone; the rest in `percent` chunks.

    Batches never exceed `percent` of the group (rounded up, at least one node).
    """
    nodes = sorted(c["workers"]["nodes"], key=lambda n: n["name"])
    db = [n["name"] for n in nodes if n.get("db")]
    rest = [n["name"] for n in nodes if not n.get("db")]
    size = max(1, math.ceil(len(nodes) * percent / 100))
    batches = [[x] for x in db]
    batches += [rest[i:i + size] for i in range(0, len(rest), size)]
    return batches


def blocking_pdbs(c, node_name):
    """PDBs covering `node_name` that allow zero (or fewer) disruptions."""
    return [p for p in c["pdbs"]
            if node_name in p["nodes"] and p["current_healthy"] - p["min_available"] <= 0]


def build_plan(fleet, c, target):
    src = c["version"]
    violations, warnings = [], []
    if model.minor(target) != model.minor(src) + 1:
        violations.append(f"hop {src} -> {target} is not exactly one minor: kubeadm upgrades one minor at a time")

    # control plane
    steps = []
    for m in c["masters"]:
        for comp in ("apiserver", "controller_manager", "scheduler", "kubelet"):
            steps.append({"master": m["name"], "component": comp, "from": m[comp], "to": target})
        if not model.skew_ok(target, "kubelet", m["kubelet"]):
            violations.append(f"{m['name']}: kubelet {m['kubelet']} would violate skew against apiserver {target}")
        for comp in ("controller_manager", "scheduler"):
            if not model.skew_ok(target, comp, m[comp]):
                violations.append(f"{m['name']}: {comp} {m[comp]} would violate skew against apiserver {target}")

    # workers: AMI diff and Launch Template diff
    asg = c["workers"]["asg"]
    lt = asg["launch_template"]
    new_ami = model.target_ami(fleet, target)
    ami_diff = {"from": asg["ami"], "to": new_ami,
                "target_kubelet": fleet.amis[new_ami]["kubelet"] if new_ami else None}
    if not new_ami:
        violations.append(f"no AMI with kubelet {target}")
    elif fleet.amis[new_ami]["kubelet"] != target:
        violations.append(f"AMI {new_ami} kubelet {fleet.amis[new_ami]['kubelet']} != target {target}")
    proposed = dict(lt)
    proposed.update(lt.get("pending", {}))          # anything else queued on the template
    proposed.pop("pending", None)
    proposed["ami"] = new_ami
    base = {k: v for k, v in lt.items() if k != "pending"}
    changed = {k: [base.get(k), proposed.get(k)] for k in sorted(set(base) | set(proposed))
               if base.get(k) != proposed.get(k)}
    for k in changed:
        if k != "ami":
            violations.append(f"launch template change {k!r} is not allowed: only the AMI may change")
    lt_diff = {"changed": changed, "only_ami": set(changed) <= {"ami"}}

    # blast radius by quorum math
    members = len(c["etcd"]["members"])
    tolerated = model.quorum_tolerance(members)
    batches = make_batches(c)
    blast = {
        "etcd_members": members, "tolerated_unavailable": tolerated, "serial": SERIAL,
        "worst_case_masters_down": min(SERIAL, len(c["masters"])),
        "within_quorum": SERIAL <= tolerated,
        "worker_batch_percent": BATCH_PERCENT,
        "worst_case_worker_batch": max((len(b) for b in batches), default=0),
    }
    if not blast["within_quorum"]:
        violations.append(f"serial={SERIAL} exceeds quorum tolerance {tolerated} of {members} members")

    # things the human should see before approving (they stop the apply, they do not fail the plan)
    timeout = c["flags"].get("drain_timeout_s", 300)
    for n in c["workers"]["nodes"]:
        if n["eviction_s"] > timeout:
            warnings.append(f"{n['name']}: eviction takes {n['eviction_s']}s > drain_timeout_s {timeout}s "
                            f"(needs a per-cluster flag, a human decision)")
        for p in blocking_pdbs(c, n["name"]):
            warnings.append(f"{n['name']}: PDB {p['name']} allows 0 disruptions (drain will block; never forced)")

    return {
        "cluster": c["name"], "stage": c["stage"], "cluster_type": c["cluster_type"],
        "from": src, "to": target, "flags": dict(c["flags"]),
        "control_plane": {"order_per_master": ["gate", "apiserver", "apiserver_ready", "controller_manager",
                                               "scheduler", "kubelet", "verify"],
                          "masters": [m["name"] for m in c["masters"]], "kubeadm_plan": steps},
        "workers": {"ami_diff": ami_diff, "launch_template_diff": lt_diff, "batches": batches,
                    "drain_timeout_s": timeout},
        "addons": [{"name": a, "from": c["addons"][a]["version"], "to": target} for a in ADDON_ORDER],
        "blast_radius": blast,
        "violations": violations, "warnings": warnings,
    }


def render(plan):
    """Human-readable plan: what apply would do. Printed at the approval gate."""
    b, w = plan["blast_radius"], plan["workers"]
    lines = [
        f"PLAN {plan['cluster']} ({plan['stage']}, {plan['cluster_type']}): {plan['from']} -> {plan['to']}",
        f"  blast radius: {b['etcd_members']} etcd members tolerate {b['tolerated_unavailable']}; "
        f"serial={b['serial']} => worst case {b['worst_case_masters_down']} master down "
        f"({'within' if b['within_quorum'] else 'EXCEEDS'} quorum)",
        "  control plane, per master (each master needs its own sign-off):",
        "    " + " -> ".join(plan["control_plane"]["order_per_master"]),
        "    masters in order: " + ", ".join(plan["control_plane"]["masters"]),
        f"  workers: AMI {w['ami_diff']['from']} -> {w['ami_diff']['to']} "
        f"(kubelet {w['ami_diff']['target_kubelet']}); launch template changes: "
        f"{', '.join(w['launch_template_diff']['changed']) or 'none'}",
        f"    batches (stateful nodes first, alone): "
        + " | ".join(",".join(x) for x in w["batches"]) + f"; drain timeout {w['drain_timeout_s']}s, never forced",
        "  addons in order: " + " -> ".join(a["name"] for a in plan["addons"]),
    ]
    for v in plan["violations"]:
        lines.append(f"  VIOLATION: {v}")
    for x in plan["warnings"]:
        lines.append(f"  WARNING: {x}")
    return "\n".join(lines) + "\n"
