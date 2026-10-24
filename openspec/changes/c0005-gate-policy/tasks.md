## 1. Policy
- [ ] 1.1 `gate.py`: policies, auto restriction by cluster type, plan gate, decision table
- [ ] 1.2 engine and CLI: `--gate`, refusal before a run directory exists, policy kept across resume, fleet pause on refusal
- [ ] 1.3 `test_gate.py`: refusal on prod, assisted completes and stops, auto on dev, auto refuses warnings, manual unchanged, evidence and contracts

## 2. Docs
- [ ] 2.1 METHOD gate section, README, REQUIREMENTS R21-R22

## 3. Acceptance
- [ ] 3.1 `python3 -m unittest discover -v` green; mutation check all killed
- [ ] 3.2 demos: auto refused on prod-canary (exit 2), assisted prod-canary completes unattended, assisted stops at prod-north, auto on dev-1
- [ ] 3.3 `check_rules` OK; `openspec validate`
- [ ] 3.4 report, notes, Progress row
