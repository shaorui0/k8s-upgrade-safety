## Why

The method (c0001) and the fleet (c0002) exist; nothing executes them. The pipeline skeleton turns the model into a CLI whose every step writes evidence, so a run can be inspected, interrupted, resumed and reported, and so each planted fault can be shown stopping at the step the method says it should.

## What Changes

- Package `upgrade_safety/`: `checks` (health snapshot and the fixed criteria), `plan` (dry-run, AMI/Launch Template diff, quorum blast radius, batch plan), `engine` (step state machine, gates, layers, resume), `verify` (version x health quadrant, baseline diff, rollback triggers and advice), `evidence` (run directory, execution log), `report` (HTML), `cli` (`check|plan|apply|verify|run`).
- Evidence per run in `runs/<run_id>/`: `snapshots/pre.json` (the baseline), `snapshots/post.json`, `plan.json` + `plan.txt`, `execution.log`, `state.json` (completed / in-progress / pending / failed), `cluster.json` (simulated cluster state, makes resume possible), `diff.json`, `rollback.json` on failure, `report.html`.
- Human gates: `apply` without `--approve` stops at the printed plan with exit code 2; with `--approve` every master is signed off individually and logged. No force flag exists.
- The apiserver gate inside each master: `/readyz` and load-balancer membership must pass before controller-manager, scheduler or kubelet is touched.
- Unit tests for each behaviour in the spec, plus the planted-fault matrix.
- README Quickstart.

## Capabilities

### New Capabilities
- `pipeline`: check, plan, gate, apply (three layers), verify, rollback advice, fleet order.
- `run-evidence`: run directory contents, state and resume semantics.
- `run-report`: per-run HTML report.

### Modified Capabilities
(none)

## Impact

Simulator only: no network, no kubectl. Human gate and rollback are in the proposal because the model describes operations that, on real infrastructure, are destructive: the gate is `--approve`, and rollback is advice executed by a person (control plane: snapshot restore plus binary downgrade; workers: stop refresh plus revert launch template; addons: rollout undo).
