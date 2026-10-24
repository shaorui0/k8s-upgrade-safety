## 1. Precondition
- [x] 1.1 worker steps carry the CCM precheck (`steps.py`); executor models the new apiserver breaking the old CCM when the fleet says so
- [x] 1.2 F2 re-planted in the generator and `fleet.yaml`: new shape, new expected stop
- [x] 1.3 tests: F2 stop and untouched workers, mid-layer CCM failure, addon-layer rollout failure still covered, mutation for the precheck

## 2. Docs consistency
- [ ] 2.1 METHOD, testenv README, README, c0002/c0003 descriptions; evidence files annotated, not rewritten

## 3. Acceptance
- [ ] 3.1 `python3 -m unittest discover -v` green; mutation check all killed
- [ ] 3.2 prod-south run: stop at `workers:launch_template`, nothing replaced; `grep` shows no remaining claim that F2 stops at the addon layer
- [ ] 3.3 `check_rules` OK; `openspec validate`
- [ ] 3.4 report, notes, Progress row
