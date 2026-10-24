## ADDED Requirements

### Requirement: Fleet shape
`testenv/fleet.yaml` SHALL contain at least five clusters covering the stages dev, preprod, prod-canary, prod and management, and the cluster types workload, management and dev-staging.

#### Scenario: Stage coverage
- **WHEN** the fleet is loaded
- **THEN** every stage has at least one cluster and there are at least five clusters

### Requirement: Planted faults with ground truth
The fleet SHALL plant at least these faults and list them under `faults:` with cluster, kind and the step expected to stop: a raft follower lagging by 2000, a CCM whose target rollout is unhealthy, a PDB allowing zero disruptions on a stateful node, and a node whose eviction takes longer than the default 300 s drain timeout in a cluster without the 600 s flag.

#### Scenario: Ground truth matches data
- **WHEN** a test reads each fault's cluster
- **THEN** the cluster data actually exhibits the fault (lag, flag, PDB, ccm field)

### Requirement: A flagged exception passes
At least one cluster SHALL contain a slow-eviction node together with `drain_timeout_s: 600`, so the flag mechanism has a positive case.

#### Scenario: Flag present
- **WHEN** the preprod cluster is loaded
- **THEN** its flags contain drain_timeout_s 600 and a node eviction time between 300 and 600 seconds
