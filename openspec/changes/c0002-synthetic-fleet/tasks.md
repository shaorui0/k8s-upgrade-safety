## 1. Fleet
- [x] 1.1 `testenv/gen_fleet.py` and generated `testenv/fleet.yaml` (9 clusters, 5 faults, ground truth)
- [ ] 1.2 `testenv/README.md`

## 2. Model
- [x] 2.1 `upgrade_safety/model.py` (load, validate, skew, quorum, ordering, target AMI)
- [x] 2.2 `upgrade_safety/test_model.py`

## 3. Acceptance
- [ ] 3.1 `python3 -m unittest discover -v` green
- [ ] 3.2 `python3 -c` loader prints cluster table; fault ground truth matches data
- [ ] 3.3 `python3 tools/check_rules.py` OK; `openspec validate c0002-synthetic-fleet`
- [ ] 3.4 report, notes, Progress row
