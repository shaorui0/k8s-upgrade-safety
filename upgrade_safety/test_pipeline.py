import io
import json
import re
import tempfile
import unittest
from pathlib import Path

from upgrade_safety import cli, model, verify

FLEET_PATH = Path(__file__).resolve().parent.parent / "testenv" / "fleet.yaml"
FLEET = model.load_fleet(FLEET_PATH)


def make_engine(runs, rid, cluster="dev-1", fleet=FLEET, **kw):
    from upgrade_safety.engine import Engine
    from upgrade_safety.evidence import RunDir
    return Engine(fleet, RunDir(runs, rid), cluster=cluster, target="1.26", approve=kw.pop("approve", True), **kw)


def run_def(eng, sid):
    from upgrade_safety import reconcile
    return reconcile.run_step(eng._ctx(), eng.defs[sid])


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.runs = self._tmp.name
        self.n = 0

    def tearDown(self):
        self._tmp.cleanup()

    def cli(self, *argv, fleet=None):
        out = io.StringIO()
        code = cli.main([argv[0], "--fleet", str(fleet or FLEET_PATH), "--runs-dir", self.runs, *argv[1:]], out)
        return code, out.getvalue()

    def run_cluster(self, command, cluster, *extra, run_id=None):
        self.n += 1
        rid = run_id or f"t{self.n}-{cluster}"
        code, out = self.cli(command, "--cluster", cluster, "--target", "1.26", "--run-id", rid, *extra)
        return code, out, Path(self.runs) / rid

    @staticmethod
    def state(rd):
        return json.loads((rd / "state.json").read_text())

    @staticmethod
    def world(rd):
        return json.loads((rd / "cluster.json").read_text())

    @staticmethod
    def status(rd, sid):
        return next(s["status"] for s in json.loads((rd / "state.json").read_text())["steps"] if s["id"] == sid)

    @staticmethod
    def log(rd):
        return (rd / "execution.log").read_text()


class CheckGateTest(Base):
    def test_raft_lag_over_1000_fails_check_and_mutates_nothing(self):
        code, out, rd = self.run_cluster("check", "prod-east")
        self.assertEqual(code, 1)
        self.assertIn("etcd_raft_lag", out)
        crit = json.loads((rd / "criteria-baseline.json").read_text())
        failed = [r["id"] for r in crit if not r["ok"]]
        self.assertEqual(failed, ["etcd_raft_lag"])
        self.assertEqual(self.status(rd, "snapshot"), "pending")      # no snapshot, no further step
        self.assertFalse((rd / "etcd-snapshot.json").exists())
        self.assertTrue((rd / "report.html").exists())

    def test_run_stops_at_check_for_raft_lag(self):
        code, out, rd = self.run_cluster("run", "prod-east", "--approve")
        self.assertEqual(code, 1)
        self.assertEqual(self.state(rd)["stopped_at"], "check")
        self.assertTrue(all(m["apiserver"] == "1.25" for m in self.world(rd)["masters"]))

    def test_clean_check_takes_snapshot(self):
        code, _, rd = self.run_cluster("check", "prod-canary")
        self.assertEqual(code, 0)
        self.assertTrue((rd / "etcd-snapshot.json").exists())


class ApproveGateTest(Base):
    def test_apply_without_approve_refuses_and_prints_plan(self):
        code, out, rd = self.run_cluster("apply", "prod-canary")
        self.assertEqual(code, 2)
        self.assertIn("NOT APPROVED", out)
        self.assertIn("PLAN prod-canary", out)
        self.assertTrue((rd / "diff.json").exists())
        self.assertEqual(self.state(rd)["status"], "awaiting_approval")
        self.assertEqual(self.state(rd)["stopped_at"], "gate:plan")
        w = self.world(rd)
        self.assertTrue(all(m["apiserver"] == "1.25" for m in w["masters"]))
        self.assertEqual(w["workers"]["asg"]["ami"], "ami-synth-125")

    def test_run_without_approve_also_refuses(self):
        code, _, _ = self.run_cluster("run", "dev-1")
        self.assertEqual(code, 2)

    def test_each_master_is_signed_off_individually_in_order(self):
        code, _, rd = self.run_cluster("apply", "prod-canary", "--approve")
        self.assertEqual(code, 0)
        signoffs = re.findall(r"SIGNOFF master (\S+) signed off", self.log(rd))
        self.assertEqual(signoffs, ["prod-canary-m1", "prod-canary-m2", "prod-canary-m3"])
        for m in signoffs:    # sign-off precedes that master's first mutation
            self.assertLess(self.log(rd).index(f"SIGNOFF master {m}"), self.log(rd).index(f"DONE master:{m}:apiserver"))

    def test_approving_via_resume_continues_the_same_run(self):
        code, _, rd = self.run_cluster("apply", "prod-canary", run_id="gated")
        self.assertEqual(code, 2)
        code, out = self.cli("apply", "--cluster", "prod-canary", "--resume", "gated", "--approve")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.log(rd).count("START check"), 1)


