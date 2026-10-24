## ADDED Requirements

### Requirement: Method document is a model
`docs/METHOD.md` SHALL describe the system as states and gates: at least one mermaid diagram, a step table naming each step's gate and failure behaviour, and a section on the apiserver gate.

#### Scenario: Reader looks for the gate order
- **WHEN** a reader opens `docs/METHOD.md`
- **THEN** the pipeline check, plan, gate, apply, verify and the per-layer rollback are visible in a diagram and in the step table

### Requirement: Criteria are written down
The check criteria, rollback triggers and fleet order SHALL be stated as fixed values (raft lag threshold 1000, rollback trigger list, stage order), not as guidance.

#### Scenario: Threshold lookup
- **WHEN** a reader needs the raft lag limit
- **THEN** `docs/METHOD.md` states 1000 entries and says exceeding it fails the gate
