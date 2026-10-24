## 1. Core
- [x] 1.1 `evidence.py`, `checks.py`, `plan.py` + tests
- [x] 1.2 `verify.py`, `engine.py`, `report.py`, `cli.py`, `__main__.py` + tests

## 2. Docs
- [x] 2.1 README Quickstart and layout

## 3. Acceptance
- [x] 3.1 `python3 -m unittest discover -v` green (raft lag, approve gate, CCM stop, PDB no force, quadrants, resume, readyz gate)
- [x] 3.2 `python3 -m upgrade_safety run --fleet testenv/fleet.yaml --cluster prod-canary --target 1.26 --approve` completes and writes `runs/<id>/report.html`
- [x] 3.3 every planted fault stops at its expected step (fault matrix run)
- [x] 3.4 fleet run stops at first failure; `check_rules` OK; `openspec validate`
- [x] 3.5 `tools/mutation_check.py`: 13 gate mutations, all killed (found two untested gates during acceptance; tests added)
- [x] 3.6 report, notes, Progress row
