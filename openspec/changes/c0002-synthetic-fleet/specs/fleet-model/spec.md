## ADDED Requirements

### Requirement: Validation reports every problem
Loading a fleet SHALL raise `FleetError` listing all structural problems at once (even master count, leader not a member, unknown AMI, PDB naming an unknown node, missing stage), not only the first.

#### Scenario: Two problems
- **WHEN** a fleet has an unknown AMI and a leader outside the member list
- **THEN** the error message contains both

### Requirement: Skew arithmetic
The model SHALL answer whether a component version is allowed given the apiserver version: kubelet may trail by at most 2 minors, controller-manager and scheduler by at most 1, none may be newer.

#### Scenario: Skew
- **WHEN** apiserver is 1.27 and kubelet 1.25
- **THEN** the kubelet is allowed; with kubelet 1.24 it is not

### Requirement: Quorum math and ordering
The model SHALL compute tolerated failures as (members - 1) // 2 and order clusters dev, preprod, prod-canary, other prod, management.

#### Scenario: Order
- **WHEN** the fleet is ordered
- **THEN** prod-canary precedes every other prod cluster and management is last
