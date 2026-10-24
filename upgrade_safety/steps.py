"""Step definitions: the upgrade as data, not as engine code.

Each step conforms to `contracts/step.schema.json`. The list is built once per
run from the baseline snapshot and the worker tiers, stored as `steps.json`, and
interpreted by `reconcile.run_step`. Layers are serial: master, then worker,
then components. Inside a layer, blast radius is tiered (a canary node first).
"""
from . import contracts

CP_COMPONENTS = ("apiserver", "controller_manager", "scheduler", "kubelet")
ADDON_ORDER = ["ccm", "cni", "ca"]
ADDON_NAME = {"ccm": "cloud-controller-manager", "cni": "CNI", "ca": "Cluster Autoscaler"}
LIMIT = 1000


def A(id, probe, op, expected, why, args=None, severity="block"):
    a = {"id": id, "probe": probe, "op": op, "expected": expected, "severity": severity, "why": why}
    if args:
        a["args"] = args
    return a


def _step(id, goal, layer, reversible, execute, precheck, postcheck, policy, *, signoff=False, backup=None,
          already_done=None, blast=None, on_fail="stop"):
    s = {"id": id, "goal": goal, "layer": layer, "reversible": reversible, "precheck": precheck,
         "execute": dict(execute, idempotent=True), "postcheck": postcheck,
         "gate": {"policy": policy, "signoff": signoff, "on_fail": on_fail}}
    if backup:
        s["backup_precondition"] = backup
    if already_done:
        s["already_done"] = already_done
    if blast:
        s["blast_radius"] = blast
    return s


