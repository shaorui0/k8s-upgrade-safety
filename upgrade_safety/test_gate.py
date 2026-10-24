import io
import json
import tempfile
import unittest
from pathlib import Path

import yaml

from upgrade_safety import cli, contracts, gate, model
from upgrade_safety.engine import Engine
from upgrade_safety.evidence import RunDir
from upgrade_safety.test_pipeline import FLEET, FLEET_PATH


class GateBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.runs = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def cli(self, *argv, fleet=None):
        out = io.StringIO()
        code = cli.main([argv[0], "--fleet", str(fleet or FLEET_PATH), "--runs-dir", self.runs, *argv[1:]], out)
        return code, out.getvalue()

    def fleet_with(self, name, mutate):
        d = json.loads(json.dumps(FLEET.data))
        mutate(next(c for c in d["clusters"] if c["name"] == name))
        p = Path(self.runs) / f"{name}-mod.yaml"
        p.write_text(yaml.safe_dump(d))
        return p

    def run_dir(self, rid):
        return Path(self.runs) / rid

    def evidence(self, rid):
        return [json.loads(x) for x in (self.run_dir(rid) / "evidence.jsonl").read_text().splitlines()]

    def state(self, rid):
        return json.loads((self.run_dir(rid) / "state.json").read_text())


class PolicyTableTest(unittest.TestCase):
    def test_auto_only_on_low_risk_types(self):
        for ctype, ok in (("dev-staging", True), ("management", True), ("workload", False)):
            with self.subTest(cluster_type=ctype):
                if ok:
                    gate.validate_policy("auto", ctype)
                else:
                    with self.assertRaises(gate.GatePolicyError) as cm:
                        gate.validate_policy("auto", ctype)
                    self.assertIn(ctype, str(cm.exception))

    def test_manual_and_assisted_allowed_everywhere(self):
        for ctype in ("dev-staging", "management", "workload"):
            gate.validate_policy("manual", ctype)
            gate.validate_policy("assisted", ctype)

    def test_unknown_policy(self):
        with self.assertRaises(gate.GatePolicyError):
            gate.validate_policy("yolo", "dev-staging")

    def test_decision_table(self):
        d, o = gate.decide("manual", True, "alice")
        self.assertEqual((d["decision"], d["decided_by"], o), ("continue", "alice", "applied_pass"))
        d, o = gate.decide("manual", False, "alice")
        self.assertEqual((d["decision"], d["decided_by"], o), ("stop", "engine", "halted_by_operator"))
        for pol in ("assisted", "auto"):
            d, o = gate.decide(pol, True, "alice")
            self.assertEqual((d["decision"], d["decided_by"], o), ("continue", "engine", "applied_pass"))
            d, o = gate.decide(pol, False, "alice")
            self.assertEqual((d["decision"], d["decided_by"], o), ("stop", "engine", "stopped_postcheck"))

    def test_plan_gate(self):
        ok = {"safe_to_apply": True, "blockers": [], "warnings": []}
        warn = {"safe_to_apply": True, "blockers": [], "warnings": ["PDB at zero"]}
        bad = {"safe_to_apply": False, "blockers": ["x"], "warnings": []}
        self.assertEqual(gate.plan_gate("manual", ok, False)[:2], (False, True))
        self.assertEqual(gate.plan_gate("manual", ok, True)[:2], (True, False))
        self.assertTrue(gate.plan_gate("assisted", warn, False)[0])
        self.assertFalse(gate.plan_gate("auto", warn, False)[0])
        self.assertFalse(gate.plan_gate("assisted", bad, True)[0])

    def test_signoff_only_under_manual(self):
        step = {"gate": {"signoff": True}}
        self.assertTrue(gate.needs_signoff("manual", step))
        self.assertFalse(gate.needs_signoff("assisted", step))
        self.assertFalse(gate.needs_signoff("auto", step))
        self.assertFalse(gate.needs_signoff("manual", {"gate": {"signoff": False}}))


