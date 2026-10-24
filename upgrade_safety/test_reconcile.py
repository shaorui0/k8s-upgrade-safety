import io
import json
import tempfile
import unittest
from pathlib import Path

from upgrade_safety import cli, contracts, model, probes, steps
from upgrade_safety.engine import Engine
from upgrade_safety.evidence import RunDir
from upgrade_safety.executors import Executor, SimulatedExecutor
from upgrade_safety.test_pipeline import FLEET, FLEET_PATH, make_engine, run_def


class TmpBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.runs = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def cli(self, *argv):
        out = io.StringIO()
        code = cli.main([argv[0], "--fleet", str(FLEET_PATH), "--runs-dir", self.runs, *argv[1:]], out)
        return code, out.getvalue()


class ReversibilityTest(TmpBase):
    def test_irreversible_step_without_backup_is_refused_and_executor_not_called(self):
        eng = make_engine(self.runs, "nobackup")
        calls = []
        real = eng.ex.execute
        eng.ex.execute = lambda step: calls.append(step["id"]) or real(step)
        out = run_def(eng, "master:dev-1-m1:apiserver")
        self.assertEqual(out["outcome"], "stopped_precheck")
        self.assertIn("backup precondition 'etcd-snapshot-fresh' not satisfied", out["reason"])
        self.assertEqual(calls, [])
        self.assertEqual(eng.c["masters"][0]["apiserver"], "1.25")
        ev = out["evidence"]
        self.assertEqual(ev["gate_decision"]["decision"], "stop")
        self.assertEqual([a["phase"] for a in ev["assertions"]], ["backup"])

    def test_with_a_fresh_snapshot_the_same_step_runs(self):
        eng = make_engine(self.runs, "backup")
        run_def(eng, "snapshot")
        out = run_def(eng, "master:dev-1-m1:apiserver")
        self.assertEqual(out["outcome"], "applied_pass")
        self.assertEqual(eng.c["masters"][0]["apiserver"], "1.26")

    def test_a_stale_snapshot_does_not_count(self):
        eng = make_engine(self.runs, "stale")
        run_def(eng, "snapshot")
        for m in eng.c["etcd"]["members"]:
            m["raft_index"] += 5000                       # cluster moved on far past the snapshot
        out = run_def(eng, "master:dev-1-m1:apiserver")
        self.assertEqual(out["outcome"], "stopped_precheck")
        self.assertIn("behind the live cluster", out["reason"])

    def test_every_step_declares_reversibility_and_irreversible_ones_name_a_backup(self):
        eng = make_engine(self.runs, "defs")
        for d in eng.defs.values():
            self.assertIsInstance(d["reversible"], bool)
            if not d["reversible"]:
                self.assertIn(d["backup_precondition"], probes.NAMED)
                self.assertEqual(d["layer"], "master")
        irrev = {d["id"].split(":")[-1] for d in eng.defs.values() if not d["reversible"]}
        self.assertEqual(irrev, {"apiserver", "controller_manager", "scheduler", "kubelet"})
        self.assertTrue(all(d["reversible"] for d in eng.defs.values() if d["layer"] in ("worker", "components")))

    def test_snapshot_is_one_instance_of_the_rule_not_a_special_case(self):
        eng = make_engine(self.runs, "inst")
        self.assertTrue(eng.defs["snapshot"]["reversible"])
        self.assertEqual(eng.defs["master:dev-1-m1:apiserver"]["backup_precondition"], "etcd-snapshot-fresh")


class SignoffTest(TmpBase):
    def test_step_waits_for_a_signature_and_does_not_execute(self):
        eng = make_engine(self.runs, "unsigned", approve=False)
        run_def(eng, "snapshot")                                   # no sign-off needed for the backup
        out = run_def(eng, "master:dev-1-m1:apiserver")
        self.assertEqual((out["outcome"], out["awaiting"]), ("halted_by_operator", True))
        self.assertEqual(eng.c["masters"][0]["apiserver"], "1.25")
        self.assertEqual(out["evidence"]["gate_decision"]["decision"], "stop")

    def test_signed_step_executes(self):
        eng = make_engine(self.runs, "signed", approve=True)
        run_def(eng, "snapshot")
        self.assertEqual(run_def(eng, "master:dev-1-m1:apiserver")["outcome"], "applied_pass")


