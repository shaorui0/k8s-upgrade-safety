## ADDED Requirements

### Requirement: CCM health is a worker-layer precheck
Every worker-layer step SHALL carry a blocking precheck that the cloud-controller-manager is healthy; a failing precheck SHALL stop the step with outcome `stopped_precheck` before any executor call.

#### Scenario: Unhealthy CCM before the launch template
- **WHEN** the CCM is unhealthy when the worker layer starts
- **THEN** `workers:launch_template` stops at precheck, the launch template and ASG still point at the old AMI, and no worker is replaced

#### Scenario: Unhealthy CCM mid-layer
- **WHEN** the CCM becomes unhealthy after the canary succeeded
- **THEN** the next batch stops at precheck and later batches are untouched

### Requirement: F2 stops at the worker layer
The planted fault on `prod-south` SHALL be a CCM that is healthy at `check` time and unhealthy once the new control plane is up, and its expected stop SHALL be `workers:launch_template`.

#### Scenario: Fault matrix
- **WHEN** `run --approve --cluster prod-south` is executed
- **THEN** all masters are at the target version, the stop is at `workers:launch_template`, the reason mentions the uninitialized taint, and CNI and Cluster Autoscaler are untouched

### Requirement: The addon layer still verifies the rollout
The addon layer SHALL keep verifying the CCM rollout; a CCM whose target rollout is unhealthy SHALL stop `addon:ccm` and leave CNI and Cluster Autoscaler untouched.

#### Scenario: Rollout unhealthy
- **WHEN** the target CCM rollout is unhealthy and the worker layer completed
- **THEN** the run stops at `addon:ccm` with the rollout reason
