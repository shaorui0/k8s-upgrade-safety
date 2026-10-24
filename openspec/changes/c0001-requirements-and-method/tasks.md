## 1. Scan tool
- [x] 1.1 `tools/check_rules.py`: required files, generic + local leak patterns, file:line output
- [x] 1.2 `tools/test_check_rules.py`: planted leak fails, clean tree passes, missing doc fails

## 2. Documents
- [x] 2.1 `docs/REQUIREMENTS.md` (goal, requirement table, constraints)
- [x] 2.2 `docs/METHOD.md` (state machine, step table, apiserver gate, quadrant, rollback, fleet order, hard parts)
- [x] 2.3 `.claude/skills/upgrade-change-loop/SKILL.md`
- [x] 2.4 `README.md` skeleton with Progress table

## 3. Acceptance
- [x] 3.1 `python3 -m unittest discover -s tools -v` green
- [x] 3.2 `python3 tools/check_rules.py` prints OK; `grep -ri` for employer and alias strings returns 0 hits
- [x] 3.3 `openspec validate c0001-requirements-and-method` passes
- [x] 3.4 HTML report and blog note exist; Progress row appended
