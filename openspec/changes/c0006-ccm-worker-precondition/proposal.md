## Why

A new worker only becomes useful when the cloud-controller-manager (CCM) initialises it; with an unhealthy CCM the node joins and sticks on the `uninitialized` taint. Until now the model verified CCM health only in the last layer, after every worker had been replaced, so the failure was found late and at the cost of replaced nodes. The decision (previously an open question in the notes) is to make CCM health a **precondition of the worker layer**, checked before the launch template changes and before every worker step. The addon layer keeps its own final verification of the CCM rollout.

## What Changes

- Every worker-layer step (`workers:launch_template`, the canary, each batch) gets a blocking precheck `addon.healthy{ccm} == true`, with the reason "an unhealthy CCM would strand new workers on the uninitialized taint".
- Fault **F2** (`prod-south`) changes shape and stop point. It is now "the old CCM is unhealthy once the new control plane is up" (`healthy_after_control_plane: false`, the new apiserver breaks it), which `check` cannot see because it runs before the upgrade. Expected stop moves from `addon:ccm` to `workers:launch_template`, with no worker touched. The `target_rollout_healthy` field still exists and still drives the addon layer's own verification; a unit test covers it with a purpose-built fleet.
- Docs: METHOD, testenv README, the fleet's `faults:` text (via the generator), and the c0002/c0003 descriptions that named the old stop point are updated, with the earlier evidence files annotated rather than rewritten.

## Capabilities

### New Capabilities
- `worker-ccm-precondition`: CCM health gates the worker layer.

### Modified Capabilities
- `synthetic-fleet` (c0002): F2 definition and expected stop.
- `pipeline` (c0003): the "Addon order" scenario about an unhealthy CCM.

## Impact

Layer order is unchanged: master, worker, components. The CCM check is a dependency edge between layers (components' health gates the worker layer), not a reordering. Rollback advice for an F2 stop fires no trigger: nothing irreversible has run since the control plane finished and no worker was replaced; the control plane upgrade itself is not undone by this stop.
