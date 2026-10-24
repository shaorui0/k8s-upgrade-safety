## ADDED Requirements

### Requirement: Fixed check criteria
`check` SHALL evaluate: etcd members odd, all online, raft lag <= 1000 for every follower, exactly one leader, all nodes Ready, kube-system healthy, zero external alerts, and agreement with the external monitor. Any failure SHALL stop the pipeline before any mutation.

#### Scenario: Raft lag
- **WHEN** a follower is 2000 entries behind and check runs
- **THEN** the criterion `etcd_raft_lag` fails, the run status is failed and nothing is mutated

#### Scenario: Boundary
- **WHEN** the lag is exactly 1000
- **THEN** the criterion passes; at 1001 it fails

### Requirement: Approval gate
`apply` and `run` without `--approve` SHALL stop at the plan, print what would be executed, and exit with code 2; no cluster state changes.

#### Scenario: No approval
- **WHEN** `apply` runs without `--approve`
- **THEN** exit code is 2, plan evidence exists and every master still runs the old version

### Requirement: Per-master sign-off
With `--approve`, each master SHALL have its own gate step whose sign-off is logged individually before that master is touched.

#### Scenario: Three masters
- **WHEN** a clean cluster is upgraded
- **THEN** the execution log has one sign-off line per master, in order

### Requirement: apiserver gate
Inside a master the order SHALL be apiserver, apiserver readiness (`/readyz` and load-balancer membership), controller-manager, scheduler, kubelet, member verification. A failed readiness step SHALL stop the layer with the later components of that master and all later masters unchanged.

#### Scenario: Readyz fails
- **WHEN** the second master's apiserver fails `/readyz` after upgrade
- **THEN** the run stops at that master's readiness step, its controller-manager is still old and the third master is untouched

### Requirement: Worker layer never forces
Worker replacement SHALL happen in ASG-refresh batches of 20% with stateful nodes first and alone, SHALL stop on the first failed batch, and SHALL NOT replace any node in a batch whose drain is blocked by a PDB allowing zero disruptions or whose eviction exceeds the drain timeout.

#### Scenario: PDB blocks
- **WHEN** a stateful node's PDB allows zero disruptions
- **THEN** the batch fails naming the PDB, no worker node is replaced and the reason says a human must wait or lower minAvailable

#### Scenario: Slow eviction needs the flag
- **WHEN** a node evicts in 540 s and the cluster drain timeout is 300 s
- **THEN** the batch fails naming the 600 s flag; with `drain_timeout_s: 600` it passes

### Requirement: Addon order
Addons SHALL be upgraded CCM, then CNI, then Cluster Autoscaler, each requiring the previous to be completed; an unhealthy CCM rollout SHALL stop the layer and say why, leaving CNI and Cluster Autoscaler untouched.

#### Scenario: CCM unhealthy
- **WHEN** the target CCM rollout is unhealthy and the worker layer has completed (in the fleet, fault F2 now stops earlier at the worker layer, see c0006)
- **THEN** the run stops at `addon:ccm`, the reason mentions the uninitialized taint, and CNI and Cluster Autoscaler versions are unchanged

### Requirement: Version x health quadrant
`verify` SHALL classify target+healthy as proceed, old+healthy as rerun, and any unhealthy as human, and SHALL diff against the baseline snapshot written before the upgrade.

#### Scenario: Four quadrants
- **WHEN** the four combinations are evaluated
- **THEN** decisions are proceed, rerun, human, human

### Requirement: Rollback advice
On a failed apply step the run SHALL write `rollback.json` with the triggers that fired (master upgrade failed, over 50% pods not Running, critical service unreachable, alert flood) and the action for the failed layer; it SHALL NOT execute the action.

#### Scenario: Master failure
- **WHEN** a master step fails
- **THEN** rollback.json lists master_upgrade_failed and the control-plane action (snapshot restore plus binary downgrade)

### Requirement: Fleet order and pause
Without `--cluster`, `run` SHALL process clusters dev, preprod, prod-canary, other prod, management, and SHALL stop at the first failure without touching later clusters.

#### Scenario: Fault in prod
- **WHEN** the fleet runs and a prod cluster fails
- **THEN** the management cluster is not started and the exit code is non-zero