class ApiserverGateTest(Base):
    def test_readyz_failure_stops_before_next_component(self):
        code, out, rd = self.run_cluster("run", "prod-north", "--approve")
        self.assertEqual(code, 1)
        st = self.state(rd)
        self.assertEqual(st["stopped_at"], "master:prod-north-m2:apiserver_ready")
        w = {m["name"]: m for m in self.world(rd)["masters"]}
        m1, m2, m3 = w["prod-north-m1"], w["prod-north-m2"], w["prod-north-m3"]
        self.assertEqual({m1[k] for k in ("apiserver", "controller_manager", "scheduler", "kubelet")}, {"1.26"})
        self.assertEqual(m2["apiserver"], "1.26")                       # the apiserver moved...
        self.assertEqual((m2["controller_manager"], m2["scheduler"], m2["kubelet"]), ("1.25",) * 3)  # ...nothing else did
        self.assertEqual({m3[k] for k in ("apiserver", "controller_manager", "scheduler", "kubelet")}, {"1.25"})
        self.assertEqual(self.status(rd, "master:prod-north-m2:controller_manager"), "pending")
        self.assertNotIn("START master:prod-north-m3", self.log(rd))
        self.assertEqual(self.world(rd)["workers"]["asg"]["ami"], "ami-synth-125")

    def test_readyz_alone_is_enough_to_stop(self):
        import yaml
        d = json.loads(json.dumps(FLEET.data))
        d["clusters"][0]["masters"][0]["readyz_after_upgrade"] = False      # LB stays healthy
        p = Path(self.runs) / "readyz.yaml"
        p.write_text(yaml.safe_dump(d))
        code, out = self.cli("run", "--cluster", "dev-1", "--approve", "--run-id", "readyz", fleet=p)
        self.assertEqual(code, 1)
        self.assertIn("/readyz failed", out)
        w = self.world(Path(self.runs) / "readyz")
        self.assertEqual((w["masters"][0]["controller_manager"], w["masters"][0]["scheduler"]), ("1.25", "1.25"))

    def test_lb_membership_is_a_separate_gate(self):
        c = FLEET.cluster("dev-1")
        c["masters"][0]["lb_after_upgrade"] = "unhealthy"          # /readyz fine, LB says no
        d = json.loads(json.dumps(FLEET.data))
        d["clusters"][0] = c
        import yaml
        p = Path(self.runs) / "lb.yaml"
        p.write_text(yaml.safe_dump(d))
        code, out = self.cli("run", "--cluster", "dev-1", "--approve", "--run-id", "lb", fleet=p)
        self.assertEqual(code, 1)
        self.assertIn("load-balancer member", out)
        w = self.world(Path(self.runs) / "lb")
        self.assertEqual(w["masters"][0]["controller_manager"], "1.25")

    def test_next_component_refuses_if_gate_was_skipped(self):
        eng = make_engine(self.runs, "direct")
        self.assertEqual(run_def(eng, "snapshot")["outcome"], "applied_pass")      # backup precondition satisfied
        m = eng.c["masters"][0]
        m["apiserver"], m["readyz"] = "1.26", False
        out = run_def(eng, "master:dev-1-m1:controller_manager")
        self.assertEqual(out["outcome"], "stopped_precheck")
        self.assertEqual(m["controller_manager"], "1.25")
        self.assertIn("apiserver gate", out["reason"])

    def test_leader_transfer_is_logged_as_expected(self):
        code, _, rd = self.run_cluster("run", "dev-1", "--approve")
        self.assertEqual(code, 0)
        self.assertIn("leader transfer dev-1-m1", self.log(rd))
        self.assertIn("is expected", self.log(rd))

    def test_member_that_does_not_come_back_is_the_danger(self):
        import yaml
        d = json.loads(json.dumps(FLEET.data))
        d["clusters"][0]["masters"][1]["etcd_returns"] = False
        p = Path(self.runs) / "dead.yaml"
        p.write_text(yaml.safe_dump(d))
        code, out = self.cli("run", "--cluster", "dev-1", "--approve", "--run-id", "dead", fleet=p)
        self.assertEqual(code, 1)
        self.assertEqual(self.state(Path(self.runs) / "dead")["stopped_at"], "master:dev-1-m2:verify")
        self.assertIn("real danger", out)


