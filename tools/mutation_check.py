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
    ("apiserver /readyz gate removed", "engine.py", 'if not m["readyz"]:', "if False:"),
    ("apiserver LB-membership gate removed", "engine.py", 'if m["lb_member"] != "healthy":', "if False:"),
    ("next-component guard removed",
     "engine.py", 'if not (m["apiserver"] == T and m["readyz"] and m["lb_member"] == "healthy"):', "if False:"),
    ("approval gate removed", "engine.py", "if not self.approve:", "if False:"),
    ("completed steps re-executed on resume", "engine.py", 'if s["status"] == "completed":\n                self.rd.log(f"SKIP',
     'if False:\n                self.rd.log(f"SKIP'),
    ("PDB check removed from drain", "engine.py", "for p in planmod.blocking_pdbs(c, n[\"name\"]):", "for p in []:"),
    ("drain timeout ignored", "engine.py", 'if n["eviction_s"] > timeout:', "if False:"),
    ("addon order not enforced", "engine.py", "if prev and not self.completed", "if False and not self.completed"),
    ("CCM rollout health ignored", "engine.py", 'if not a["target_rollout_healthy"]:', "if False:"),
    ("quadrant: unhealthy still proceeds", "verify.py", "    if not healthy:\n        decision = \"human\"", "    if False:\n        decision = \"human\""),
    ("baseline regressions ignored", "verify.py", "healthy = not checks.failures(results) and not diff[\"regressions\"]",
     "healthy = not checks.failures(results)"),
    ("serial may exceed quorum", "plan.py", "if not blast[\"within_quorum\"]:", "if False:"),
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
