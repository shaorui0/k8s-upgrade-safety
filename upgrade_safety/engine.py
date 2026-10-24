"""The control-plane driver: ordered steps, state, resume, evidence.

One Engine drives one cluster through a fixed list of steps. Reconcile steps
(`steps.py`) run through `reconcile.run_step`; four pipeline phases (check,
plan, gate:plan, verify) are handled here. Every step has a status (pending /
in-progress / completed / failed) persisted in state.json together with the
simulated cluster (cluster.json), so an interrupted run resumes: completed
steps are skipped, an in-progress step is re-run, and `already_done` makes
every re-run safe.

The engine never touches the cluster. It observes and acts only through the
Executor interface (executors.py).
"""
import json

from . import checks, gate, model, plan as planmod, reconcile, steps as stepsmod, verify as verifymod
from .evidence import now
from .executors import make_executor

OK, FAIL, AWAIT = "ok", "fail", "await"
LAYERS = ("master", "worker", "components")
PHASES = ("check", "plan", "gate:plan", "verify")
SCOPES = {"check": "snapshot", "plan": "plan", "apply": None, "run": "verify"}


class Interrupted(Exception):
    pass


def _assertion_from_criterion(r):
    return {"id": r["id"], "phase": "postcheck", "probe": f"check.{r['id']}", "measured": r["ok"], "expected": True,
            "op": "==", "passed": r["ok"], "severity": "block", "detail": r["detail"]}