class WorkerLayerTest(Base):
    def test_pdb_blocks_drain_and_nothing_is_forced(self):
        code, out, rd = self.run_cluster("run", "prod-west", "--approve")
        self.assertEqual(code, 1)
        self.assertEqual(self.state(rd)["stopped_at"], "workers:canary")
        self.assertIn("PDB mysql-pdb", out)
        self.assertIn("never forced", out)
        self.assertIn("lower minAvailable", self.state(rd)["reason"])
        w = self.world(rd)
        self.assertTrue(all(n["ami"] == "ami-synth-125" for n in w["workers"]["nodes"]))   # not one node replaced
        self.assertEqual(self.status(rd, "workers:batch1"), "pending")

    def test_slow_eviction_needs_the_600s_flag(self):
        code, out, rd = self.run_cluster("run", "prod-eu", "--approve")
        self.assertEqual(code, 1)
        self.assertIn("drain_timeout_s: 600", out)
        self.assertTrue(self.state(rd)["stopped_at"].startswith("workers:batch"))
        # same fault, flag set: passes
        import yaml
        d = json.loads(json.dumps(FLEET.data))
        eu = next(c for c in d["clusters"] if c["name"] == "prod-eu")
        eu["flags"]["drain_timeout_s"] = 600
        p = Path(self.runs) / "flag.yaml"
        p.write_text(yaml.safe_dump(d))
        code, out = self.cli("run", "--cluster", "prod-eu", "--approve", "--run-id", "flagged", fleet=p)
        self.assertEqual(code, 0, out)

    def test_flagged_preprod_passes(self):
        code, _, _ = self.run_cluster("run", "preprod-1", "--approve")
        self.assertEqual(code, 0)

    def test_stateful_nodes_go_first_and_alone(self):
        code, _, rd = self.run_cluster("run", "prod-canary", "--approve")
        self.assertEqual(code, 0)
        tiers = self.state(rd)["tiers"]
        w = {n["name"]: n for n in self.world(rd)["workers"]["nodes"]}
        db_nodes = sorted(n for n, x in w.items() if x["db"])
        self.assertEqual([t["nodes"] for t in tiers[:len(db_nodes)]], [[n] for n in db_nodes])
        self.assertIn("VERIFY service kafka", self.log(rd))

    def test_canary_runs_before_any_batch_and_is_one_node(self):
        code, _, rd = self.run_cluster("run", "prod-canary", "--approve")
        ids = [s["id"] for s in self.state(rd)["steps"]]
        self.assertLess(ids.index("workers:canary"), ids.index("workers:batch1"))
        defs = {d["id"]: d for d in json.loads((rd / "steps.json").read_text())}
        self.assertEqual(len(defs["workers:canary"]["blast_radius"]["nodes"]), 1)
        self.assertEqual(defs["workers:canary"]["blast_radius"]["phase"], "canary")
        self.assertLess(self.log(rd).index("DONE workers:canary"), self.log(rd).index("START workers:batch1"))

    def test_workers_never_lead_the_control_plane(self):
        eng = make_engine(self.runs, "lead")
        out = run_def(eng, "workers:launch_template")
        self.assertEqual(out["outcome"], "stopped_precheck")
        self.assertIn("never lead", out["reason"])

    def test_new_node_stuck_when_ccm_unhealthy_now(self):
        eng = make_engine(self.runs, "stuck")
        for m in eng.c["masters"]:
            for k in ("apiserver", "controller_manager", "scheduler", "kubelet"):
                m[k] = "1.26"
        self.assertEqual(run_def(eng, "workers:launch_template")["outcome"], "applied_pass")
        eng.c["addons"]["ccm"]["healthy"] = False
        out = run_def(eng, "workers:canary")
        self.assertEqual(out["outcome"], "stopped_precheck")                 # the precheck catches it first
        self.assertIn("uninitialized taint", out["reason"])
        self.assertEqual(eng.c["workers"]["nodes"][0]["ami"], "ami-synth-125")
        # defence in depth: even if the precheck were bypassed, the executor reports the stuck node
        res = eng.ex.execute(eng.defs["workers:canary"])
        self.assertEqual(res["exit_code"], 1)
        self.assertIn("uninitialized taint", res["stdout"])

    def test_every_worker_step_carries_the_ccm_precheck(self):
        eng = make_engine(self.runs, "ccmdefs")
        worker = [d for d in eng.defs.values() if d["layer"] == "worker" and d["id"] != "workers:verify"]
        self.assertTrue(worker)
        for d in worker:
            ids = [a["id"] for a in d["precheck"]]
            self.assertIn("ccm-healthy", ids, d["id"])


