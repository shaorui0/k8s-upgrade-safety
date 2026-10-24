## Why

The upgrade safety system I built and ran is only described in prose (a project page and a blog post). Prose cannot be run, and nobody can check that the gates in it are consistent. This repository turns it into a clean-room, runnable model, and the first step is to pin down what the model must satisfy before any code exists: requirements, the method itself (a state machine with gates), and the data boundary that keeps the repository public-safe.

## What Changes

- `docs/REQUIREMENTS.md`: one-sentence goal, numbered requirement table (R1..), constraints (data boundary, clean-room rule, no network, stdlib + yaml).
- `docs/METHOD.md`: the model. Pipeline `check -> plan -> gate -> apply -> verify` plus per-layer rollback, with a mermaid state diagram, a step table, the apiserver gate, the version x health quadrant, rollback triggers, fleet order, and the hard parts as method entries.
- `tools/check_rules.py`: leak scan over every text file using `.leak_patterns.local` (gitignored, one regex per line) plus generic public patterns; also verifies the required docs exist.
- `.claude/skills/upgrade-change-loop/SKILL.md`: the per-change loop (OpenSpec change, staged commits, evidence, HTML report, blog notes).
- `README.md` skeleton with the Progress table.

## Capabilities

### New Capabilities
- `upgrade-model`: the model document has the required sections and diagrams.
- `data-boundary`: the repository never contains employer, cluster or account identifiers, and the scan proves it.

### Modified Capabilities
(none)

## Impact

No runnable code yet. Everything after this change is checked against `docs/METHOD.md`; a gate that is not in the method does not get implemented.