class ExecutorSeamTest(TmpBase):
    def test_unimplemented_adapters_refuse_loudly(self):
        for name in ("terraform", "ansible", "aws"):
            with self.subTest(adapter=name):
                with self.assertRaises(NotImplementedError) as cm:
                    Engine(FLEET, RunDir(self.runs, f"x-{name}"), cluster="dev-1", target="1.26", executor=name)
                self.assertIn(f"no {name} adapter", str(cm.exception))

    def test_cli_reports_missing_adapter(self):
        code, out = self.cli("check", "--cluster", "dev-1", "--executor", "terraform", "--run-id", "tf")
        self.assertEqual(code, 2)
        self.assertIn("no terraform adapter", out)

    def test_engine_acts_only_through_the_executor(self):
        class Recording(SimulatedExecutor):
            def __init__(self, *a):
                super().__init__(*a)
                self.seen = []

            def execute(self, step):
                self.seen.append(step["id"])
                return super().execute(step)
        eng = make_engine(self.runs, "rec")
        eng.ex = Recording(eng.c, "1.26", "ami-synth-126")
        self.assertIsInstance(eng.ex, Executor)
        eng.run("apply")
        self.assertIn("master:dev-1-m3:kubelet", eng.ex.seen)
        self.assertEqual(eng.state["status"], "complete")
        self.assertEqual(eng.c["workers"]["asg"]["ami"], "ami-synth-126")


class ContractsOnRunsTest(TmpBase):
    def validate_run(self, rd):
        for f in (rd / "snapshots").rglob("*.json"):
            contracts.validate("snapshot", json.loads(f.read_text()))
        if (rd / "diff.json").exists():
            contracts.validate("diff", json.loads((rd / "diff.json").read_text()))
        for s in json.loads((rd / "steps.json").read_text()):
            contracts.validate("step", s)
        return contracts.validate_jsonl("evidence", (rd / "evidence.jsonl").read_text())

    def test_complete_run_artifacts_conform(self):
        code, _ = self.cli("run", "--cluster", "prod-canary", "--approve", "--run-id", "ok")
        self.assertEqual(code, 0)
        recs = self.validate_run(Path(self.runs) / "ok")
        ids = [r["step_id"] for r in recs]
        for sid in json.loads((Path(self.runs) / "ok" / "steps.json").read_text()):
            self.assertIn(sid["id"], ids)
        self.assertEqual({r["outcome"] for r in recs}, {"applied_pass"})
        roles = {json.loads(f.read_text())["meta"]["role"] for f in (Path(self.runs) / "ok" / "snapshots").rglob("*.json")}
        self.assertEqual(roles, {"baseline", "postcheck"})

    def test_failed_and_awaiting_runs_conform_too(self):
        for rid, cluster, extra in (("f1", "prod-west", ["--approve"]), ("f2", "prod-north", ["--approve"]),
                                    ("f3", "prod-east", ["--approve"]), ("f4", "dev-1", [])):
            self.cli("run", "--cluster", cluster, *extra, "--run-id", rid)
            self.validate_run(Path(self.runs) / rid)

    def test_evidence_outcomes_for_each_kind_of_stop(self):
        def last(rid):
            return [json.loads(x) for x in (Path(self.runs) / rid / "evidence.jsonl").read_text().splitlines()][-1]
        self.cli("run", "--cluster", "prod-west", "--approve", "--run-id", "w")
        self.cli("run", "--cluster", "prod-north", "--approve", "--run-id", "n")
        self.cli("run", "--cluster", "prod-east", "--approve", "--run-id", "e")
        self.cli("run", "--cluster", "dev-1", "--run-id", "g")
        self.assertEqual((last("w")["outcome"], last("w")["step_id"]), ("stopped_precheck", "workers:canary"))
        self.assertEqual((last("n")["outcome"], last("n")["step_id"]), ("halted_by_operator", "master:prod-north-m2:apiserver_ready"))
        self.assertEqual((last("e")["outcome"], last("e")["step_id"]), ("stopped_precheck", "check"))
        self.assertEqual((last("g")["outcome"], last("g")["step_id"]), ("halted_by_operator", "gate:plan"))
        failed = [a["id"] for a in last("w")["assertions"] if not a["passed"]]
        self.assertEqual(failed, ["no-pdb-block"])

    def test_evidence_is_append_only_across_resume(self):
        self.cli("run", "--cluster", "dev-1", "--approve", "--run-id", "ap", "--interrupt-at", "master:dev-1-m2:apiserver")
        path = Path(self.runs) / "ap" / "evidence.jsonl"
        before = path.read_text().splitlines()
        self.cli("run", "--cluster", "dev-1", "--approve", "--resume", "ap")
        after = path.read_text().splitlines()
        self.assertEqual(after[:len(before)], before)
        self.assertGreater(len(after), len(before))

    def test_converged_skip_is_recorded_on_resume_of_a_failed_step(self):
        self.cli("run", "--cluster", "prod-south", "--approve", "--run-id", "cs")
        self.cli("run", "--cluster", "prod-south", "--approve", "--resume", "cs")
        recs = [json.loads(x) for x in (Path(self.runs) / "cs" / "evidence.jsonl").read_text().splitlines()]
        self.assertEqual([r["outcome"] for r in recs if r["step_id"] == "workers:launch_template"], ["stopped_precheck"] * 2)

    def test_snapshot_role_enum_rejects_other_roles(self):
        self.cli("check", "--cluster", "dev-1", "--run-id", "r")
        snap = json.loads((Path(self.runs) / "r" / "snapshots" / "baseline.json").read_text())
        snap["meta"]["role"] = "whenever"
        with self.assertRaises(contracts.ContractError):
            contracts.validate("snapshot", snap)

    def test_doctored_artifact_is_caught(self):
        self.cli("check", "--cluster", "dev-1", "--run-id", "d")
        snap = json.loads((Path(self.runs) / "d" / "snapshots" / "baseline.json").read_text())
        del snap["etcd"]["max_lag"]
        with self.assertRaises(contracts.ContractError) as cm:
            contracts.validate("snapshot", snap)
        self.assertIn("max_lag", str(cm.exception))


