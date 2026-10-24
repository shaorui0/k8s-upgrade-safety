"""`plan`: desired state compared with an observed snapshot, as a diff artifact.

Level-triggered: nothing here remembers what was done before. It takes the
desired state (target minor, target AMI) and an observed snapshot, and lists
what differs. Changes nothing. The result conforms to `contracts/diff.schema.json`.
"""
import math

from . import model
from .evidence import now
from .probes import blocking_pdbs

SERIAL = 1            # masters changed at a time
BATCH_PERCENT = 20    # worker batch size cap
COMPONENTS = ("apiserver", "controller_manager", "scheduler", "kubelet")
ADDONS = [("ccm", "ccm"), ("cni", "cni"), ("ca", "cluster_autoscaler")]


def make_batches(nodes, percent=BATCH_PERCENT):
    """Stateful nodes first, each alone; the rest in `percent` chunks (at least one node, rounded up)."""
    nodes = sorted(nodes, key=lambda n: n["name"])
    db = [n["name"] for n in nodes if n.get("db")]
    rest = [n["name"] for n in nodes if not n.get("db")]
    size = max(1, math.ceil(len(nodes) * percent / 100))
    return [[x] for x in db] + [rest[i:i + size] for i in range(0, len(rest), size)]


def worker_tiers(nodes):
    """Blast-radius tiers, orthogonal to layers: canary (one node), the first batch, then rollout batches."""
    batches = make_batches(nodes)
    if not batches:
        return []
    first = batches[0]
    tiers = [{"phase": "canary", "nodes": [first[0]]}]
    rest = ([first[1:]] if first[1:] else []) + batches[1:]
    for i, b in enumerate(rest):
        tiers.append({"phase": "batch" if i == 0 else "rollout", "nodes": b})
    return tiers


def build_diff(fleet, snap, target, snapshot_ref="snapshots/baseline.json"):
    src = max((m["apiserver"] for m in snap["masters"]), key=model.minor)
    blockers, warnings, changes = [], [], []
    if model.minor(target) != model.minor(src) + 1:
        blockers.append(f"hop {src} -> {target} is not exactly one minor: kubeadm upgrades one minor at a time")

    # control plane: every component of every master (in-place, irreversible)
    lagging = []
    for m in snap["masters"]:
        for comp in COMPONENTS:
            if m[comp] != target:
                changes.append({"target": f"master/{m['name']}/{comp}", "field": "component_version",
                                "before": m[comp], "after": target, "reversible": False,
                                "note": "in-place kubeadm/kubelet upgrade; undo needs snapshot restore + binary downgrade"})
        if not model.skew_ok(target, "kubelet", m["kubelet"]):
            blockers.append(f"{m['name']}: kubelet {m['kubelet']} would violate skew against apiserver {target}")
        for comp in ("controller_manager", "scheduler"):
            if not model.skew_ok(target, comp, m[comp]):
                blockers.append(f"{m['name']}: {comp} {m[comp]} would violate skew against apiserver {target}")
        lagging += [f"{m['name']}.{c}" for c in COMPONENTS if m[c] != max((x[c] for x in snap["masters"]), key=model.minor)]

    # workers: AMI and Launch Template (re-pointing: reversible)
    asg, lt = snap["workers"]["asg"], snap["workers"]["launch_template"]
    new_ami = snap["meta"]["target_ami"]
    if not new_ami:
        blockers.append(f"no AMI with kubelet {target}")
    elif fleet.amis[new_ami]["kubelet"] != target:
        blockers.append(f"AMI {new_ami} kubelet {fleet.amis[new_ami]['kubelet']} != target {target}")
    if new_ami and lt["ami"] != new_ami:
        changes.append({"target": f"lt/{lt['id']}", "field": "ami_id", "before": lt["ami"], "after": new_ami,
                        "reversible": True, "note": "only the AMI changes; undo by re-pointing to the previous version"})
        changes.append({"target": f"lt/{lt['id']}", "field": "launch_template_version", "before": lt["version"],
                        "after": lt["version"] + 1, "reversible": True})
    if new_ami and asg["ami"] != new_ami:
        changes.append({"target": f"asg/{asg['name']}", "field": "ami_id", "before": asg["ami"], "after": new_ami,
                        "reversible": True})
    for k in sorted(lt["pending"]):
        if k != "ami":
            blockers.append(f"launch template change {k!r} is not allowed: only the AMI may change")

    # addons (rollout undo: reversible)
    for short, key in ADDONS:
        if snap["addons"][key]["version"] != target:
            changes.append({"target": f"addon/{short}", "field": "addon_version",
                            "before": snap["addons"][key]["version"], "after": target, "reversible": True,
                            "note": "undo with kubectl rollout undo"})

    # alignment: do the observed pointers agree with each other before we start?
    node_amis = sorted({n["ami"] for n in snap["workers"]["nodes"]})
    aligned_asg = asg["ami"] == lt["ami"] and node_amis == [lt["ami"]]
    per_asg = [{"asg": asg["name"], "asg_ami": asg["ami"], "launch_template_ami": lt["ami"], "node_amis": node_amis,
                "aligned": aligned_asg,
                "explanation": ("asg, launch template and every node agree" if aligned_asg else
                                f"asg={asg['ami']} lt={lt['ami']} nodes={node_amis}: drift, not a surprise")}]
    if not aligned_asg:
        warnings.append(f"{asg['name']}: AMI pointers disagree before the change ({per_asg[0]['explanation']})")
    cp_aligned = not lagging and len({m['apiserver'] for m in snap['masters']}) == 1

    # blast radius by quorum math, plus worker tiers
    members = snap["etcd"]["count"]
    tolerated = model.quorum_tolerance(members)
    tiers = worker_tiers(snap["workers"]["nodes"])
    within = SERIAL <= tolerated
    if not within:
        blockers.append(f"serial={SERIAL} exceeds quorum tolerance {tolerated} of {members} members")

    # things the human should see before approving (they stop the apply, they do not fail the plan)
    timeout = snap["flags"].get("drain_timeout_s", 300)
    for n in snap["workers"]["nodes"]:
        if n["eviction_s"] > timeout:
            warnings.append(f"{n['name']}: eviction takes {n['eviction_s']}s > drain_timeout_s {timeout}s "
                            f"(needs a per-cluster flag, a human decision)")
        for p in blocking_pdbs(snap, n["name"]):
            warnings.append(f"{n['name']}: PDB {p['name']} allows 0 disruptions (drain will block; never forced)")

    return {
        "meta": {"cluster": snap["meta"]["cluster"], "computed_at": now(), "from_version": src, "to_version": target,
                 "snapshot_ref": snapshot_ref},
        "desired": {"target_version": target, "target_ami": new_ami},
        "reversible": all(c["reversible"] for c in changes),
        "changes": changes,
        "alignment": {"aligned": aligned_asg and cp_aligned,
                      "control_plane": {"aligned": cp_aligned, "lagging": lagging}, "per_asg": per_asg},
        "blast_radius": {"etcd_members": members, "tolerated_unavailable": tolerated, "serial": SERIAL,
                         "worst_case_masters_down": min(SERIAL, len(snap["masters"])), "within_quorum": within,
                         "worker_tiers": tiers},
        "verdict": {"safe_to_apply": not blockers, "blockers": blockers, "warnings": warnings},
    }