class Engine:
    def __init__(self, fleet, rd, cluster=None, target=None, approve=False, interrupt_at=None, resume=False,
                 executor="simulated", gate_policy="manual", operator="operator"):
        self.fleet, self.rd, self.approve, self.interrupt_at = fleet, rd, approve, interrupt_at
        self.operator, self.gate_policy, self.executor_name = operator, gate_policy, executor
        if resume:
            self.state = rd.read_json("state.json")
            self.c = rd.read_json("cluster.json")
            self.defs = {d["id"]: d for d in rd.read_json("steps.json")}
            if target and target != self.state["target"]:
                raise ValueError(f"run {rd.run_id} targets {self.state['target']}, not {target}")
            self.T = self.state["target"]
            self.tami = model.target_ami(fleet, self.T)
            self.gate_policy = gate_policy = self.state.get("gate_policy", gate_policy)
            gate.validate_policy(gate_policy, self.c["cluster_type"])
            self.ex = make_executor(executor, self.c, self.T, self.tami)
        else:
            self.c = fleet.cluster(cluster)
            self.T = target
            self.tami = model.target_ami(fleet, self.T)
            gate.validate_policy(gate_policy, self.c["cluster_type"])
            self.ex = make_executor(executor, self.c, self.T, self.tami)
            base = self.ex.observe("baseline")
            tiers = planmod.worker_tiers(base["workers"]["nodes"])
            defs = stepsmod.build_steps(base, tiers, gate_policy)
            self.defs = {d["id"]: d for d in defs}
            ids = ["check", defs[0]["id"], "plan", "gate:plan"] + [d["id"] for d in defs[1:]] + ["verify"]
            rd.write_json("steps.json", defs)
            self.state = {
                "run_id": rd.run_id, "cluster": cluster, "target": target, "from": self.c["version"],
                "status": "running", "scope": None, "stopped_at": None, "reason": None, "created": now(),
                "gate_policy": gate_policy, "tiers": tiers,
                "steps": [{"id": i, "layer": self.defs[i]["layer"] if i in self.defs else None, "status": "pending",
                           "detail": "", "started": None, "finished": None} for i in ids],
            }
            rd.log(f"RUN {rd.run_id} cluster={cluster} {self.c['version']} -> {target} "
                   f"stage={self.c['stage']} type={self.c['cluster_type']} gate={gate_policy} "
                   f"executor={executor} approve={approve}")
        self.save()

    # ---- persistence -------------------------------------------------
    def save(self):
        self.rd.write_json("state.json", self.state)
        self.rd.write_json("cluster.json", self.c)

    def step(self, sid):
        return next(s for s in self.state["steps"] if s["id"] == sid)

    def completed(self, sid):
        return self.step(sid)["status"] == "completed"

    def _ctx(self):
        return reconcile.Ctx(self.rd, self.ex, self.rd.run_id, self.c["name"], self.operator, self.gate_policy,
                             self.approve, "diff.json" if self.rd.exists("diff.json") else None, self.rd.log)

    # ---- driver ------------------------------------------------------
    def run(self, until="run"):
        last = SCOPES.get(until) or [s["id"] for s in self.state["steps"] if s["id"] != "verify"][-1]
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
                   if s["status"] != "completed" and s["layer"] in LAYERS]
        if pending:
            self.state.update(status="failed", stopped_at="verify",
                              reason=f"apply is not complete; pending: {', '.join(pending[:3])}...")
            self.rd.log("FAIL verify: " + self.state["reason"], "ERROR")
            self.save()
            return "failed"
        self.step("verify")["status"] = "pending"
        return self.run("run")

    def _exec(self, s):
        sid = s["id"]
        self.rd.log(f"START {sid}")
        s["status"], s["started"] = "in-progress", now()
        self.save()
        if self.interrupt_at == sid:
            self.state["status"] = "interrupted"
            self.rd.log(f"INTERRUPT at {sid} (simulated crash; step left in-progress)", "WARN")
            self.save()
            raise Interrupted(sid)
        out = getattr(self, "_phase_" + sid.replace(":", "_"))() if sid in PHASES else \
            reconcile.run_step(self._ctx(), self.defs[sid])
        self.rd.append_jsonl("evidence.jsonl", out["evidence"])
        s["finished"], s["detail"] = now(), out["reason"]
        if out["outcome"] in ("converged_skipped", "applied_pass"):
            s["status"] = "completed"
            self.rd.log(f"{'SKIPPED' if out['outcome'] == 'converged_skipped' else 'DONE'} {sid}: {out['reason']}")
            self.save()
            return OK
        if out["awaiting"]:
            s["status"] = "pending"
            self.state.update(status="awaiting_approval", stopped_at=sid, reason=out["reason"])
            self.rd.log(f"GATE {sid}: awaiting approval, nothing mutated past this point")
            self.save()
            return AWAIT
        s["status"] = "failed"
        self.state.update(status="failed", stopped_at=sid, reason=out["reason"])
        self.rd.log(f"FAIL {sid}: {out['reason']}", "ERROR")
        self._on_failure(s, out["reason"])
        self.save()
        return FAIL

    def _on_failure(self, s, reason):
        snap = self.ex.observe("postcheck")
        self.rd.write_json("snapshots/failure.json", snap)
        layer = s["layer"] or ("verify" if s["id"] == "verify" else None)
        if layer is None or not self.rd.exists("snapshots/baseline.json"):
            return
        advice = verifymod.rollback_advice(layer, s["id"], reason, snap, self.rd.read_json("snapshots/baseline.json"))
        self.rd.write_json("rollback.json", advice)
        self.rd.log(f"ROLLBACK-ADVICE layer={layer} fired={advice['fired_triggers'] or 'none'} "
                    f"(advice only; a human executes)", "WARN")

    # ---- pipeline phases ---------------------------------------------------
    def _evidence(self, sid, outcome, assertions, decision, reason, *, baseline="snapshots/baseline.json",
                  post=None, started=None, decided_by="engine"):
        return {"step_id": sid, "run_id": self.rd.run_id, "cluster": self.c["name"], "started_at": started or now(),
                "finished_at": now(), "outcome": outcome, "baseline_snapshot": baseline, "postcheck_snapshot": post,
                "dry_run_diff": "diff.json" if self.rd.exists("diff.json") else None, "assertions": assertions,
                "gate_decision": {"policy": self.gate_policy, "decision": decision, "decided_by": decided_by,
                                  "reason": reason},
                "operator": self.operator}

    def _phase_check(self):
        t0 = now()
        snap = self.ex.observe("baseline")
        res = checks.evaluate(snap)
        self.rd.write_json("snapshots/baseline.json", snap)
        self.rd.write_json("criteria-baseline.json", res)
        bad = checks.failures(res)
        asserts = [dict(_assertion_from_criterion(r), phase="precheck") for r in res]
        if bad:
            reason = "check failed: " + "; ".join(f"{r['id']} ({r['detail']})" for r in bad)
            return {"outcome": "stopped_precheck", "reason": reason, "awaiting": False,
                    "evidence": self._evidence("check", "stopped_precheck", asserts, "stop", reason, started=t0)}
        reason = f"{len(res)}/{len(res)} criteria pass; baseline written to snapshots/baseline.json"
        return {"outcome": "applied_pass", "reason": reason, "awaiting": False,
                "evidence": self._evidence("check", "applied_pass", asserts, "continue", "all criteria pass", started=t0)}

    def _phase_plan(self):
        t0 = now()
        base = self.rd.read_json("snapshots/baseline.json")
        diff = planmod.build_diff(self.fleet, base, self.T)
        self.rd.write_json("diff.json", diff)
        self.rd.write_text("plan.txt", planmod.render(diff, base))
        v = diff["verdict"]
        if not v["safe_to_apply"]:
            reason = "plan blockers: " + "; ".join(v["blockers"])
            return {"outcome": "stopped_precheck", "reason": reason, "awaiting": False,
                    "evidence": self._evidence("plan", "stopped_precheck", [], "stop", reason, started=t0)}
        reason = f"dry-run clean; {len(diff['changes'])} change(s), {len(v['warnings'])} warning(s) carried to the gate"
        return {"outcome": "applied_pass", "reason": reason, "awaiting": False,
                "evidence": self._evidence("plan", "applied_pass", [], "continue", "diff verdict: safe_to_apply", started=t0)}

    def _phase_gate_plan(self):
        t0 = now()
        if self.gate_policy == "manual" and not self.approve:
            reason = "gate:plan needs a human sign-off (re-run with --approve)"
            return {"outcome": "halted_by_operator", "reason": reason, "awaiting": True,
                    "evidence": self._evidence("gate:plan", "halted_by_operator", [], "stop", reason, started=t0)}
        self.rd.log("SIGNOFF plan approved by operator (--approve)")
        return {"outcome": "applied_pass", "reason": "plan approved", "awaiting": False,
                "evidence": self._evidence("gate:plan", "applied_pass", [], "continue", "plan approved",
                                           started=t0, decided_by=self.operator)}

    def _phase_verify(self):
        t0 = now()
        post = self.ex.observe("postcheck")
        if self.rd.exists("snapshots/baseline.json"):
            baseline, note = self.rd.read_json("snapshots/baseline.json"), "baseline = snapshots/baseline.json written before the upgrade"
        else:
            baseline, note = dict(post, meta=dict(post["meta"], role="baseline")), \
                "no baseline file for this run: diff is empty by construction"
            self.rd.write_json("snapshots/baseline.json", baseline)
        res = verifymod.verify_cluster(post, baseline)
        self.rd.write_json("snapshots/final.json", post)
        self.rd.write_json("criteria-final.json", res["criteria"])
        self.rd.write_json("verify.json", res)
        q = res["quadrant"]
        self.state["decision"] = q["decision"]
        summary = f"version={res['version_state']} healthy={q['healthy']} -> {q['decision']}; {note}"
        asserts = [_assertion_from_criterion(r) for r in res["criteria"]]
        asserts += [{"id": f"regression-{i}", "phase": "postcheck", "probe": "baseline.diff", "measured": x,
                     "expected": "no regression", "op": "==", "passed": False, "severity": "block", "detail": x}
                    for i, x in enumerate(res["diff"]["regressions"])]
        if q["decision"] == "proceed":
            self.c["version"] = self.T
            return {"outcome": "applied_pass", "reason": summary, "awaiting": False,
                    "evidence": self._evidence("verify", "applied_pass", asserts, "continue", summary,
                                               post="snapshots/final.json", started=t0)}
        extra = res["failed_criteria"] + res["diff"]["regressions"]
        reason = summary + ("; " + "; ".join(extra) if extra else "")
        return {"outcome": "stopped_postcheck", "reason": reason, "awaiting": False,
                "evidence": self._evidence("verify", "stopped_postcheck", asserts, "stop", reason,
                                           post="snapshots/final.json", started=t0)}