class ProbeTest(unittest.TestCase):
    def snap(self):
        from upgrade_safety import checks
        return checks.snapshot(FLEET.cluster("dev-1"), "baseline", "1.26", "ami-synth-126")

    def test_target_tokens_resolve_from_the_snapshot(self):
        a = {"id": "x", "probe": "master.component_version", "args": {"master": "dev-1-m1", "component": "apiserver"},
             "op": "==", "expected": "$target", "severity": "block", "why": "w"}
        s = self.snap()
        self.assertFalse(probes.evaluate(a, s, s, "precheck")["passed"])
        s["masters"][0]["apiserver"] = "1.26"
        self.assertTrue(probes.evaluate(a, s, s, "precheck")["passed"])

    def test_unknown_probe_is_an_error_not_a_pass(self):
        s = self.snap()
        with self.assertRaises(KeyError):
            probes.evaluate({"id": "x", "probe": "nope", "op": "==", "expected": 1, "severity": "block", "why": "w"}, s, s, "precheck")

    def test_baseline_relative_probe_ignores_pre_existing_breakage(self):
        b = self.snap()
        b["alerts"] = ["OldAlert"]
        a = json.loads(json.dumps(b))
        a["alerts"] = ["OldAlert", "NewAlert"]
        r = probes.evaluate({"id": "x", "probe": "alerts.new_count", "op": "==", "expected": 0, "severity": "block", "why": "w"},
                            b, a, "postcheck")
        self.assertFalse(r["passed"])
        self.assertEqual(r["detail"], "NewAlert")


class TierTest(TmpBase):
    def test_ten_stateless_workers_canary_then_batches_of_two(self):
        d = json.loads(json.dumps(FLEET.data))
        c = next(x for x in d["clusters"] if x["name"] == "dev-1")
        c["workers"]["nodes"] = [dict(c["workers"]["nodes"][0], name=f"dev-1-w{i:02d}", db=None, eviction_s=30) for i in range(10)]
        c["workers"]["asg"]["desired"] = 10
        c["monitor"]["nodes_ready"] = 13
        import yaml
        p = Path(self.runs) / "ten.yaml"
        p.write_text(yaml.safe_dump(d))
        fleet = model.load_fleet(p)
        eng = Engine(fleet, RunDir(self.runs, "ten"), cluster="dev-1", target="1.26", approve=True)
        sizes = [len(t["nodes"]) for t in eng.state["tiers"]]
        self.assertEqual(sizes, [1, 1, 2, 2, 2, 2])
        eng.run("run")
        self.assertEqual(eng.state["status"], "complete")


class StepSchemaTest(unittest.TestCase):
    def test_built_steps_validate(self):
        from upgrade_safety import checks, plan
        snap = checks.snapshot(FLEET.cluster("prod-canary"), "baseline", "1.26", "ami-synth-126")
        defs = steps.build_steps(snap, plan.worker_tiers(snap["workers"]["nodes"]))
        self.assertEqual(defs[0]["id"], "snapshot")
        self.assertEqual([d["layer"] for d in defs if d["layer"] != "master"][0], "worker")
        layers = [d["layer"] for d in defs]
        self.assertEqual(layers, sorted(layers, key=["master", "worker", "components"].index))


if __name__ == "__main__":
    unittest.main()
