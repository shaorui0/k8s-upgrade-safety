## ADDED Requirements

### Requirement: Four contracts
`upgrade_safety/contracts/` SHALL contain `snapshot`, `diff`, `step` and `evidence` JSON Schemas (draft-07 subset) and a validator that raises `ContractError` listing every violation with its path.

#### Scenario: Reject a malformed record
- **WHEN** an evidence record has an outcome outside the enumerated set
- **THEN** validation fails and the message names the path `$.outcome`

### Requirement: Snapshot roles
A snapshot SHALL carry `meta.role` in {baseline, precheck, postcheck, daily} and everything a probe needs (versions, etcd members and lag, readiness, load-balancer state, nodes, PDBs, addons, backups).

#### Scenario: Baseline file
- **WHEN** a run completes the check step
- **THEN** `snapshots/baseline.json` validates against the snapshot contract with role baseline

### Requirement: Diff artifact
`plan` SHALL write `diff.json` conforming to the diff contract: `reversible`, `changes` (each with target, field, before, after, reversible), `alignment`, and `verdict` with `safe_to_apply`, blockers and warnings.

#### Scenario: Irreversible diff
- **WHEN** the plan contains a control-plane component change
- **THEN** the diff is `reversible: false` and the worker AMI change is marked `reversible: true`

### Requirement: Evidence records
Every executed or stopped step SHALL append one record to `evidence.jsonl`, conforming to the evidence contract, with outcome, baseline snapshot, postcheck snapshot, dry-run diff, gate decision and operator.

#### Scenario: Whole run
- **WHEN** a clean cluster is upgraded
- **THEN** every line of evidence.jsonl validates and every reconcile step has at least one record