class AddonLayerTest(Base):
    def test_ccm_broken_by_the_new_control_plane_stops_the_worker_layer_before_any_worker(self):
        code, out, rd = self.run_cluster("run", "prod-south", "--approve")
        self.assertEqual(code, 1)
        st = self.state(rd)
        self.assertEqual(st["stopped_at"], "workers:launch_template")
        self.assertIn("uninitialized taint", st["reason"])
        w = self.world(rd)
        self.assertTrue(all(m[k] == "1.26" for m in w["masters"] for k in ("apiserver", "controller_manager", "scheduler", "kubelet")))
        self.assertEqual(w["workers"]["asg"]["ami"], "ami-synth-125")
        self.assertEqual(w["workers"]["asg"]["launch_template"]["ami"], "ami-synth-125")
        self.assertTrue(all(n["ami"] == "ami-synth-125" for n in w["workers"]["nodes"]))
        a = w["addons"]
        self.assertEqual((a["ccm"]["version"], a["cni"]["version"], a["cluster_autoscaler"]["version"]), ("1.25",) * 3)
        self.assertEqual(self.status(rd, "workers:canary"), "pending")
        self.assertEqual(self.status(rd, "addon:ccm"), "pending")
        self.assertEqual(self.status(rd, "master:prod-south-m3:verify"), "completed")      # control plane did finish
        last = [json.loads(x) for x in (rd / "evidence.jsonl").read_text().splitlines()][-1]
        self.assertEqual((last["outcome"], [a["id"] for a in last["assertions"] if not a["passed"]]),
                         ("stopped_precheck", ["ccm-healthy"]))
        self.assertNotIn("execute", last)                                                  # executor never called

    def test_ccm_unhealthy_mid_layer_stops_the_next_batch(self):
        eng = make_engine(self.runs, "mid")
        eng.run("workers:canary")
        self.assertEqual(self.status(Path(self.runs) / "mid", "workers:canary"), "completed")
        eng.c["addons"]["ccm"]["healthy"] = False
        self.assertEqual(eng.run("apply"), "failed")
        self.assertEqual(eng.state["stopped_at"], "workers:batch1")
        replaced = [n["name"] for n in eng.c["workers"]["nodes"] if n["ami"] == "ami-synth-126"]
        self.assertEqual(replaced, ["dev-1-w1"])                                           # only the canary

    def test_addon_layer_still_verifies_the_ccm_rollout(self):
        import yaml
        d = json.loads(json.dumps(FLEET.data))
        d["clusters"][0]["addons"]["ccm"]["target_rollout_healthy"] = False
        p = Path(self.runs) / "rollout.yaml"
        p.write_text(yaml.safe_dump(d))
        code, out = self.cli("run", "--cluster", "dev-1", "--approve", "--run-id", "rollout", fleet=p)
        self.assertEqual(code, 1)
        rd = Path(self.runs) / "rollout"
        self.assertEqual(self.state(rd)["stopped_at"], "addon:ccm")
        self.assertIn("uninitialized taint", self.state(rd)["reason"])
        a = self.world(rd)["addons"]
        self.assertEqual((a["cni"]["version"], a["cluster_autoscaler"]["version"]), ("1.25", "1.25"))
        self.assertEqual(self.status(rd, "workers:verify"), "completed")

    def test_addon_order_is_enforced(self):
        eng = make_engine(self.runs, "order")
        out = run_def(eng, "addon:cni")
        self.assertEqual(out["outcome"], "stopped_precheck")
        self.assertIn("requires ccm", out["reason"])
        self.assertEqual(eng.c["addons"]["cni"]["version"], "1.25")