class AutoOnProdIsRefusedTest(GateBase):
    def test_refused_before_a_run_directory_exists(self):
        for cluster in ("prod-canary", "prod-east", "prod-north"):
            with self.subTest(cluster=cluster):
                code, out = self.cli("run", "--cluster", cluster, "--gate", "auto", "--run-id", f"r-{cluster}")
                self.assertEqual(code, 2)
                self.assertIn("REFUSED", out)
                self.assertIn("'workload'", out)
                self.assertFalse(self.run_dir(f"r-{cluster}").exists())

    def test_engine_constructor_refuses_too(self):
        with self.assertRaises(gate.GatePolicyError):
            Engine(FLEET, RunDir(self.runs, "direct"), cluster="prod-canary", target="1.26", gate_policy="auto")

    def test_check_and_plan_are_refused_too(self):
        for cmd in ("check", "plan", "apply"):
            code, _ = self.cli(cmd, "--cluster", "prod-canary", "--gate", "auto")
            self.assertEqual(code, 2)

    def test_allowed_on_dev_and_management_unattended(self):
        for cluster in ("dev-1", "preprod-1", "mgmt-1"):
            with self.subTest(cluster=cluster):
                code, out = self.cli("run", "--cluster", cluster, "--gate", "auto", "--run-id", f"a-{cluster}")
                self.assertEqual(code, 0, out)
                log = (self.run_dir(f"a-{cluster}") / "execution.log").read_text()
                self.assertNotIn("SIGNOFF", log)
                self.assertTrue(all(e["gate_decision"]["policy"] == "auto" for e in self.evidence(f"a-{cluster}")))

    def test_fleet_with_auto_pauses_at_the_first_prod_class_cluster(self):
        out = io.StringIO()
        code = cli.main(["run", "--fleet", str(FLEET_PATH), "--runs-dir", self.runs, "--gate", "auto", "--run-id", "fl"], out)
        self.assertEqual(code, 2)
        fs = json.loads((self.run_dir("fl") / "fleet.json").read_text())
        self.assertEqual([(n, r["status"]) for n, r in fs["runs"].items()],
                         [("dev-1", "complete"), ("preprod-1", "complete"), ("prod-canary", "refused")])
        self.assertEqual(fs["stopped_at"], "prod-canary")
        self.assertNotIn("mgmt-1", fs["runs"])
        self.assertIn("FLEET PAUSED at prod-canary", out.getvalue())


