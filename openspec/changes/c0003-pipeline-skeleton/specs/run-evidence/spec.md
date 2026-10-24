## ADDED Requirements

### Requirement: Evidence per run
Each run SHALL write to `runs/<run_id>/`: `snapshots/pre.json`, `plan.json`, `plan.txt`, `execution.log`, `state.json`, `cluster.json`, and after verify `snapshots/post.json` and `diff.json`.

#### Scenario: Complete run
- **WHEN** a clean cluster is upgraded with `run --approve`
- **THEN** all listed files exist and every step in state.json is completed

### Requirement: Resume
`--resume <run_id>` SHALL continue from `state.json`, SHALL NOT re-execute completed steps, and SHALL re-run a step left in-progress.

#### Scenario: Interrupted run
- **WHEN** a run is interrupted at a step and resumed
- **THEN** every step that completed before the interruption has exactly one START line in the log and the run completes
