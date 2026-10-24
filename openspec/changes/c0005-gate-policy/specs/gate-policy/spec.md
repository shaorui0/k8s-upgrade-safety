## ADDED Requirements

### Requirement: Three policies
The system SHALL support gate policies `manual`, `assisted` and `auto`, selected with `--gate` (default `manual`), recorded in state, in every step definition and in every evidence record.

#### Scenario: Default
- **WHEN** `--gate` is omitted
- **THEN** the policy is manual and `--approve` is required to pass the plan gate

### Requirement: Assisted continues on a passing postcheck
Under `assisted`, a step SHALL continue without a human signature when its postcheck passes, and SHALL stop with outcome `stopped_postcheck` when it fails; the plan gate SHALL proceed only if the diff verdict is `safe_to_apply`.

#### Scenario: Clean prod-class cluster
- **WHEN** a clean workload cluster runs with `--gate assisted` and no `--approve`
- **THEN** the run completes, no SIGNOFF line exists, and every gate decision in evidence is `continue` by `engine`

#### Scenario: Postcheck fails
- **WHEN** the second master's apiserver fails `/readyz` under assisted
- **THEN** the run stops at that step with outcome `stopped_postcheck`, and the next component is untouched

### Requirement: Auto only on low-risk clusters
`auto` SHALL be accepted only for cluster types `dev-staging` and `management`. For a `workload` cluster the command SHALL be refused with exit code 2 before a run directory is created.

#### Scenario: Refused on prod
- **WHEN** `run --gate auto --cluster prod-canary` is issued
- **THEN** exit code is 2, the message names the cluster type, and no run directory exists

#### Scenario: Allowed on dev
- **WHEN** `run --gate auto --cluster dev-1` is issued without `--approve`
- **THEN** the run completes unattended

### Requirement: Auto does not carry unread warnings
Under `auto`, a plan with warnings SHALL NOT pass the plan gate.

#### Scenario: Slow eviction on a dev cluster
- **WHEN** a dev-staging cluster has a node whose eviction exceeds the drain timeout and runs under auto
- **THEN** the run stops at `gate:plan` and names the warning; under assisted the same plan passes the gate

### Requirement: Manual keeps its meaning
Under `manual`, a failed postcheck SHALL end with outcome `halted_by_operator`, and a step asking for sign-off SHALL not execute without `--approve`.

#### Scenario: Unsigned step
- **WHEN** a signoff step runs without `--approve`
- **THEN** the executor is not called and the run is awaiting approval
