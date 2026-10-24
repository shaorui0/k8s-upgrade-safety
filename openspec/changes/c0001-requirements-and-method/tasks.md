## 1. Scan tool
- [ ] 1.1 `tools/check_rules.py`: required files, generic + local leak patterns, file:line output
- [ ] 1.2 `tools/test_check_rules.py`: planted leak fails, clean tree passes, missing doc fails

## 2. Documents
- [ ] 2.1 `docs/REQUIREMENTS.md` (goal, requirement table, constraints)
- [ ] 2.2 `docs/METHOD.md` (state machine, step table, apiserver gate, quadrant, rollback, fleet order, hard parts)
- [ ] 2.3 `.claude/skills/upgrade-change-loop/SKILL.md`
- [ ] 2.4 `README.md` skeleton with Progress table

## 3. Acceptance
- [ ] 3.1 `python3 -m unittest discover -s tools -v` green
- [ ] 3.2 `python3 tools/check_rules.py` prints OK; `grep -ri` for employer and alias strings returns 0 hits
- [ ] 3.3 `openspec validate c0001-requirements-and-method` passes
- [ ] 3.4 HTML report and blog note exist; Progress row appended