class AssistedTest(GateBase):
    def test_completes_a_prod_class_cluster_without_a_signature(self):
        code, out = self.cli("run", "--cluster", "prod-canary", "--gate", "assisted", "--run-id", "as")
        self.assertEqual(code, 0, out)
        log = (self.run_dir("as") / "execution.log").read_text()
        self.assertNotIn("SIGNOFF", log)
        self.assertIn("GATE plan passed by the engine (assisted)", log)
        recs = self.evidence("as")
        self.assertEqual({r["gate_decision"]["policy"] for r in recs}, {"assisted"})
        self.assertEqual({r["gate_decision"]["decided_by"] for r in recs}, {"engine"})
        self.assertEqual({r["outcome"] for r in recs}, {"applied_pass"})
        contracts.validate_jsonl("evidence", (self.run_dir("as") / "evidence.jsonl").read_text())

    def test_stops_at_the_failed_postcheck_and_nothing_after_it_runs(self):
        code, out = self.cli("run", "--cluster", "prod-north", "--gate", "assisted", "--run-id", "asn")
        self.assertEqual(code, 1)
        st = self.state("asn")
        self.assertEqual(st["stopped_at"], "master:prod-north-m2:apiserver_ready")
        last = self.evidence("asn")[-1]
        self.assertEqual((last["outcome"], last["gate_decision"]["decision"], last["gate_decision"]["decided_by"]),
                         ("stopped_postcheck", "stop", "engine"))
        steps = {s["id"]: s["status"] for s in st["steps"]}
        self.assertEqual(steps["master:prod-north-m2:controller_manager"], "pending")
        self.assertEqual(steps["master:prod-north-m3:apiserver"], "pending")
        w = {m["name"]: m for m in json.loads((self.run_dir("asn") / "cluster.json").read_text())["masters"]}
        self.assertEqual(w["prod-north-m2"]["controller_manager"], "1.25")

    def test_manual_same_failure_is_halted_by_operator(self):
        self.cli("run", "--cluster", "prod-north", "--approve", "--run-id", "man")
        self.assertEqual(self.evidence("man")[-1]["outcome"], "halted_by_operator")

    def test_assisted_ignores_approve_and_manual_does_not_run_without_it(self):
        code, _ = self.cli("run", "--cluster", "dev-1", "--gate", "assisted", "--approve", "--run-id", "both")
        self.assertEqual(code, 0)
        code, _ = self.cli("run", "--cluster", "dev-1", "--run-id", "m")
        self.assertEqual(code, 2)

    def test_precheck_failures_still_stop_under_assisted(self):
        code, _ = self.cli("run", "--cluster", "prod-west", "--gate", "assisted", "--run-id", "w")
        self.assertEqual(code, 1)
        self.assertEqual(self.evidence("w")[-1]["outcome"], "stopped_precheck")
        code, _ = self.cli("run", "--cluster", "prod-east", "--gate", "assisted", "--run-id", "e")
        self.assertEqual(self.state("e")["stopped_at"], "check")

    def test_policy_is_kept_across_resume(self):
        self.cli("run", "--cluster", "dev-1", "--gate", "assisted", "--run-id", "k", "--interrupt-at", "master:dev-1-m2:apiserver")
        code, _ = self.cli("run", "--cluster", "dev-1", "--resume", "k")
        self.assertEqual(code, 0)
        self.assertEqual({r["gate_decision"]["policy"] for r in self.evidence("k")}, {"assisted"})
        self.assertEqual(self.state("k")["gate_policy"], "assisted")

    def test_steps_json_records_the_policy(self):
        self.cli("plan", "--cluster", "dev-1", "--gate", "assisted", "--run-id", "p")
        defs = json.loads((self.run_dir("p") / "steps.json").read_text())
        self.assertEqual({d["gate"]["policy"] for d in defs}, {"assisted"})


class AutoTest(GateBase):
    def test_auto_stops_on_a_failed_postcheck_unattended(self):
        p = self.fleet_with("dev-1", lambda c: c["masters"][1].update(readyz_after_upgrade=False))
        code, out = self.cli("run", "--cluster", "dev-1", "--gate", "auto", "--run-id", "af", fleet=p)
        self.assertEqual(code, 1)
        self.assertEqual(self.evidence("af")[-1]["outcome"], "stopped_postcheck")
        self.assertEqual(self.state("af")["stopped_at"], "master:dev-1-m2:apiserver_ready")

    def test_auto_refuses_a_plan_with_warnings_assisted_accepts_it(self):
        p = self.fleet_with("dev-1", lambda c: c["workers"]["nodes"][2].update(eviction_s=540))
        code, out = self.cli("run", "--cluster", "dev-1", "--gate", "auto", "--run-id", "aw", fleet=p)
        self.assertEqual(code, 1)
        self.assertEqual(self.state("aw")["stopped_at"], "gate:plan")
        self.assertIn("warnings nobody will read", self.state("aw")["reason"])
        self.assertEqual(self.evidence("aw")[-1]["outcome"], "stopped_precheck")
        code, out = self.cli("run", "--cluster", "dev-1", "--gate", "assisted", "--run-id", "asw", fleet=p)
        self.assertEqual(code, 1)
        self.assertTrue(self.state("asw")["stopped_at"].startswith("workers:"))      # got past the plan gate

    def test_manual_without_approve_stays_awaiting(self):
        code, _ = self.cli("apply", "--cluster", "dev-1", "--run-id", "mw")
        self.assertEqual(code, 2)
        self.assertEqual(self.state("mw")["status"], "awaiting_approval")


if __name__ == "__main__":
    unittest.main()
