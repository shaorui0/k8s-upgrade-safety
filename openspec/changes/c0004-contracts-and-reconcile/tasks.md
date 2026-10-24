## 1. Contracts
- [ ] 1.1 four schemas + validator (`contracts/`) + validator tests
- [ ] 1.2 snapshot with meta/role and the observed fields probes need (`checks.py`)
- [ ] 1.3 diff artifact from `plan.py`

## 2. Reconcile
- [ ] 2.1 probes (unary and baseline-relative) and assertion evaluation
- [ ] 2.2 executor interface, `SimulatedExecutor`, adapter slots
- [ ] 2.3 step definitions with reversibility, backup preconditions, blast-radius tiers
- [ ] 2.4 reconcile loop, evidence.jsonl, engine driver, report, CLI updated
- [ ] 2.5 tests rewritten against new artifacts; new tests for reversibility, executor, canary, schema validation of every run artifact

## 3. Docs
- [ ] 3.1 METHOD (reconcile, contracts, reversibility, plane split, tiers, clean-room statement), README, REQUIREMENTS

## 4. Acceptance
- [ ] 4.1 `python3 -m unittest discover -v` green; `python3 tools/mutation_check.py` all killed
- [ ] 4.2 DoD run on prod-canary; validate a run directory against the four contracts
- [ ] 4.3 `check_rules` OK; `openspec validate`
- [ ] 4.4 report, notes, Progress row