def build_steps(snap, tiers, policy="manual"):
    """Ordered step definitions for one cluster. Validated against the step contract."""
    masters = [m["name"] for m in snap["masters"]]
    steps = []

    steps.append(_step(
        "snapshot", "take a restorable etcd snapshot before anything irreversible runs", "master", True,
        {"engine": "ansible", "action": "etcd-backup"},
        [A("etcd-quorum", "etcd.members_online_all", "==", True, "a snapshot is only meaningful from a healthy quorum")],
        [A("snapshot-fresh", "backup.etcd_snapshot_fresh", "==", True, "the snapshot must exist and be recent")],
        policy, already_done=A("snapshot-exists", "backup.etcd_snapshot_fresh", "==", True, "snapshot already taken")))

    for m in masters:
        a = {"master": m}
        pre = f"master:{m}"
        quorum = A("quorum-survives", "etcd.quorum_survives_taking", "==", True,
                   "taking this master must leave an etcd quorum", a)
        irrev = dict(backup="etcd-snapshot-fresh", blast={"unit": "node", "batch": 1})
        steps.append(_step(
            f"{pre}:apiserver", f"upgrade the apiserver on {m} (the version-skew anchor)", "master", False,
            {"engine": "ansible", "action": "master-upgrade", "args": {"master": m, "component": "apiserver"}},
            [quorum, A("kubelet-skew", "master.kubelet_skew_ok", "==", True,
                       "kubelet may trail the target apiserver by at most 2 minors", a)],
            [A("leader-unique", "etcd.leader_count", "==", 1, "leader transfer is expected, a missing or double leader is not")],
            policy, signoff=True,
            already_done=A("apiserver-done", "master.component_version", "==", "$target", "already at target",
                           {"master": m, "component": "apiserver"}), **irrev))
        steps.append(_step(
            f"{pre}:apiserver_ready", f"prove the apiserver on {m} serves before anything else on it moves", "master", True,
            {"engine": "ansible", "action": "wait-apiserver-ready", "args": {"master": m}}, [],
            [A("readyz", "master.readyz", "==", True,
               f"apiserver /readyz must pass before controller-manager, scheduler or kubelet on {m}, or any later master, is touched", a),
             A("lb-member", "master.lb_healthy", "==", True,
               "the apiserver must be a healthy load-balancer member: upgraded without membership means removed from service", a)],
            policy))
        for comp in ("controller_manager", "scheduler", "kubelet"):
            steps.append(_step(
                f"{pre}:{comp}", f"upgrade {comp.replace('_', '-')} on {m}", "master", False,
                {"engine": "ansible", "action": "master-upgrade", "args": {"master": m, "component": comp}},
                [A("apiserver-gate", "master.apiserver_gate_passed", "==", True,
                   f"refusing to upgrade {comp.replace('_', '-')} on {m}: the apiserver gate (/readyz + load-balancer) has not passed", a)],
                [], policy,
                already_done=A(f"{comp}-done", "master.component_version", "==", "$target", "already at target",
                               {"master": m, "component": comp}), **irrev))
        steps.append(_step(
            f"{pre}:verify", f"confirm {m} is a whole, healthy control-plane member again", "master", True,
            {"engine": "ansible", "action": "verify-member", "args": {"master": m}}, [],
            [A("member-online", "etcd.member_online", "==", True,
               "a member that does not come back is the real danger (leader transfer is not)", a),
             A("member-lag", "etcd.member_lag", "<=", LIMIT, f"raft lag must be back within {LIMIT}", a),
             A("node-ready", "master.ready", "==", True, "the control-plane node must be Ready", a),
             A("components", "master.all_components_at_target", "==", True, "all four components at the target version", a)],
            policy))

    # worker layer: terraform-style pointer change, then tiers (canary, batch, rollout)
    worker_pre = [
        A("control-plane-first", "masters.all_at_target", "==", True,
          "workers never lead the control plane: the control plane must be fully at target first")]
    steps.append(_step(
        "workers:launch_template", "point the launch template at the target AMI (AMI only)", "worker", True,
        {"engine": "terraform", "action": "terraform-lt"},
        worker_pre + [A("lt-ami-only", "lt.pending_non_ami_count", "==", 0, "only the AMI may change on the launch template")],
        [A("lt-ami", "lt.ami", "==", "$target_ami", "launch template now points at the target AMI"),
         A("asg-ami", "asg.ami", "==", "$target_ami", "ASG now points at the target AMI")],
        policy, signoff=True, already_done=A("lt-done", "lt.ami", "==", "$target_ami", "already pointing at target")))
    for i, t in enumerate(tiers):
        sid = "workers:canary" if t["phase"] == "canary" else f"workers:batch{i}"
        nodes = {"nodes": t["nodes"]}
        steps.append(_step(
            sid, f"replace {', '.join(t['nodes'])} ({t['phase']})", "worker", True,
            {"engine": "aws", "action": "asg-instance-refresh", "args": nodes},
            [A("ami-pointed", "asg.ami", "==", "$target_ami", "the launch template must be updated first"),
             A("no-pdb-block", "workers.drain_blockers", "==", 0, "a PDB allowing zero disruptions blocks the drain; never forced", nodes),
             A("eviction-in-time", "workers.slow_evictions", "==", 0, "eviction must finish inside the drain timeout; never forced", nodes)],
            [A("replaced", "workers.on_target_ami", "==", True, "the nodes run the target AMI and kubelet", nodes),
             A("ready", "workers.nodes_ready", "==", True, "replaced nodes join and become Ready", nodes),
             A("pods-not-fewer", "pods.running_delta", ">=", 0, "no fewer Running pods than the baseline"),
             A("nodes-not-fewer", "nodes.ready_delta", ">=", 0, "no fewer Ready nodes than the baseline")],
            policy, signoff=True,
            already_done=A("nodes-done", "workers.on_target_ami", "==", True, "nodes already replaced", nodes),
            blast={"unit": "node" if t["phase"] == "canary" else "batch", "phase": t["phase"],
                   "batch": 1 if t["phase"] == "canary" else "20%", "nodes": t["nodes"]}))
    steps.append(_step(
        "workers:verify", "every worker on the target AMI, kubelet and Ready", "worker", True,
        {"engine": "aws", "action": "verify-member"}, [],
        [A("all-workers", "workers.all_on_target", "==", True, "no worker left behind")], policy))

    # components layer: addons in dependency order, each requires the previous
    for i, short in enumerate(ADDON_ORDER):
        a = {"addon": short}
        pre = [A("addon-healthy", "addon.healthy", "==", True, f"{ADDON_NAME[short]} must be healthy before its upgrade", a)]
        if i:
            prev = ADDON_ORDER[i - 1]
            pre.append(A("order", "addon.at_target", "==", True,
                         f"addon {short} requires {prev} to be completed first (order: CCM -> CNI -> Cluster Autoscaler)",
                         {"addon": prev}))
        steps.append(_step(
            f"addon:{short}", f"upgrade {ADDON_NAME[short]} and verify it", "components", True,
            {"engine": "ansible", "action": "addon-rollout", "args": a}, pre,
            [A("at-target", "addon.at_target", "==", True, "addon at the target version", a),
             A("healthy", "addon.healthy", "==", True, "addon healthy after rollout (undo: kubectl rollout undo)", a)],
            policy, signoff=True, already_done=A("addon-done", "addon.at_target", "==", True, "already at target", a)))

    for s in steps:
        contracts.validate("step", s)
    return steps
