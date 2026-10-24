import unittest
from pathlib import Path

from upgrade_safety import checks, model, plan

FLEET = model.load_fleet(Path(__file__).resolve().parent.parent / "testenv" / "fleet.yaml")


def results(c):
    return {r["id"]: r for r in checks.evaluate(checks.snapshot(c))}


class CheckTest(unittest.TestCase):
    def test_clean_cluster_passes_all_eight(self):
        r = results(FLEET.cluster("prod-canary"))
        self.assertEqual(len(r), 8)
        self.assertTrue(all(x["ok"] for x in r.values()), r)

    def test_raft_lag_2000_fails(self):
        r = results(FLEET.cluster("prod-east"))
        self.assertFalse(r["etcd_raft_lag"]["ok"])
        self.assertIn("2000", r["etcd_raft_lag"]["detail"])
        self.assertEqual([x["id"] for x in checks.failures(r.values())], ["etcd_raft_lag"])

    def test_raft_lag_boundary(self):
        c = FLEET.cluster("dev-1")
        top = c["etcd"]["members"][0]["raft_index"]
        c["etcd"]["members"][2]["raft_index"] = top - 1000
        self.assertTrue(results(c)["etcd_raft_lag"]["ok"])
        c["etcd"]["members"][2]["raft_index"] = top - 1001
        self.assertFalse(results(c)["etcd_raft_lag"]["ok"])

    def test_even_members_offline_and_two_leaders(self):
        c = FLEET.cluster("dev-1")
        c["etcd"]["members"][1]["online"] = False
        c["etcd"]["leaders"] = ["dev-1-m1", "dev-1-m2"]
        r = results(c)
        self.assertFalse(r["etcd_all_online"]["ok"])
        self.assertFalse(r["etcd_single_leader"]["ok"])

    def test_node_not_ready_and_kube_system(self):
        c = FLEET.cluster("dev-1")
        c["workers"]["nodes"][0]["ready"] = False
        c["kube_system"]["pods_running"] = 13
        r = results(c)
        self.assertFalse(r["nodes_ready"]["ok"])
        self.assertFalse(r["kube_system_healthy"]["ok"])

    def test_external_alert_fails(self):
        c = FLEET.cluster("dev-1")
        c["external"]["alerts"] = ["DiskPressure"]
        self.assertFalse(results(c)["external_alerts_zero"]["ok"])

    def test_monitor_disagreement_fails(self):
        c = FLEET.cluster("dev-1")
        c["monitor"]["nodes_ready"] -= 1
        r = results(c)
        self.assertFalse(r["monitor_cross_check"]["ok"])
        self.assertIn("baseline itself may be wrong", r["monitor_cross_check"]["detail"])


class PlanTest(unittest.TestCase):
    def plan(self, name, target="1.26", mutate=None):
        c = FLEET.cluster(name)
        if mutate:
            mutate(c)
        return plan.build_plan(FLEET, c, target)

    def test_clean_plan(self):
        p = self.plan("prod-canary")
        self.assertEqual(p["violations"], [])
        self.assertEqual(p["workers"]["ami_diff"]["to"], "ami-synth-126")
        self.assertEqual(p["workers"]["launch_template_diff"]["changed"], {"ami": ["ami-synth-125", "ami-synth-126"]})
        b = p["blast_radius"]
        self.assertEqual((b["etcd_members"], b["tolerated_unavailable"], b["serial"], b["worst_case_masters_down"]),
                         (3, 1, 1, 1))
        self.assertTrue(b["within_quorum"])

    def test_not_one_minor_is_a_violation(self):
        p = self.plan("dev-1", target="1.27")
        self.assertTrue(any("one minor" in v for v in p["violations"]))

    def test_launch_template_may_only_change_ami(self):
        p = self.plan("dev-1", mutate=lambda c: c["workers"]["asg"]["launch_template"].update(
            pending={"instance_type": "m5.2xlarge"}))
        self.assertTrue(any("instance_type" in v and "only the AMI" in v for v in p["violations"]))

    def test_batches_stateful_first_alone_and_20_percent(self):
        c = FLEET.cluster("prod-canary")
        batches = plan.make_batches(c)
        self.assertEqual(batches[0], ["prod-canary-w1"])
        self.assertEqual(batches[1], ["prod-canary-w2"])
        self.assertTrue(all(len(b) <= 1 for b in batches))  # 20% of 5 nodes = 1
        big = FLEET.cluster("dev-1")
        big["workers"]["nodes"] = [dict(big["workers"]["nodes"][0], name=f"n{i}", db=None) for i in range(10)]
        self.assertEqual([len(b) for b in plan.make_batches(big)], [2] * 5)

    def test_warnings_surface_faults_before_approval(self):
        self.assertTrue(any("PDB" in w for w in self.plan("prod-west")["warnings"]))
        self.assertTrue(any("drain_timeout_s 300s" in w for w in self.plan("prod-eu")["warnings"]))
        self.assertEqual(self.plan("preprod-1")["warnings"], [])

    def test_serial_beyond_quorum_tolerance_is_a_violation(self):
        old = plan.SERIAL
        plan.SERIAL = 2
        try:
            p = self.plan("dev-1")
        finally:
            plan.SERIAL = old
        self.assertFalse(p["blast_radius"]["within_quorum"])
        self.assertTrue(any("exceeds quorum tolerance" in v for v in p["violations"]))

    def test_render_mentions_serial_and_gate(self):
        text = plan.render(self.plan("prod-canary"))
        self.assertIn("serial=1", text)
        self.assertIn("own sign-off", text)


if __name__ == "__main__":
    unittest.main()
