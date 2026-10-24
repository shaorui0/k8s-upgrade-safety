## Why

A model of gates is only believable if each gate has something to catch. The simulator needs a fleet with realistic structure (five stages, three cluster types, masters, etcd, worker groups, stateful nodes, PDBs, addons, alerts) and with faults planted on purpose, so that every later test can say "this fault is caught by this gate" against ground truth rather than against a fixture built to pass.

## What Changes

- `testenv/fleet.yaml`: nine synthetic clusters across dev, preprod, prod-canary, prod and management, plus a `faults:` ground-truth list (five faults: raft lag 2000, CCM unhealthy (initially a target rollout that does not come up; since c0006, an old CCM broken by the new control plane), PDB blocking drain, slow eviction without the 600 s flag, apiserver `/readyz` failing after upgrade). One cluster carries the 600 s flag and a slow node and must pass.
- `testenv/gen_fleet.py`: the generator that writes it, so the fleet is reproducible and reviewable as code.
- `upgrade_safety/model.py`: load and validate the fleet (`FleetError` lists every problem), version and skew arithmetic, quorum math, fleet ordering, target AMI lookup.
- `upgrade_safety/test_model.py`: loader, validator, skew, ordering and ground-truth tests.
- `testenv/README.md`: what is in the fleet and where each fault lives.

## Capabilities

### New Capabilities
- `synthetic-fleet`: shape and ground truth of the test fleet.
- `fleet-model`: loading, validation, skew and quorum arithmetic.

### Modified Capabilities
(none)

## Impact

No CLI yet. Only synthetic data; no real cluster names, versions of real systems or identifiers. Faults are data fields, never code paths keyed on cluster names.
