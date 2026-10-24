"""The step state machine: gates, three layers, evidence, resume.

One Engine drives one cluster through a fixed list of steps. Every step has a
status (pending / in-progress / completed / failed) persisted in state.json
together with the simulated cluster (cluster.json), so an interrupted run can be
resumed: completed steps are skipped, an in-progress step is re-run, and every
mutating step is idempotent.
"""
from . import checks, model, plan as planmod, verify as verifymod
from .evidence import RunDir, now

OK, FAIL, AWAIT = "ok", "fail", "await"
LAYERS = {"master": "control_plane", "workers": "workers", "addon": "addons"}
ADDON_STEP = {"ccm": "ccm", "cni": "cni", "ca": "cluster_autoscaler"}
LAST_STEP = {"check": "snapshot", "plan": "plan", "apply": "addon:ca", "run": "verify"}


class Interrupted(Exception):
    pass


def build_steps(c, batches):
    """Fixed step list: check, snapshot, plan, gate, masters, workers, addons, verify."""
    ids = ["check", "snapshot", "plan", "gate:plan"]
    for m in c["masters"]:
        ids += [f"master:{m['name']}:{x}" for x in
                ("gate", "apiserver", "apiserver_ready", "controller_manager", "scheduler", "kubelet", "verify")]
    ids += ["workers:launch_template"]
    ids += [f"workers:batch{i}" for i in range(1, len(batches) + 1)]
    ids += ["workers:verify", "addon:ccm", "addon:cni", "addon:ca", "verify"]
    return ids


def layer_of(sid):
    return LAYERS.get(sid.split(":")[0])


