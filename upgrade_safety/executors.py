"""The execution plane: the only code that is allowed to act on a cluster.

The engine (control plane) interprets steps, evaluates probes over snapshots,
runs gates and writes evidence. It never touches a cluster itself. It asks an
`Executor` for two things:

  observe(role)   read-only: return a snapshot-contract dict
  execute(step)   perform ONE already-decided, idempotent action; return a result

An executor never decides what runs next, never retries, never skips a step.
Real adapters (Terraform for declarative infrastructure, Ansible for ordered
imperative actions such as kubeadm and drain, direct cloud API calls) belong
behind this interface. This repository ships only `SimulatedExecutor`; the other
names are registered so the seam is visible, and they refuse loudly.
"""
from . import checks

ADDON_KEY = {"ccm": "ccm", "cni": "cni", "ca": "cluster_autoscaler"}
COMPONENTS = ("apiserver", "controller_manager", "scheduler", "kubelet")


class Executor:
    name = "abstract"

    def observe(self, role):
        raise NotImplementedError

    def execute(self, step):
        raise NotImplementedError


class UnimplementedExecutor(Executor):
    """Placeholder for a real adapter. Fails on first use, never silently."""

    def __init__(self, name, world=None, target=None, target_ami=None):
        self.name = name

    def _fail(self):
        raise NotImplementedError(
            f"no {self.name} adapter: this repository ships only the simulated executor; "
            f"a real adapter implements Executor.observe and Executor.execute")

    def observe(self, role):
        self._fail()

    def execute(self, step):
        self._fail()


def _result(command, stdout="", exit_code=0, config_diff="", events=None, artifacts=None):
    return {"command": command, "stdout": stdout, "exit_code": exit_code, "config_diff": config_diff,
            "events": events or [], "artifacts": artifacts or {}}


class SimulatedExecutor(Executor):
    """Acts on an in-memory cluster dict. Planted faults are data fields on that dict."""
    name = "simulated"

    def __init__(self, world, target, target_ami):
        self.c, self.T, self.ami = world, target, target_ami

    def observe(self, role):
        return checks.snapshot(self.c, role=role, target=self.T, target_ami=self.ami)

    def execute(self, step):
        ex = step["execute"]
        args = ex.get("args", {})
        fn = getattr(self, "_" + ex["action"].replace("-", "_"))
        command = f"[simulated] {ex['engine']} {ex['action']} " + " ".join(f"{k}={v}" for k, v in sorted(args.items())
                                                                           if not isinstance(v, list))
        return fn(command.strip(), **args)

    # ---- actions ----------------------------------------------------------
    def _noop(self, command, **kw):
        return _result(command, "read-only wait, nothing mutated")

    _wait_apiserver_ready = _verify_member = _noop

    def _etcd_backup(self, command):
        e = self.c["etcd"]
        snap = {"id": f"snap-{self.c['name']}", "taken_at": checks.now(),
                "max_raft_index": max(m["raft_index"] for m in e["members"])}
        self.c.setdefault("backups", {})["etcd_snapshot"] = snap
        art = {"etcd-snapshot.json": {**snap, "cluster": self.c["name"], "members": [m["name"] for m in e["members"]],
                                      "leader": e["leaders"][0],
                                      "restore_hint": "etcd snapshot restore restores data, not binaries: pair with a binary downgrade"}}
        return _result(command, f"snapshot {snap['id']} written", artifacts=art)

    def _master_upgrade(self, command, master, component):
        m = next(x for x in self.c["masters"] if x["name"] == master)
        events = []
        if component == "apiserver":
            e = self.c["etcd"]
            if master in e["leaders"]:
                new = max((x for x in e["members"] if x["name"] != master and x["online"]), key=lambda x: x["raft_index"])
                e["leaders"] = [new["name"]]
                events.append(f"EVENT leader transfer {master} -> {new['name']} is expected during a master upgrade "
                              f"(election 1-2 s)")
            m["apiserver"] = self.T
            m["readyz"], m["lb_member"] = m["readyz_after_upgrade"], m["lb_after_upgrade"]
            if not m.get("etcd_returns", True):
                next(x for x in e["members"] if x["name"] == master)["online"] = False
            if self.c["addons"]["ccm"].get("healthy_after_control_plane") is False:
                self.c["addons"]["ccm"]["healthy"] = False      # the old CCM does not survive the new apiserver
        else:
            m[component] = self.T
        return _result(command, f"{component} {self.T}", events=events)

    def _terraform_lt(self, command):
        asg = self.c["workers"]["asg"]
        lt = asg["launch_template"]
        old = lt["ami"]
        lt["ami"], asg["ami"] = self.ami, self.ami
        lt["version"] += 1
        return _result(command, f"launch template {lt['id']} v{lt['version']}: AMI {old} -> {self.ami}, nothing else changed",
                       config_diff=f"- ami: {old}\n+ ami: {self.ami}\n")

    def _asg_instance_refresh(self, command, nodes):
        ccm_ok = self.c["addons"]["ccm"]["healthy"]
        events, replaced = [], []
        for n in self.c["workers"]["nodes"]:
            if n["name"] not in nodes or n["ami"] == self.ami:
                continue
            n["ami"], n["kubelet"], n["ready"] = self.ami, self.T, ccm_ok
            if not ccm_ok:
                return _result(command, f"new node {n['name']} is stuck on the uninitialized taint: "
                                        f"cloud-controller-manager is unhealthy", exit_code=1)
            replaced.append(n["name"])
            if n.get("db"):
                events.append(f"VERIFY service {n['db']} on {n['name']} healthy after replacement (stateful node, alone)")
        return _result(command, f"replaced {', '.join(replaced) or 'nothing'}", events=events)

    def _addon_rollout(self, command, addon):
        a = self.c["addons"][ADDON_KEY[addon]]
        if not a["target_rollout_healthy"]:
            why = {
                "ccm": "cloud-controller-manager rollout is unhealthy: new workers would be stranded on the "
                       "uninitialized taint. CNI and Cluster Autoscaler are untouched",
                "cni": "CNI rollout unhealthy: cross-node pod connectivity check failed. Cluster Autoscaler untouched",
                "ca": "Cluster Autoscaler rollout unhealthy: drain-triggered scale-out was not observed",
            }[addon]
            return _result(command, why, exit_code=1)
        a["version"], a["healthy"] = self.T, True
        how = {"ccm": "rollout healthy",
               "cni": f"maxUnavailable {a.get('max_unavailable', 1)}, cross-node pod connectivity ok",
               "ca": "drained one node, scale-out observed"}[addon]
        return _result(command, f"{addon} {self.T}: {how}")


EXECUTORS = {
    "simulated": SimulatedExecutor,
    "terraform": lambda w, t, a: UnimplementedExecutor("terraform"),
    "ansible": lambda w, t, a: UnimplementedExecutor("ansible"),
    "aws": lambda w, t, a: UnimplementedExecutor("aws"),
}


def make_executor(name, world, target, target_ami):
    if name not in EXECUTORS:
        raise ValueError(f"unknown executor {name!r}; known: {', '.join(EXECUTORS)}")
    return EXECUTORS[name](world, target, target_ami)
