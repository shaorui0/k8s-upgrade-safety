"""CLI: python3 -m upgrade_safety <check|plan|apply|verify|run> --fleet F [--cluster C] --target 1.26 [--approve] [--resume ID]

Exit codes: 0 ok, 1 failed (a gate stopped the run), 2 awaiting approval or usage error, 130 interrupted.
"""
import argparse
import sys
from datetime import datetime, timezone

from . import model, report
from .engine import Engine, Interrupted
from .evidence import RunDir

COMMANDS = ("check", "plan", "apply", "verify", "run")
CODES = {"complete": 0, "failed": 1, "awaiting_approval": 2, "interrupted": 130}


def parse(argv):
    p = argparse.ArgumentParser(prog="upgrade_safety", description="Upgrade safety model: check -> plan -> gate -> apply -> verify")
    p.add_argument("command", choices=COMMANDS)
    p.add_argument("--fleet", required=True, help="path to fleet.yaml")
    p.add_argument("--cluster", help="one cluster; omit to walk the fleet in order")
    p.add_argument("--target", help="target minor, e.g. 1.26 (default: the fleet's target_version)")
    p.add_argument("--approve", action="store_true", help="sign off the plan and each master (logged individually)")
    p.add_argument("--resume", metavar="RUN_ID", help="continue a run from its state.json")
    p.add_argument("--runs-dir", default="runs")
    p.add_argument("--run-id", help="explicit run id (default: timestamp-cluster-command)")
    p.add_argument("--interrupt-at", metavar="STEP", help="simulate a crash when this step starts (for resume tests)")
    return p.parse_args(argv)


def _new_id(cmd, cluster):
    return f"{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{cluster}-{cmd}"


def run_one(args, fleet, cluster, run_id, resume, out):
    rd = RunDir(args.runs_dir, run_id, create=not resume)
    target = args.target or fleet.target_version
    eng = Engine(fleet, rd, cluster=cluster, target=target if not resume else args.target, approve=args.approve,
                 interrupt_at=args.interrupt_at, resume=resume)
    try:
        if args.command == "verify":
            status = eng.verify_only() if resume else _verify_fresh(eng)
        else:
            status = eng.run(args.command)
    except Interrupted as ex:
        status = "interrupted"
        print(f"[{cluster}] INTERRUPTED at {ex} (state saved). Resume: --resume {run_id}", file=out)
    report.write(rd)
    _print(args, eng, rd, status, out)
    return status, eng


def _verify_fresh(eng):
    """verify without a run to resume: judge the cluster as given, baseline = itself."""
    eng.state["steps"] = [s for s in eng.state["steps"] if s["id"] == "verify"]
    return eng.run("run")


def _print(args, eng, rd, status, out):
    st, name = eng.state, eng.state["cluster"]
    done = sum(1 for s in st["steps"] if s["status"] == "completed")
    print(f"[{name}] {args.command}: {status.upper()}  run={rd.run_id}  steps {done}/{len(st['steps'])} completed", file=out)
    if args.command in ("plan", "apply", "run") and rd.exists("plan.txt") and status in ("complete", "awaiting_approval"):
        print(rd.read_text("plan.txt"), end="", file=out)
    if status == "awaiting_approval":
        print(f"NOT APPROVED: stopped at {st['stopped_at']}; nothing was changed. Review the plan, then re-run with "
              f"--approve (or --resume {rd.run_id} --approve). Each master is signed off individually.", file=out)
    if status == "failed":
        print(f"STOPPED at {st['stopped_at']}: {st['reason']}", file=out)
        if rd.exists("rollback.json"):
            rb = rd.read_json("rollback.json")
            print(f"  rollback advice: triggers fired = {', '.join(rb['fired_triggers']) or 'none'}. {rb['note']}", file=out)
        print(f"  a human decides; resume with: --resume {rd.run_id}", file=out)
    if st.get("decision"):
        print(f"  verify decision: {st['decision']}", file=out)
    print(f"  evidence: {rd.path}/   report: {rd.path}/report.html", file=out)


def main(argv=None, out=None):
    out = out or sys.stdout
    args = parse(argv)
    try:
        fleet = model.load_fleet(args.fleet)
    except model.FleetError as ex:
        print("fleet file is invalid:\n" + str(ex), file=out)
        return 2
    except OSError as ex:
        print(f"cannot read fleet: {ex}", file=out)
        return 2

    if args.cluster:
        if args.cluster not in fleet.names:
            print(f"unknown cluster {args.cluster!r}; known: {', '.join(fleet.names)}", file=out)
            return 2
        if args.resume:
            rid, resume = args.resume, True
        else:
            rid, resume = args.run_id or _new_id(args.command, args.cluster), False
            if (RunDir(args.runs_dir, rid, create=False).path).exists():
                print(f"run {rid} already exists; use --resume {rid}", file=out)
                return 2
        try:
            status, _ = run_one(args, fleet, args.cluster, rid, resume, out)
        except (ValueError, FileNotFoundError) as ex:
            print(f"error: {ex}", file=out)
            return 2
        return CODES[status]
    return _fleet(args, fleet, out)


def _fleet(args, fleet, out):
    """Walk the fleet in order; apply/run stop at the first failure and wait for a human."""
    base = args.resume or args.run_id or _new_id(args.command, "fleet")
    frd = RunDir(args.runs_dir, base, create=True)
    fs = frd.read_json("fleet.json") if args.resume and frd.exists("fleet.json") else {
        "fleet_run_id": base, "command": args.command, "order": fleet.ordered_names(), "runs": {}, "stopped_at": None}
    mutating = args.command in ("apply", "run")
    code = 0
    for name in fs["order"]:
        rid = f"{base}-{name}"
        prev = fs["runs"].get(name)
        if prev and prev["status"] == "complete":
            print(f"[{name}] already complete in this fleet run; skipping", file=out)
            continue
        resume = frd.__class__(args.runs_dir, rid, create=False).exists("state.json")
        status, _ = run_one(args, fleet, name, rid, resume, out)
        fs["runs"][name] = {"run_id": rid, "status": status}
        if status != "complete":
            code = max(code, CODES[status])
            if mutating:
                fs["stopped_at"] = name
                later = [n for n in fs["order"] if n not in fs["runs"]]
                print(f"FLEET PAUSED at {name}: a human decides how to continue. Not started: "
                      f"{', '.join(later) or 'none'}", file=out)
                break
    frd.write_json("fleet.json", fs)
    report.write_fleet(frd, fs)
    print(f"fleet evidence: {frd.path}/  report: {frd.path}/report.html", file=out)
    return code
