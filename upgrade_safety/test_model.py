import tempfile
import unittest
from pathlib import Path

import yaml

from upgrade_safety import model

FLEET = Path(__file__).resolve().parent.parent / "testenv" / "fleet.yaml"


def raw():
    return yaml.safe_load(FLEET.read_text())


class LoadTest(unittest.TestCase):
    def setUp(self):
        self.fleet = model.load_fleet(FLEET)

    def test_shape(self):
        self.assertGreaterEqual(len(self.fleet.names), 5)
        stages = {self.fleet.cluster(n)["stage"] for n in self.fleet.names}
        self.assertEqual(stages, set(model.STAGES))
        types = {self.fleet.cluster(n)["cluster_type"] for n in self.fleet.names}
        self.assertEqual(types, model.CLUSTER_TYPES)

    def test_cluster_is_a_copy(self):
        c = self.fleet.cluster("dev-1")
        c["version"] = "9.9"
        self.assertEqual(self.fleet.cluster("dev-1")["version"], "1.25")

    def test_unknown_cluster(self):
        with self.assertRaises(KeyError):
            self.fleet.cluster("nope")

    def test_order_canary_before_other_prod_and_management_last(self):
        order = self.fleet.ordered_names()
        self.assertEqual(order[0], "dev-1")
        self.assertEqual(order[1], "preprod-1")
        self.assertEqual(order[2], "prod-canary")
        self.assertEqual(order[-1], "mgmt-1")
        self.assertEqual(set(order[3:-1]), {"prod-east", "prod-west", "prod-south", "prod-eu", "prod-north"})

    def test_target_ami(self):
        self.assertEqual(model.target_ami(self.fleet, "1.26"), "ami-synth-126")
        self.assertIsNone(model.target_ami(self.fleet, "1.40"))


class GroundTruthTest(unittest.TestCase):
    """Every planted fault is really present in the data."""

    def setUp(self):
        self.fleet = model.load_fleet(FLEET)

    def test_at_least_four_distinct_fault_kinds(self):
        kinds = {f["kind"] for f in self.fleet.faults}
        self.assertTrue({"raft_lag", "ccm_unhealthy", "pdb_blocks_drain", "slow_eviction"} <= kinds)

    def test_raft_lag_2000(self):
        c = self.fleet.cluster(self._cluster("raft_lag"))
        self.assertEqual(max(model.raft_lag(c["etcd"]).values()), 2000)

    def test_ccm_rollout_unhealthy(self):
        c = self.fleet.cluster(self._cluster("ccm_unhealthy"))
        self.assertFalse(c["addons"]["ccm"]["target_rollout_healthy"])
        self.assertTrue(c["addons"]["ccm"]["healthy"])  # healthy today, unhealthy after the upgrade

    def test_pdb_allows_zero_disruptions(self):
        c = self.fleet.cluster(self._cluster("pdb_blocks_drain"))
        self.assertTrue(any(p["current_healthy"] - p["min_available"] <= 0 for p in c["pdbs"]))

    def test_slow_eviction_without_flag(self):
        c = self.fleet.cluster(self._cluster("slow_eviction"))
        self.assertEqual(c["flags"]["drain_timeout_s"], 300)
        self.assertTrue(any(n["eviction_s"] > 300 for n in c["workers"]["nodes"]))

    def test_flagged_exception_is_a_positive_case(self):
        c = self.fleet.cluster("preprod-1")
        self.assertEqual(c["flags"]["drain_timeout_s"], 600)
        self.assertTrue(any(300 < n["eviction_s"] <= 600 for n in c["workers"]["nodes"]))

    def test_apiserver_not_ready_fault(self):
        c = self.fleet.cluster(self._cluster("apiserver_not_ready"))
        self.assertTrue(any(m["readyz_after_upgrade"] is False for m in c["masters"]))

    def test_clean_clusters_have_no_fault_fields(self):
        for n in ("dev-1", "prod-canary", "mgmt-1"):
            c = self.fleet.cluster(n)
            self.assertEqual(self.fleet.fault_for(n), [])
            self.assertEqual(max(model.raft_lag(c["etcd"]).values()), 80)
            self.assertTrue(all(a["target_rollout_healthy"] for a in c["addons"].values()))

    def _cluster(self, kind):
        return next(f["cluster"] for f in self.fleet.faults if f["kind"] == kind)


class ValidationTest(unittest.TestCase):
    def test_reports_every_problem_at_once(self):
        d = raw()
        d["clusters"][0]["workers"]["asg"]["ami"] = "ami-unknown"
        d["clusters"][1]["etcd"]["leaders"] = ["ghost"]
        problems = model.validate(d)
        self.assertTrue(any("unknown AMI" in p for p in problems))
        self.assertTrue(any("leader ghost" in p for p in problems))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.yaml"
            path.write_text(yaml.safe_dump(d))
            with self.assertRaises(model.FleetError) as cm:
                model.load_fleet(path)
        self.assertIn("unknown AMI", str(cm.exception))
        self.assertIn("leader ghost", str(cm.exception))

    def test_even_master_count(self):
        d = raw()
        d["clusters"][0]["masters"].pop()
        self.assertTrue(any("odd" in p for p in model.validate(d)))

    def test_missing_stage(self):
        d = raw()
        d["clusters"] = [c for c in d["clusters"] if c["stage"] != "management"]
        self.assertTrue(any("no cluster in stage management" in p for p in model.validate(d)))

    def test_pdb_unknown_node(self):
        d = raw()
        d["clusters"][1]["pdbs"][0]["nodes"] = ["nowhere"]
        self.assertTrue(any("unknown node nowhere" in p for p in model.validate(d)))

    def test_valid_fleet_has_no_problems(self):
        self.assertEqual(model.validate(raw()), [])


class ArithmeticTest(unittest.TestCase):
    def test_skew_kubelet(self):
        self.assertTrue(model.skew_ok("1.27", "kubelet", "1.25"))
        self.assertFalse(model.skew_ok("1.27", "kubelet", "1.24"))

    def test_skew_cm_and_scheduler(self):
        self.assertTrue(model.skew_ok("1.26", "controller_manager", "1.25"))
        self.assertFalse(model.skew_ok("1.27", "scheduler", "1.25"))

    def test_nothing_newer_than_apiserver(self):
        for comp in ("kubelet", "controller_manager", "scheduler"):
            self.assertFalse(model.skew_ok("1.25", comp, "1.26"))

    def test_quorum(self):
        self.assertEqual(model.quorum_tolerance(3), 1)
        self.assertEqual(model.quorum_tolerance(5), 2)
        self.assertEqual(model.quorum_tolerance(1), 0)

    def test_minor_rejects_garbage(self):
        with self.assertRaises(ValueError):
            model.minor("two.six")


if __name__ == "__main__":
    unittest.main()
