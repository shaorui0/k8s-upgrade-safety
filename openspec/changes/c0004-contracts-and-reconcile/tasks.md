## 1. Contracts
- [x] 1.1 four schemas + validator (`contracts/`) + validator tests
- [x] 1.2 snapshot with meta/role and the observed fields probes need (`checks.py`)
- [x] 1.3 diff artifact from `plan.py`

## 2. Reconcile
- [x] 2.1 probes (unary and baseline-relative) and assertion evaluation
- [x] 2.2 executor interface, `SimulatedExecutor`, adapter slots
- [x] 2.3 step definitions with reversibility, backup preconditions, blast-radius tiers
- [x] 2.4 reconcile loop, evidence.jsonl, engine driver, report, CLI updated
- [x] 2.5 tests rewritten against new artifacts; new tests for reversibility, executor, canary, schema validation of every run artifact

## 3. Docs
- [x] 3.1 METHOD (reconcile, contracts, reversibility, plane split, tiers, clean-room statement), README, REQUIREMENTS

## 4. Acceptance
- [x] 4.1 `python3 -m unittest discover -v` green; `python3 tools/mutation_check.py` all killed
- [x] 4.2 DoD run on prod-canary; validate a run directory against the four contracts
- [x] 4.3 `check_rules` OK; `openspec validate`
- [x] 4.4 report, notes, Progress row
