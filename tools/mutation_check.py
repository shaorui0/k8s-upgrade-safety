#!/usr/bin/env python3
"""Sanity check that the tests can fail: break one gate at a time, expect the suite to go red.

A gate whose removal leaves the suite green is a gate nobody tests. Files are
restored in a finally block. Exit 0 = every mutation was killed.

Usage: python3 tools/mutation_check.py
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "upgrade_safety"

MUTATIONS = [
    ("raft lag limit 1000 -> 3000", "checks.py", "RAFT_LAG_LIMIT = 1000", "RAFT_LAG_LIMIT = 3000"),
    ("apiserver /readyz probe always true", "probes.py", 'ok = _master(s, a["master"])["readyz"]', "ok = True"),
    ("apiserver LB-membership probe always true", "probes.py",
     'return st == "healthy", f"{a[\'master\']}: apiserver load-balancer', 'return True, f"{a[\'master\']}: apiserver load-balancer'),
    ("next-component guard always passes", "probes.py",
     'ok = m["apiserver"] == t and m["readyz"] and m["lb_member"] == "healthy"', "ok = True"),
    ("step sign-off ignored", "reconcile.py", "if not ctx.approved:", "if False:"),
    ("plan sign-off ignored", "engine.py", "if self.gate_policy == \"manual\" and not self.approve:", "if False:"),
    ("completed steps re-executed on resume", "engine.py", 'if s["status"] == "completed":\n                self.rd.log(f"SKIP',
     'if False:\n                self.rd.log(f"SKIP'),
    ("PDB zero-disruption not a blocker", "probes.py", 'p["current_healthy"] - p["min_available"] <= 0', 'p["current_healthy"] - p["min_available"] < -99'),
    ("drain timeout ignored", "probes.py", 'if n["eviction_s"] > timeout]', "if False]"),
    ("addon order not enforced", "steps.py", "        if i:\n", "        if False:\n"),
    ("CCM rollout health ignored", "executors.py", 'if not a["target_rollout_healthy"]:', "if False:"),
    ("irreversible step runs without backup", "reconcile.py", 'if not step["reversible"]:', "if False:"),
    ("already_done skip disabled", "reconcile.py", 'if "already_done" in step:', "if False:"),
    ("canary widened to the whole first batch", "plan.py", '"nodes": [first[0]]', '"nodes": first'),
    ("quadrant: unhealthy still proceeds", "verify.py", "    if not healthy:\n        decision = \"human\"", "    if False:\n        decision = \"human\""),
    ("baseline regressions ignored", "verify.py", "healthy = not checks.failures(results) and not diff[\"regressions\"]",
     "healthy = not checks.failures(results)"),
    ("serial may exceed quorum", "plan.py", "within = SERIAL <= tolerated", "within = True"),
    ("auto allowed on prod-class clusters", "gate.py", 'if policy == "auto" and cluster_type not in AUTO_ALLOWED_TYPES:', "if False:"),
    ("failed postcheck continues", "gate.py", "    if postcheck_ok:\n        who", "    if True:\n        who"),
    ("auto accepts plan warnings", "gate.py", 'if policy == "auto" and verdict["warnings"]:', "if False:"),
    ("assisted demands a signature", "gate.py", 'return policy == "manual" and step', 'return policy in ("manual", "assisted") and step'),
    ("contract enum not enforced", "contracts/validator.py", 'if "enum" in schema and value not in schema["enum"]:', "if False:"),
    ("contract required not enforced", "contracts/validator.py", 'if key not in value:', "if False:"),
]


def main():
    survivors = []
    for label, fname, old, new in MUTATIONS:
        path = PKG / fname
        original = path.read_text()
        if old not in original:
            print(f"BROKEN  {label}: pattern not found in {fname}")
            survivors.append(label)
            continue
        try:
            path.write_text(original.replace(old, new, 1))
            r = subprocess.run([sys.executable, "-m", "unittest", "discover"], cwd=ROOT, capture_output=True, text=True)
        finally:
            path.write_text(original)
        killed = r.returncode != 0
        print(f"{'killed  ' if killed else 'SURVIVED'} {label}")
        if not killed:
            survivors.append(label)
    print(f"\n{len(MUTATIONS) - len(survivors)}/{len(MUTATIONS)} mutations killed")
    return 1 if survivors else 0


if __name__ == "__main__":
    sys.exit(main())
