"""Fleet loading and validation, version arithmetic, quorum math, fleet order.

Pure functions over plain dicts; no I/O except `load_fleet`.
"""
import copy
from pathlib import Path

import yaml

STAGES = ["dev", "preprod", "prod-canary", "prod", "management"]
CLUSTER_TYPES = {"workload", "management", "dev-staging"}

# version-skew policy relative to the apiserver
MAX_SKEW = {"kubelet": 2, "controller_manager": 1, "scheduler": 1}


class FleetError(Exception):
    """Raised with every structural problem found, one per line."""

    def __init__(self, problems):
        self.problems = list(problems)
        super().__init__("\n".join(self.problems))


def minor(version):
    """'1.26' -> 26. Only major 1 exists in the model."""
    major, _, mnr = str(version).partition(".")
    if major != "1" or not mnr.isdigit():
        raise ValueError(f"bad version {version!r}")
    return int(mnr)


def skew_ok(apiserver, component, version):
    """May `component` run `version` while the apiserver runs `apiserver`?

    Nothing may be newer than the apiserver; kubelet may trail by <= 2 minors,
    controller_manager and scheduler by <= 1.
    """
    diff = minor(apiserver) - minor(version)
    return 0 <= diff <= MAX_SKEW[component]


def quorum_tolerance(members):
    """Failures an etcd cluster of `members` survives: (n - 1) // 2."""
    return (members - 1) // 2


def raft_lag(etcd):
    """Per-member lag behind the highest index (the leader's, in a sane cluster)."""
    top = max(m["raft_index"] for m in etcd["members"])
    return {m["name"]: top - m["raft_index"] for m in etcd["members"]}


def target_ami(fleet, version):
    """The AMI whose kubelet equals `version` (None if there is none)."""
    cands = sorted(a for a, d in fleet.amis.items() if d["kubelet"] == version)
    return cands[0] if cands else None


class FleetError(Exception):
    """Raised with every structural problem found, one per line."""

    def __init__(self, problems):
        self.problems = list(problems)
        super().__init__("\n".join(self.problems))


def minor(version):
    """'1.26' -> 26. Only major 1 exists in the model."""
    major, _, mnr = str(version).partition(".")
    if major != "1" or not mnr.isdigit():
        raise ValueError(f"bad version {version!r}")
    return int(mnr)


def skew_ok(apiserver, component, version):
    """May `component` run `version` while the apiserver runs `apiserver`?

    Nothing may be newer than the apiserver; kubelet may trail by <= 2 minors,
    controller_manager and scheduler by <= 1.
    """
    diff = minor(apiserver) - minor(version)
    return 0 <= diff <= MAX_SKEW[component]


def quorum_tolerance(members):
    """Failures an etcd cluster of `members` survives: (n - 1) // 2."""
    return (members - 1) // 2


def raft_lag(etcd):
    """Per-member lag behind the highest index (the leader's, in a sane cluster)."""
    top = max(m["raft_index"] for m in etcd["members"])
    return {m["name"]: top - m["raft_index"] for m in etcd["members"]}


def target_ami(fleet, version):
    """The AMI whose kubelet equals `version`, preferring a name ending in the minor."""
    cands = sorted(a for a, d in fleet.amis.items() if d["kubelet"] == version)
    preferred = [a for a in cands if a.endswith(str(minor(version)) + "") or a.endswith(version.replace(".", ""))]
    return (preferred or cands or [None])[0]


class Fleet:
    def __init__(self, data):
        self.data = data
        self.source_version = data["fleet"]["source_version"]
        self.target_version = data["fleet"]["target_version"]
        self.stage_order = data["fleet"].get("stage_order", STAGES)
        self.amis = data["amis"]
        self.faults = data.get("faults", [])
        self._clusters = {c["name"]: c for c in data["clusters"]}

    @property
    def names(self):
        return list(self._clusters)

    def cluster(self, name):
        """A deep copy, so a simulation can mutate it freely."""
        if name not in self._clusters:
            raise KeyError(f"unknown cluster {name!r}; known: {', '.join(self._clusters)}")
        return copy.deepcopy(self._clusters[name])

    def ordered(self):
        """dev -> preprod -> prod canary -> remaining prod -> management last."""
        rank = {s: i for i, s in enumerate(self.stage_order)}
        return sorted(self._clusters.values(), key=lambda c: (rank[c["stage"]], c["name"]))

    def ordered_names(self):
        return [c["name"] for c in self.ordered()]

    def fault_for(self, name):
        return [f for f in self.faults if f["cluster"] == name]


def validate(data):
    """Return the list of structural problems (empty = valid)."""
    p = []
    fleet = data.get("fleet") or {}
    for k in ("source_version", "target_version"):
        if k not in fleet:
            p.append(f"fleet.{k} missing")
    amis = data.get("amis") or {}
    clusters = data.get("clusters") or []
    if len(clusters) < 5:
        p.append(f"need at least 5 clusters, found {len(clusters)}")
    names = [c.get("name") for c in clusters]
    if len(set(names)) != len(names):
        p.append("duplicate cluster names")
    stages = {c.get("stage") for c in clusters}
    for s in STAGES:
        if s not in stages:
            p.append(f"no cluster in stage {s}")
    for c in clusters:
        n = c.get("name", "?")
        if c.get("stage") not in STAGES:
            p.append(f"{n}: unknown stage {c.get('stage')!r}")
        if c.get("cluster_type") not in CLUSTER_TYPES:
            p.append(f"{n}: unknown cluster_type {c.get('cluster_type')!r}")
        masters = c.get("masters") or []
        if len(masters) % 2 == 0 or not masters:
            p.append(f"{n}: master count must be odd, got {len(masters)}")
        mnames = {m["name"] for m in masters}
        etcd = c.get("etcd") or {}
        members = {m["name"] for m in etcd.get("members", [])}
        if members != mnames:
            p.append(f"{n}: etcd members {sorted(members)} do not match masters {sorted(mnames)}")
        for leader in etcd.get("leaders", []):
            if leader not in members:
                p.append(f"{n}: leader {leader} is not an etcd member")
        workers = c.get("workers") or {}
        asg = workers.get("asg") or {}
        if asg.get("ami") not in amis:
            p.append(f"{n}: unknown AMI {asg.get('ami')!r} on ASG")
        lt = asg.get("launch_template") or {}
        if lt.get("ami") not in amis:
            p.append(f"{n}: unknown AMI {lt.get('ami')!r} in launch template")
        node_names = set()
        for node in workers.get("nodes", []):
            node_names.add(node["name"])
            if node.get("ami") not in amis:
                p.append(f"{n}: node {node['name']} has unknown AMI {node.get('ami')!r}")
        for pdb in c.get("pdbs", []):
            for nn in pdb.get("nodes", []):
                if nn not in node_names:
                    p.append(f"{n}: PDB {pdb['name']} names unknown node {nn}")
        for a in ("ccm", "cni", "cluster_autoscaler"):
            if a not in (c.get("addons") or {}):
                p.append(f"{n}: addon {a} missing")
    for f in data.get("faults", []):
        if f.get("cluster") not in names:
            p.append(f"fault {f.get('id')}: unknown cluster {f.get('cluster')!r}")
    if fleet.get("target_version") and not any(
            d["kubelet"] == fleet["target_version"] for d in amis.values()):
        p.append(f"no AMI whose kubelet is {fleet['target_version']}")
    return p


def load_fleet(path):
    data = yaml.safe_load(Path(path).read_text())
    problems = validate(data)
    if problems:
        raise FleetError(problems)
    return Fleet(data)