def render(diff, snap):
    """Human-readable plan: what apply would do. Printed at the approval gate."""
    b, m = diff["blast_radius"], diff["meta"]
    lines = [
        f"PLAN {m['cluster']} ({snap['meta']['stage']}, {snap['meta']['cluster_type']}): {m['from_version']} -> {m['to_version']}",
        f"  desired vs observed: {len(diff['changes'])} change(s); diff is "
        f"{'reversible' if diff['reversible'] else 'IRREVERSIBLE (control plane in place): needs the etcd snapshot'}",
        f"  blast radius: {b['etcd_members']} etcd members tolerate {b['tolerated_unavailable']}; "
        f"serial={b['serial']} => worst case {b['worst_case_masters_down']} master down "
        f"({'within' if b['within_quorum'] else 'EXCEEDS'} quorum)",
        "  layers in order: master -> worker -> components (addons)",
        "  control plane, per master (each master needs its own sign-off):",
        "    apiserver -> apiserver_ready (/readyz + LB) -> controller_manager -> scheduler -> kubelet -> verify",
        "    masters in order: " + ", ".join(x["name"] for x in snap["masters"]),
        f"  workers: AMI {diff['alignment']['per_asg'][0]['asg_ami']} -> {diff['desired']['target_ami']}; "
        f"launch template changes: only the AMI",
        "    tiers (stateful nodes alone, never forced; drain timeout "
        f"{snap['flags'].get('drain_timeout_s', 300)}s): "
        + " | ".join(f"{t['phase']}: {','.join(t['nodes'])}" for t in b["worker_tiers"]),
        "  addons in order: ccm -> cni -> cluster_autoscaler",
    ]
    for v in diff["verdict"]["blockers"]:
        lines.append(f"  BLOCKER: {v}")
    for x in diff["verdict"]["warnings"]:
        lines.append(f"  WARNING: {x}")
    return "\n".join(lines) + "\n"
