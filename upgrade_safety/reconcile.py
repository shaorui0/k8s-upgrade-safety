"""The reconcile loop for ONE step (control plane).

    reversibility guard -> baseline -> already_done skip -> prechecks
      -> sign-off -> execute (one executor call) -> postcheck vs baseline -> gate

Invariants:
  * The engine decides everything from snapshots; the executor only acts.
  * Every step is re-entrant: `already_done` makes a re-run after an interruption a no-op.
  * Every attempt appends exactly one evidence record (contracts/evidence.schema.json).
  * A step with reversible=false never executes without its backup_precondition holding.
"""
from . import gate, probes
from .evidence import now


class Ctx:
    """What a step needs to run: run identity, the executor, the gate settings, and where to write."""

    def __init__(self, rd, ex, run_id, cluster, operator, policy, approved, diff_ref, log):
        self.rd, self.ex, self.run_id, self.cluster = rd, ex, run_id, cluster
        self.operator, self.policy, self.approved = operator, policy, approved
        self.diff_ref, self.log = diff_ref, log


def snap_path(sid, role):
    return f"snapshots/steps/{sid.replace(':', '__')}.{role}.json"


def _record(ev, r):
    ev["assertions"].append({k: v for k, v in r.items() if k != "why"})


def _finish(ctx, ev, outcome, decision, reason, postcheck=None):
    ev.update(outcome=outcome, finished_at=now(), postcheck_snapshot=postcheck,
              gate_decision={"policy": ctx.policy, "decision": decision, "decided_by": "engine", "reason": reason})
    return ev


def run_step(ctx, step):
    """Returns {'outcome', 'reason', 'awaiting', 'evidence'}; the caller appends evidence and updates state."""
    sid = step["id"]
    ev = {"step_id": sid, "run_id": ctx.run_id, "cluster": ctx.cluster, "started_at": now(),
          "operator": ctx.operator, "assertions": [], "dry_run_diff": ctx.diff_ref, "postcheck_snapshot": None}
    baseline = ctx.ex.observe("baseline")
    ev["baseline_snapshot"] = snap_path(sid, "baseline")
    ctx.rd.write_json(ev["baseline_snapshot"], baseline)

    def stop(outcome, reason, awaiting=False, postcheck=None):
        _finish(ctx, ev, outcome, "stop", reason, postcheck)
        return {"outcome": outcome, "reason": reason, "awaiting": awaiting, "evidence": ev}

    # idempotent re-entry: already converged, nothing to do
    if "already_done" in step:
        r = probes.evaluate(step["already_done"], baseline, baseline, "already_done")
        if r["passed"]:
            _record(ev, r)           # "not done yet" is the normal case and is not evidence of anything
            _finish(ctx, ev, "converged_skipped", "continue", "already converged (idempotent re-entry)",
                    ev["baseline_snapshot"])
            return {"outcome": "converged_skipped", "reason": "already converged", "awaiting": False, "evidence": ev}

    # reversibility guard: an irreversible step needs a proven backup first
    if not step["reversible"]:
        name = step.get("backup_precondition")
        a = probes.NAMED.get(name)
        if a is None:
            return stop("stopped_precheck", f"irreversible step '{sid}' has no known backup_precondition")
        r = probes.evaluate(a, baseline, baseline, "backup")
        _record(ev, r)
        if not r["passed"]:
            return stop("stopped_precheck",
                        f"irreversible step '{sid}' refused: backup precondition '{name}' not satisfied ({r['detail']})")

    for a in step["precheck"]:
        r = probes.evaluate(a, baseline, baseline, "precheck")
        _record(ev, r)
        if not r["passed"] and r["severity"] == "block":
            return stop("stopped_precheck", f"precheck '{a['id']}' failed: {probes.explain(r)}")

    if gate.needs_signoff(ctx.policy, step):
        if not ctx.approved:
            return stop("halted_by_operator", f"{sid} needs a human sign-off (re-run with --approve)", awaiting=True)
        ctx.log(f"SIGNOFF {sid} signed off by operator (--approve)" if not sid.startswith("master:") else
                f"SIGNOFF master {sid.split(':')[1]} signed off by operator (--approve), one master at a time (serial=1)")

    res = ctx.ex.execute(step)
    for line in res["events"]:
        ctx.log(line)
    for name, obj in res["artifacts"].items():
        ctx.rd.write_json(name, obj)
    ev["execute"] = {"engine": step["execute"]["engine"], "executor": ctx.ex.name, "command": res["command"],
                     "exit_code": res["exit_code"], "stdout": res["stdout"]}
    if res["config_diff"]:
        ev["execute"]["config_diff"] = res["config_diff"]

    after = ctx.ex.observe("postcheck")
    post_ref = snap_path(sid, "postcheck")
    ctx.rd.write_json(post_ref, after)
    if res["exit_code"] != 0:
        return stop("stopped_postcheck", res["stdout"], postcheck=post_ref)

    failed = []
    for a in step["postcheck"]:
        r = probes.evaluate(a, baseline, after, "postcheck")
        _record(ev, r)
        if not r["passed"] and r["severity"] == "block":
            failed.append(r)
    ok = not failed
    decision, outcome = gate.decide(ctx.policy, ok, ctx.operator, step["gate"]["on_fail"])
    ev.update(outcome=outcome, finished_at=now(), postcheck_snapshot=post_ref, gate_decision=decision)
    if ok:
        return {"outcome": outcome, "reason": res["stdout"], "awaiting": False, "evidence": ev}
    reason = "; ".join(f"postcheck '{r['id']}' failed: {probes.explain(r)}" for r in failed)
    ev["gate_decision"] = dict(decision, reason=reason)
    return {"outcome": outcome, "reason": reason, "awaiting": False, "evidence": ev}