class Engine:
    def __init__(self, fleet, rd, cluster=None, target=None, approve=False, interrupt_at=None, resume=False):
        self.fleet, self.rd, self.approve, self.interrupt_at = fleet, rd, approve, interrupt_at
        if resume:
            self.state = rd.read_json("state.json")
            self.c = rd.read_json("cluster.json")
            if target and target != self.state["target"]:
                raise ValueError(f"run {rd.run_id} targets {self.state['target']}, not {target}")
        else:
            self.c = fleet.cluster(cluster)
            batches = planmod.make_batches(self.c)
            ids = build_steps(self.c, batches)
            self.state = {
                "run_id": rd.run_id, "cluster": cluster, "target": target, "from": self.c["version"],
                "status": "running", "scope": None, "stopped_at": None, "reason": None, "created": now(),
                "batches": batches,
                "steps": [{"id": i, "layer": layer_of(i), "status": "pending", "detail": "",
                           "started": None, "finished": None} for i in ids],
            }
            rd.log(f"RUN {rd.run_id} cluster={cluster} {self.c['version']} -> {target} "
                   f"stage={self.c['stage']} type={self.c['cluster_type']} approve={approve}")
        self.T = self.state["target"]
        self.tami = model.target_ami(fleet, self.T)
        self.save()

    # ---- persistence -------------------------------------------------
    def save(self):
        self.rd.write_json("state.json", self.state)
        self.rd.write_json("cluster.json", self.c)

    def step(self, sid):
        return next(s for s in self.state["steps"] if s["id"] == sid)

    def completed(self, sid):
        return self.step(sid)["status"] == "completed"

    # ---- driver ------------------------------------------------------
    def run(self, until="run"):
        last = LAST_STEP.get(until, until)
        ids = [s["id"] for s in self.state["steps"]]
        self.state.update(status="running", scope=until, stopped_at=None, reason=None)
        for s in self.state["steps"][:ids.index(last) + 1]:
            if s["status"] == "completed":
                self.rd.log(f"SKIP {s['id']} (completed earlier)")
                continue
            if self._exec(s) != OK:
                return self.state["status"]
        self.state["status"] = "complete"
        self.rd.log(f"COMPLETE scope={until}")
        self.save()
        return "complete"

    def verify_only(self):
        """Re-run just the verify step (read-only) against the run's baseline."""
        pending = [s["id"] for s in self.state["steps"]
                   if s["status"] != "completed" and self._in_apply(s["id"])]
        if pending:
            self.state.update(status="failed", stopped_at="verify",
                              reason=f"apply is not complete; pending: {', '.join(pending[:3])}...")
            self.rd.log("FAIL verify: " + self.state["reason"], "ERROR")
            self.save()
            return "failed"
        self.step("verify")["status"] = "pending"
        return self.run("run")

    @staticmethod
    def _in_apply(sid):
        return sid.split(":")[0] in LAYERS

    def _exec(self, s):
        sid = s["id"]
        if sid == "gate:plan" or sid.endswith(":gate"):
            if not self.approve:
                self.state.update(status="awaiting_approval", stopped_at=sid,
                                  reason=f"{sid} needs a human sign-off (re-run with --approve)")
                self.rd.log(f"GATE {sid}: awaiting approval, nothing mutated past this point")
                self.save()
                return AWAIT
        self.rd.log(f"START {sid}")
        s["status"], s["started"] = "in-progress", now()
        self.save()
        if self.interrupt_at == sid:
            self.state["status"] = "interrupted"
            self.rd.log(f"INTERRUPT at {sid} (simulated crash; step left in-progress)", "WARN")
            self.save()
            raise Interrupted(sid)
        outcome, detail = self._dispatch(sid)
        s["finished"], s["detail"] = now(), detail
        if outcome == OK:
            s["status"] = "completed"
            self.rd.log(f"DONE {sid}: {detail}")
            self.save()
            return OK
        s["status"] = "failed"
        self.state.update(status="failed", stopped_at=sid, reason=detail)
        self.rd.log(f"FAIL {sid}: {detail}", "ERROR")
        self._on_failure(s, detail)
        self.save()
        return FAIL

    def _on_failure(self, s, reason):
        snap = checks.snapshot(self.c)
        self.rd.write_json("snapshots/failure.json", snap)
        layer = s["layer"] or ("verify" if s["id"] == "verify" else None)
        if layer is None or not self.rd.exists("snapshots/pre.json"):
            return
        baseline = self.rd.read_json("snapshots/pre.json")["snapshot"]
        advice = verifymod.rollback_advice(layer, s["id"], reason, snap, baseline)
        self.rd.write_json("rollback.json", advice)
        self.rd.log(f"ROLLBACK-ADVICE layer={layer} fired={advice['fired_triggers'] or 'none'} "
                    f"(advice only; a human executes)", "WARN")

    # ---- dispatch ------------------------------------------------------
    def _dispatch(self, sid):
        if sid == "check":
            return self._check()
        if sid == "snapshot":
            return self._snapshot()
        if sid == "plan":
            return self._plan()
        if sid == "gate:plan":
            self.rd.log("SIGNOFF plan approved by operator (--approve)")
            return OK, "plan approved"
        if sid.startswith("master:"):
            _, name, what = sid.split(":")
            return self._master(self._m(name), what)
        if sid == "workers:launch_template":
            return self._launch_template()
        if sid.startswith("workers:batch"):
            return self._batch(int(sid[len("workers:batch"):]))
        if sid == "workers:verify":
            return self._workers_verify()
        if sid.startswith("addon:"):
            return self._addon(sid.split(":")[1])
        if sid == "verify":
            return self._verify()
        raise KeyError(sid)

    def _m(self, name):
        return next(m for m in self.c["masters"] if m["name"] == name)

    # ---- pre-apply steps -------------------------------------------------
    def _check(self):
        snap = checks.snapshot(self.c)
        res = checks.evaluate(snap)
        self.rd.write_json("snapshots/pre.json", {"snapshot": snap, "criteria": res})
        bad = checks.failures(res)
        if bad:
            return FAIL, "check failed: " + "; ".join(f"{r['id']} ({r['detail']})" for r in bad)
        return OK, f"{len(res)}/{len(res)} criteria pass; baseline written to snapshots/pre.json"

    def _snapshot(self):
        e = self.c["etcd"]
        self.rd.write_json("etcd-snapshot.json", {
            "taken_at": now(), "cluster": self.c["name"], "members": [m["name"] for m in e["members"]],
            "leader": e["leaders"][0], "max_raft_index": max(m["raft_index"] for m in e["members"]),
            "restore_hint": "etcd snapshot restore restores data, not binaries: pair with a binary downgrade",
        })
        self.state["etcd_snapshot"] = "etcd-snapshot.json"
        return OK, "etcd snapshot written before any mutation"

    def _plan(self):
        p = planmod.build_plan(self.fleet, self.c, self.T)
        self.rd.write_json("plan.json", p)
        self.rd.write_text("plan.txt", planmod.render(p))
        if p["violations"]:
            return FAIL, "plan violations: " + "; ".join(p["violations"])
        return OK, f"dry-run clean; {len(p['warnings'])} warning(s) carried to the gate"

    # ---- control plane ---------------------------------------------------
    def _master(self, m, what):
        name, T = m["name"], self.T
        if what == "gate":
            self.rd.log(f"SIGNOFF master {name} signed off by operator (--approve), one master at a time (serial=1)")
            return OK, f"{name} signed off"
        if what == "apiserver":
            if m["apiserver"] == T:
                return OK, "already at target (idempotent no-op)"
            others_online = sum(1 for e in self.c["etcd"]["members"] if e["online"] and e["name"] != name)
            need = len(self.c["etcd"]["members"]) // 2 + 1
            if others_online < need:
                return FAIL, (f"refusing to touch {name}: only {others_online} other etcd members online, "
                              f"quorum needs {need}")
            if not model.skew_ok(T, "kubelet", m["kubelet"]):
                return FAIL, f"kubelet {m['kubelet']} would violate skew against apiserver {T}"
            events = ""
            e = self.c["etcd"]
            if name in e["leaders"]:
                new = max((x for x in e["members"] if x["name"] != name and x["online"]), key=lambda x: x["raft_index"])
                e["leaders"] = [new["name"]]
                events = f"; etcd leader moved {name} -> {new['name']} (expected, election 1-2 s)"
                self.rd.log(f"EVENT leader transfer {name} -> {new['name']} is expected during a master upgrade")
            m["apiserver"] = T
            m["readyz"], m["lb_member"] = m["readyz_after_upgrade"], m["lb_after_upgrade"]
            m["etcd_returned"] = m.get("etcd_returns", True)
            return OK, f"apiserver {T} started{events}; readiness is the next gate"
        if what == "apiserver_ready":
            if not m["readyz"]:
                return FAIL, (f"{name}: apiserver /readyz failed after upgrade; controller-manager, scheduler "
                              f"and kubelet on this master and all later masters are untouched")
            if m["lb_member"] != "healthy":
                return FAIL, (f"{name}: apiserver is not a healthy load-balancer member ({m['lb_member']}); "
                              f"upgraded would mean removed from service. Later components untouched")
            return OK, "/readyz ok and load-balancer member healthy"
        if what in ("controller_manager", "scheduler", "kubelet"):
            if not (m["apiserver"] == T and m["readyz"] and m["lb_member"] == "healthy"):
                return FAIL, f"refusing to upgrade {what} on {name}: apiserver gate (/readyz + LB) has not passed"
            if m[what] == T:
                return OK, "already at target (idempotent no-op)"
            if what != "kubelet" and not model.skew_ok(m["apiserver"], what, T):
                return FAIL, f"{what} {T} violates skew against apiserver {m['apiserver']}"
            m[what] = T
            return OK, f"{what} {T}"
        if what == "verify":
            e = next(x for x in self.c["etcd"]["members"] if x["name"] == name)
            if not m.get("etcd_returned", m.get("etcd_returns", True)):
                e["online"] = False
                return FAIL, f"{name}: etcd member did not come back (the real danger; leader transfer is not)"
            lag = model.raft_lag(self.c["etcd"])[name]
            if lag > checks.RAFT_LAG_LIMIT:
                return FAIL, f"{name}: raft lag {lag} > {checks.RAFT_LAG_LIMIT}"
            if not m["ready"]:
                return FAIL, f"{name}: node not Ready"
            vers = {m[k] for k in ("apiserver", "controller_manager", "scheduler", "kubelet")}
            if vers != {T}:
                return FAIL, f"{name}: components not all at {T}: {sorted(vers)}"
            return OK, f"member online, lag {lag}, node Ready, all components {T}"
        raise KeyError(what)

    # ---- workers ----------------------------------------------------------
    def _control_plane_done(self):
        return all(m[k] == self.T for m in self.c["masters"]
                   for k in ("apiserver", "controller_manager", "scheduler", "kubelet"))

    def _launch_template(self):
        if not self._control_plane_done():
            return FAIL, "control plane is not fully at target; workers never lead the control plane"
        asg = self.c["workers"]["asg"]
        lt = asg["launch_template"]
        extra = [k for k in lt.get("pending", {}) if k != "ami"]
        if extra:
            return FAIL, f"launch template has non-AMI changes queued ({', '.join(extra)}): only the AMI may change"
        if lt["ami"] == self.tami and asg["ami"] == self.tami:
            return OK, "already at target AMI (idempotent no-op)"
        old = lt["ami"]
        lt["ami"], lt["version"], asg["ami"] = self.tami, lt["version"] + 1, self.tami
        return OK, f"launch template {lt['id']} v{lt['version']}: AMI {old} -> {self.tami}, nothing else changed"

    def _batch(self, k):
        c, T = self.c, self.T
        asg = c["workers"]["asg"]
        if asg["ami"] != self.tami:
            return FAIL, "launch template has not been updated"
        names = self.state["batches"][k - 1]
        nodes = [n for n in c["workers"]["nodes"] if n["name"] in names and n["ami"] != self.tami]
        if not nodes:
            return OK, "all nodes in batch already on target AMI (idempotent no-op)"
        timeout = c["flags"].get("drain_timeout_s", 300)
        problems = []
        for n in nodes:                           # every drain is checked before any node is replaced
            for p in planmod.blocking_pdbs(c, n["name"]):
                problems.append(
                    f"drain of {n['name']} blocked by PDB {p['name']} (allows 0 disruptions); not forced. "
                    f"A human must wait for the PDB or lower minAvailable explicitly")
            if n["eviction_s"] > timeout:
                problems.append(
                    f"eviction of {n['name']} takes {n['eviction_s']}s but drain timeout is {timeout}s; "
                    f"not forced. This cluster needs the per-cluster flag drain_timeout_s: 600 (a human decision)")
        if problems:
            return FAIL, "; ".join(problems) + f". No node in batch {k} was replaced; later batches untouched"
        ccm_ok = c["addons"]["ccm"]["healthy"]
        for n in nodes:
            n["ami"], n["kubelet"] = self.tami, T
            n["ready"] = ccm_ok
            if not ccm_ok:
                return FAIL, (f"new node {n['name']} is stuck on the uninitialized taint: "
                              f"cloud-controller-manager is unhealthy")
            if n.get("db"):
                self.rd.log(f"VERIFY service {n['db']} on {n['name']} healthy after replacement (stateful node, alone)")
        return OK, f"batch {k}: replaced {', '.join(n['name'] for n in nodes)} (drain timeout {timeout}s, no force)"

    def _workers_verify(self):
        bad = [n["name"] for n in self.c["workers"]["nodes"]
               if n["ami"] != self.tami or n["kubelet"] != self.T or not n["ready"]]
        if bad:
            return FAIL, f"workers not on target AMI / kubelet / Ready: {', '.join(bad)}"
        return OK, f"all {len(self.c['workers']['nodes'])} workers on {self.tami}, kubelet {self.T}, Ready"

    # ---- addons -----------------------------------------------------------
    def _addon(self, short):
        order = ["ccm", "cni", "ca"]
        prev = order[order.index(short) - 1] if short != "ccm" else None
        if prev and not self.completed(f"addon:{prev}"):
            return FAIL, f"addon {short} requires {prev} to be completed first (order: CCM -> CNI -> Cluster Autoscaler)"
        a = self.c["addons"][ADDON_STEP[short]]
        if a["version"] == self.T and a["healthy"]:
            return OK, "already at target (idempotent no-op)"
        if not a["healthy"]:
            return FAIL, f"{short} is unhealthy before the upgrade"
        if not a["target_rollout_healthy"]:
            why = {
                "ccm": "cloud-controller-manager rollout is unhealthy: new workers would be stranded on the "
                       "uninitialized taint. CNI and Cluster Autoscaler are untouched",
                "cni": "CNI rollout unhealthy: cross-node pod connectivity check failed. Cluster Autoscaler untouched",
                "ca": "Cluster Autoscaler rollout unhealthy: drain-triggered scale-out was not observed",
            }[short]
            return FAIL, why
        a["version"], a["healthy"] = self.T, True
        how = {"ccm": "rollout healthy", "cni": f"maxUnavailable {a.get('max_unavailable', 1)}, cross-node pod connectivity ok",
               "ca": "drained one node, scale-out observed"}[short]
        return OK, f"{short} {self.T}: {how}"

    # ---- verify -----------------------------------------------------------
    def _verify(self):
        post = checks.snapshot(self.c)
        if self.rd.exists("snapshots/pre.json"):
            baseline = self.rd.read_json("snapshots/pre.json")["snapshot"]
            note = "baseline = snapshots/pre.json written before the upgrade"
        else:
            baseline, note = post, "no baseline file for this run: diff is empty by construction"
            self.rd.write_json("snapshots/pre.json", {"snapshot": post, "criteria": checks.evaluate(post)})
        res = verifymod.verify_cluster(post, baseline, self.T, self.tami)
        self.rd.write_json("snapshots/post.json", {"snapshot": post, "criteria": res["criteria"]})
        self.rd.write_json("diff.json", res)
        q = res["quadrant"]
        self.state["decision"] = q["decision"]
        summary = (f"version={res['version_state']} healthy={q['healthy']} -> {q['decision']}; {note}")
        if q["decision"] == "proceed":
            self.c["version"] = self.T
            return OK, summary
        extra = res["failed_criteria"] + res["diff"]["regressions"]
        return FAIL, summary + ("; " + "; ".join(extra) if extra else "")