class QuadrantTest(unittest.TestCase):
    def test_four_quadrants(self):
        self.assertEqual(verify.quadrant("target", True)["decision"], "proceed")
        self.assertEqual(verify.quadrant("old", True)["decision"], "rerun")
        self.assertEqual(verify.quadrant("target", False)["decision"], "human")
        self.assertEqual(verify.quadrant("old", False)["decision"], "human")

    def test_mixed_version_counts_as_old(self):
        self.assertEqual(verify.quadrant("mixed", True)["decision"], "rerun")


class VerifyTest(Base):
    def test_verify_diffs_against_the_baseline_file(self):
        code, _, rd = self.run_cluster("run", "prod-canary", "--approve")
        self.assertEqual(code, 0)
        d = json.loads((rd / "verify.json").read_text())
        self.assertEqual(d["quadrant"]["decision"], "proceed")
        self.assertEqual(d["version_state"], "target")
        self.assertIn("prod-canary-m1.apiserver: 1.25 -> 1.26", d["diff"]["changed"])
        self.assertIn("addon.ccm: 1.25 -> 1.26", d["diff"]["changed"])
        self.assertEqual(d["diff"]["regressions"], [])

    def test_old_version_healthy_is_rerun(self):
        code, out, rd = self.run_cluster("verify", "dev-1")
        self.assertEqual(code, 1)
        self.assertEqual(self.state(rd)["decision"], "rerun")

    def test_new_alert_after_upgrade_is_a_regression_and_human(self):
        code, _, rd = self.run_cluster("run", "dev-1", "--approve")
        self.assertEqual(code, 0)
        w = self.world(rd)
        w["external"]["alerts"] = ["PodCrashLooping"]
        (rd / "cluster.json").write_text(json.dumps(w))
        code, out = self.cli("verify", "--cluster", "dev-1", "--resume", rd.name)
        self.assertEqual(code, 1)
        self.assertEqual(self.state(rd)["decision"], "human")
        self.assertIn("new alerts since baseline", self.state(rd)["reason"])

    def test_baseline_regression_alone_blocks_proceed(self):
        """Criteria all pass, but fewer pods Running than the baseline: only the baseline diff can see it."""
        code, _, rd = self.run_cluster("run", "dev-1", "--approve")
        self.assertEqual(code, 0)
        w = self.world(rd)
        w["workload"]["pods_running"] -= 10
        (rd / "cluster.json").write_text(json.dumps(w))
        code, _ = self.cli("verify", "--cluster", "dev-1", "--resume", rd.name)
        self.assertEqual(code, 1)
        d = json.loads((rd / "verify.json").read_text())
        self.assertEqual(d["failed_criteria"], [])
        self.assertEqual(d["diff"]["regressions"], ["Running pods 60 -> 50"])
        self.assertEqual(d["quadrant"]["decision"], "human")

    def test_verify_refuses_an_incomplete_apply(self):
        _, _, rd = self.run_cluster("run", "prod-south", "--approve")
        code, out = self.cli("verify", "--cluster", "prod-south", "--resume", rd.name)
        self.assertEqual(code, 1)
        self.assertIn("apply is not complete", out)

    def test_monitor_disagreement_blocks_proceed(self):
        code, _, rd = self.run_cluster("run", "dev-1", "--approve")
        w = self.world(rd)
        w["monitor"]["nodes_ready"] += 2
        (rd / "cluster.json").write_text(json.dumps(w))
        code, out = self.cli("verify", "--cluster", "dev-1", "--resume", rd.name)
        self.assertEqual(code, 1)
        self.assertEqual(self.state(rd)["decision"], "human")


