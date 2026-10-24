## ADDED Requirements

### Requirement: One loop per step
Each reconcile step SHALL run: reversibility guard, baseline snapshot, `already_done` skip, prechecks, sign-off, a single executor call, postcheck against the baseline, gate decision.

#### Scenario: Converged step
- **WHEN** a step's `already_done` assertion holds
- **THEN** the executor is not called and the outcome is `converged_skipped`

### Requirement: Irreversible steps need a proven backup
A step with `reversible: false` SHALL NOT execute unless its `backup_precondition` assertion holds; the outcome SHALL be `stopped_precheck` and the executor SHALL NOT be called.

#### Scenario: No snapshot
- **WHEN** a master component step runs without a fresh etcd snapshot
- **THEN** the step stops at precheck and no component version changes

### Requirement: Execution plane is an interface
The engine SHALL act on the cluster only through an `Executor` (`observe`, `execute`). Adapters for Terraform, Ansible and AWS SHALL be registered but raise `NotImplementedError` naming the missing adapter.

#### Scenario: Unimplemented adapter
- **WHEN** an engine is configured with the `terraform` executor
- **THEN** the first observe or execute fails with NotImplementedError

### Requirement: Blast-radius tiers
Worker replacement SHALL start with a canary step of exactly one node, followed by batches of at most 20%, stateful nodes alone, independent of layer order.

#### Scenario: Order
- **WHEN** a cluster with 10 stateless workers is planned
- **THEN** the steps are canary (1 node) then five batches of 2
