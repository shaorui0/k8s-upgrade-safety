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
    def snap(self, name, target="1.26", mutate=None):
        c = FLEET.cluster(name)
        if mutate:
            mutate(c)
        return checks.snapshot(c, "baseline", target, model.target_ami(FLEET, target))

    def diff(self, name, target="1.26", mutate=None):
        return plan.build_diff(FLEET, self.snap(name, target, mutate), target)

    def test_clean_diff(self):
        d = self.diff("prod-canary")
        self.assertEqual(d["verdict"]["blockers"], [])
        self.assertTrue(d["verdict"]["safe_to_apply"])
        lt = [c for c in d["changes"] if c["target"].startswith("lt/") and c["field"] == "ami_id"]
        self.assertEqual([(c["before"], c["after"]) for c in lt], [("ami-synth-125", "ami-synth-126")])
        b = d["blast_radius"]
        self.assertEqual((b["etcd_members"], b["tolerated_unavailable"], b["serial"], b["worst_case_masters_down"]),
                         (3, 1, 1, 1))
        self.assertTrue(b["within_quorum"])

    def test_reversibility_is_per_change_and_overall(self):
        d = self.diff("prod-canary")
        masters = [c for c in d["changes"] if c["target"].startswith("master/")]
        self.assertEqual(len(masters), 12)               # 3 masters x 4 components
        self.assertTrue(all(not c["reversible"] for c in masters))
        self.assertTrue(all(c["reversible"] for c in d["changes"] if not c["target"].startswith("master/")))
        self.assertFalse(d["reversible"])

    def test_converged_cluster_has_an_empty_reversible_diff(self):
        def done(c):
            for m in c["masters"]:
                for k in ("apiserver", "controller_manager", "scheduler", "kubelet"):
                    m[k] = "1.26"
            c["workers"]["asg"]["ami"] = c["workers"]["asg"]["launch_template"]["ami"] = "ami-synth-126"
            for n in c["workers"]["nodes"]:
                n["ami"], n["kubelet"] = "ami-synth-126", "1.26"
            for a in c["addons"].values():
                a["version"] = "1.26"
        # source minor is derived from the apiserver, so a converged cluster is a hop of zero: blocked, not a no-op
        d = self.diff("dev-1", mutate=done)
        self.assertEqual(d["changes"], [])
        self.assertTrue(d["reversible"])
        self.assertTrue(any("one minor" in b for b in d["verdict"]["blockers"]))

    def test_not_one_minor_is_a_blocker(self):
        d = self.diff("dev-1", target="1.27")
        self.assertTrue(any("one minor" in v for v in d["verdict"]["blockers"]))
        self.assertFalse(d["verdict"]["safe_to_apply"])

    def test_launch_template_may_only_change_ami(self):
        d = self.diff("dev-1", mutate=lambda c: c["workers"]["asg"]["launch_template"].update(
            pending={"instance_type": "m5.2xlarge"}))
        self.assertTrue(any("instance_type" in v and "only the AMI" in v for v in d["verdict"]["blockers"]))

    def test_alignment_reports_drift_before_it_surprises(self):
        def drift(c):
            c["workers"]["nodes"][0]["ami"] = "ami-synth-126"
        d = self.diff("dev-1", mutate=drift)
        self.assertFalse(d["alignment"]["per_asg"][0]["aligned"])
        self.assertTrue(any("disagree" in w for w in d["verdict"]["warnings"]))
        self.assertTrue(self.diff("dev-1")["alignment"]["aligned"])

    def test_batches_stateful_first_alone_and_20_percent(self):
        nodes = [{"name": f"n{i:02d}", "db": None} for i in range(10)]
        self.assertEqual([len(b) for b in plan.make_batches(nodes)], [2] * 5)
        nodes[3]["db"] = "kafka"
        nodes[7]["db"] = "mysql"
        batches = plan.make_batches(nodes)
        self.assertEqual(batches[:2], [["n03"], ["n07"]])
        self.assertTrue(all(len(b) <= 2 for b in batches))

    def test_tiers_canary_is_one_node_then_batches(self):
        nodes = [{"name": f"n{i:02d}", "db": None} for i in range(10)]
        tiers = plan.worker_tiers(nodes)
        self.assertEqual([t["phase"] for t in tiers], ["canary", "batch"] + ["rollout"] * 4)
        self.assertEqual([len(t["nodes"]) for t in tiers], [1, 1, 2, 2, 2, 2])
        self.assertEqual(sorted(sum((t["nodes"] for t in tiers), [])), sorted(n["name"] for n in nodes))

    def test_canary_is_the_first_stateful_node(self):
        d = self.diff("prod-canary")
        tiers = d["blast_radius"]["worker_tiers"]
        self.assertEqual(tiers[0], {"phase": "canary", "nodes": ["prod-canary-w1"]})

    def test_warnings_surface_faults_before_approval(self):
        self.assertTrue(any("PDB" in w for w in self.diff("prod-west")["verdict"]["warnings"]))
        self.assertTrue(any("drain_timeout_s 300s" in w for w in self.diff("prod-eu")["verdict"]["warnings"]))
        self.assertEqual(self.diff("preprod-1")["verdict"]["warnings"], [])

    def test_serial_beyond_quorum_tolerance_is_a_blocker(self):
        old = plan.SERIAL
        plan.SERIAL = 2
        try:
            d = self.diff("dev-1")
        finally:
            plan.SERIAL = old
        self.assertFalse(d["blast_radius"]["within_quorum"])
        self.assertTrue(any("exceeds quorum tolerance" in v for v in d["verdict"]["blockers"]))

    def test_render_mentions_serial_gate_and_layers(self):
        snap = self.snap("prod-canary")
        text = plan.render(plan.build_diff(FLEET, snap, "1.26"), snap)
        self.assertIn("serial=1", text)
        self.assertIn("own sign-off", text)
        self.assertIn("master -> worker -> components", text)
        self.assertIn("canary: prod-canary-w1", text)


if __name__ == "__main__":
    unittest.main()