class RollbackAdviceTest(Base):
    def test_master_failure_fires_trigger_with_control_plane_actions(self):
        _, _, rd = self.run_cluster("run", "prod-north", "--approve")
        rb = json.loads((rd / "rollback.json").read_text())
        self.assertEqual(rb["fired_triggers"], ["master_upgrade_failed"])
        self.assertTrue(any("etcd snapshot" in a for a in rb["actions"]))
        self.assertTrue(any("binaries" in a for a in rb["actions"]))

    def test_pdb_stop_fires_no_trigger_and_nothing_executes(self):
        _, _, rd = self.run_cluster("run", "prod-west", "--approve")
        rb = json.loads((rd / "rollback.json").read_text())
        self.assertEqual(rb["fired_triggers"], [])
        self.assertFalse(rb["recommended"])

    def test_triggers_pods_services_alert_flood(self):
        snap = {"workload": {"running_ratio": 0.4, "unreachable": ["edge-gateway"]}, "alerts": [f"A{i}" for i in range(5)]}
        base = {"alerts": []}
        self.assertEqual(verify.rollback_triggers(snap, base, "worker"),
                         ["pods_not_running_over_50pct", "critical_service_unreachable", "alert_flood"])
        ok = {"workload": {"running_ratio": 0.5, "unreachable": []}, "alerts": ["A1"]}
        self.assertEqual(verify.rollback_triggers(ok, base, "components"), [])

    def test_layer_actions(self):
        self.assertIn("rollout undo", " ".join(verify.ROLLBACK_ACTIONS["components"]))
        self.assertIn("Launch Template", " ".join(verify.ROLLBACK_ACTIONS["worker"]))


class ResumeTest(Base):
    def test_resume_does_not_repeat_completed_steps(self):
        code, out, rd = self.run_cluster("run", "prod-canary", "--approve", "--interrupt-at", "master:prod-canary-m2:apiserver",
                                         run_id="crash")
        self.assertEqual(code, 130)
        self.assertEqual(self.status(rd, "master:prod-canary-m2:apiserver"), "in-progress")
        done_before = [s["id"] for s in self.state(rd)["steps"] if s["status"] == "completed"]
        self.assertIn("master:prod-canary-m1:verify", done_before)
        code, out = self.cli("run", "--cluster", "prod-canary", "--resume", "crash", "--approve")
        self.assertEqual(code, 0, out)
        log = self.log(rd)
        for sid in done_before:
            self.assertEqual(log.count(f"START {sid}\n"), 1, sid)
            self.assertIn(f"SKIP {sid} (completed earlier)", log)
        self.assertEqual(log.count("START master:prod-canary-m2:apiserver\n"), 2)       # in-progress step re-ran
        self.assertEqual(log.count("SIGNOFF master prod-canary-m1"), 1)
        self.assertTrue(all(s["status"] == "completed" for s in self.state(rd)["steps"]))
        self.assertEqual(self.state(rd)["status"], "complete")

    def test_resume_after_failure_keeps_earlier_work(self):
        _, _, rd = self.run_cluster("run", "prod-south", "--approve", run_id="stuck")
        code, _ = self.cli("run", "--cluster", "prod-south", "--resume", "stuck", "--approve")
        self.assertEqual(code, 1)
        self.assertEqual(self.log(rd).count("START master:prod-south-m3:verify\n"), 1)
        self.assertEqual(self.log(rd).count("START workers:launch_template\n"), 2)        # failed step is retried, not skipped

    def test_mutating_steps_are_idempotent_and_skip_the_executor(self):
        eng = make_engine(self.runs, "idem")
        self.assertEqual(run_def(eng, "snapshot")["outcome"], "applied_pass")
        calls = []
        real = eng.ex.execute
        eng.ex.execute = lambda step: calls.append(step["id"]) or real(step)
        self.assertEqual(run_def(eng, "master:dev-1-m1:apiserver")["outcome"], "applied_pass")
        again = run_def(eng, "master:dev-1-m1:apiserver")
        self.assertEqual(again["outcome"], "converged_skipped")
        self.assertEqual(calls, ["master:dev-1-m1:apiserver"])       # the second run never reached the executor

    def test_existing_run_id_is_not_overwritten(self):
        self.run_cluster("check", "dev-1", run_id="same")
        code, out, _ = self.run_cluster("check", "dev-1", run_id="same")
        self.assertEqual(code, 2)
        self.assertIn("already exists", out)


