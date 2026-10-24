## 1. Core
- [ ] 1.1 `evidence.py`, `checks.py`, `plan.py` + tests
- [ ] 1.2 `verify.py`, `engine.py`, `report.py`, `cli.py`, `__main__.py` + tests

## 2. Docs
- [ ] 2.1 README Quickstart and layout

## 3. Acceptance
- [ ] 3.1 `python3 -m unittest discover -v` green (raft lag, approve gate, CCM stop, PDB no force, quadrants, resume, readyz gate)
- [ ] 3.2 `python3 -m upgrade_safety run --fleet testenv/fleet.yaml --cluster prod-canary --target 1.26 --approve` completes and writes `runs/<id>/report.html`
- [ ] 3.3 every planted fault stops at its expected step (fault matrix run)
- [ ] 3.4 fleet run stops at first failure; `check_rules` OK; `openspec validate`
- [ ] 3.5 report, notes, Progress row