class EvidenceTest(Base):
    def test_complete_run_leaves_all_evidence(self):
        code, _, rd = self.run_cluster("run", "prod-canary", "--approve")
        self.assertEqual(code, 0)
        for f in ("snapshots/baseline.json", "snapshots/final.json", "diff.json", "plan.txt", "execution.log",
                  "state.json", "cluster.json", "verify.json", "etcd-snapshot.json", "report.html", "steps.json",
                  "evidence.jsonl", "criteria-baseline.json", "criteria-final.json"):
            self.assertTrue((rd / f).exists(), f)
        self.assertFalse((rd / "rollback.json").exists())
        self.assertTrue(all(s["status"] == "completed" for s in self.state(rd)["steps"]))

    def test_report_html_is_escaped_and_has_the_decision(self):
        _, _, rd = self.run_cluster("run", "prod-canary", "--approve")
        html = (rd / "report.html").read_text()
        self.assertIn("proceed", html)
        self.assertIn("Check criteria: baseline", html)
        self.assertNotIn("<script", html)

    def test_report_escapes_hostile_data(self):
        import yaml
        d = json.loads(json.dumps(FLEET.data))
        d["clusters"][0]["external"]["alerts"] = ["<script>alert(1)</script>"]
        p = Path(self.runs) / "x.yaml"
        p.write_text(yaml.safe_dump(d))
        code, _ = self.cli("check", "--cluster", "dev-1", "--run-id", "xss", fleet=p)
        self.assertEqual(code, 1)
        html = (Path(self.runs) / "xss" / "report.html").read_text()
        self.assertNotIn("<script>alert", html)
        self.assertIn("&lt;script&gt;", html)

    def test_report_exists_for_failed_and_awaiting_runs(self):
        for cmd, cl, extra in (("run", "prod-west", ["--approve"]), ("apply", "dev-1", [])):
            _, _, rd = self.run_cluster(cmd, cl, *extra)
            self.assertTrue((rd / "report.html").exists())


class FaultMatrixTest(Base):
    """Every planted fault stops at the step the ground truth names."""

    def test_each_fault_stops_where_expected(self):
        for f in FLEET.faults:
            with self.subTest(fault=f["id"], cluster=f["cluster"]):
                code, _, rd = self.run_cluster("run", f["cluster"], "--approve")
                self.assertEqual(code, 1)
                self.assertTrue(self.state(rd)["stopped_at"].startswith(f["expect_stop"]),
                                (self.state(rd)["stopped_at"], f["expect_stop"]))

    def test_clean_clusters_complete(self):
        for name in ("dev-1", "preprod-1", "prod-canary", "mgmt-1"):
            with self.subTest(cluster=name):
                code, out, _ = self.run_cluster("run", name, "--approve")
                self.assertEqual(code, 0, out)


class EntryPointTest(Base):
    def test_python_dash_m_exit_codes(self):
        import subprocess
        import sys
        root = Path(__file__).resolve().parent.parent
        base = [sys.executable, "-m", "upgrade_safety", "apply", "--fleet", str(FLEET_PATH), "--cluster", "dev-1",
                "--target", "1.26", "--runs-dir", self.runs]
        no = subprocess.run(base + ["--run-id", "e1"], cwd=root, capture_output=True, text=True)
        self.assertEqual(no.returncode, 2)
        yes = subprocess.run(base + ["--run-id", "e2", "--approve"], cwd=root, capture_output=True, text=True)
        self.assertEqual(yes.returncode, 0, yes.stdout + yes.stderr)
        self.assertTrue((Path(self.runs) / "e2" / "report.html").exists())


class FleetTest(Base):
    def test_fleet_runs_in_order_and_pauses_on_first_failure(self):
        out = io.StringIO()
        code = cli.main(["run", "--fleet", str(FLEET_PATH), "--runs-dir", self.runs, "--approve", "--run-id", "fl"], out)
        text = out.getvalue()
        self.assertNotEqual(code, 0)
        fs = json.loads((Path(self.runs) / "fl" / "fleet.json").read_text())
        self.assertEqual(list(fs["runs"]), ["dev-1", "preprod-1", "prod-canary", "prod-east"])
        self.assertEqual(fs["stopped_at"], "prod-east")
        self.assertNotIn("mgmt-1", fs["runs"])
        self.assertIn("FLEET PAUSED at prod-east", text)
        self.assertTrue((Path(self.runs) / "fl" / "report.html").exists())

    def test_fleet_without_approve_stops_at_first_gate(self):
        out = io.StringIO()
        code = cli.main(["run", "--fleet", str(FLEET_PATH), "--runs-dir", self.runs, "--run-id", "fl2"], out)
        self.assertEqual(code, 2)
        fs = json.loads((Path(self.runs) / "fl2" / "fleet.json").read_text())
        self.assertEqual(list(fs["runs"]), ["dev-1"])

    def test_unknown_cluster_and_bad_fleet(self):
        code, out = self.cli("check", "--cluster", "nope")
        self.assertEqual(code, 2)
        self.assertIn("unknown cluster", out)


if __name__ == "__main__":
    unittest.main()
