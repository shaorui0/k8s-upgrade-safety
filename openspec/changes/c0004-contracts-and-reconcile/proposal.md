## Why

The pipeline in c0003 works, but its decisions are made inside engine methods that poke at the simulated cluster directly. Two things follow: the artifacts on disk are ad hoc (nothing says what a snapshot or a plan must contain), and the engine cannot be pointed at anything but the simulator. My 2026 design notes describe the shape this should have: a level-triggered reconcile loop (desired versus observed gives a diff, the diff becomes steps), four data contracts between the layers, an explicit reversibility class on every step, and a strict split between a control plane that decides and an execution plane that acts. This change re-implements those ideas here, from scratch, with the repository's own schemas and names.

## What Changes

- `upgrade_safety/contracts/`: four JSON Schemas (snapshot, diff, step, evidence) plus a small standard-library validator for the schema subset they use. Everything `runs/<id>/` writes is validated against them in tests.
- `plan` now produces a formal **diff** artifact (`diff.json`): desired versus observed as concrete changes with per-change reversibility, pointer alignment, and a machine-readable verdict.
- `apply` becomes a **per-step reconcile loop** (`reconcile.py`): reversibility guard, baseline snapshot, idempotent skip (`already_done`), prechecks, sign-off, one executor call, postcheck against the baseline, gate decision, one append-only evidence record per step (`evidence.jsonl`).
- Steps are data (`steps.py`, validated against the step contract, stored as `steps.json`). Assertions are a tiny DSL over snapshots evaluated by a probe registry (`probes.py`), so the control plane decides from observed state only.
- **Reversibility**: every step says `reversible`. A step with `reversible=false` (control-plane components) is refused unless its `backup_precondition` (`etcd-snapshot-fresh`) holds. The old "snapshot first" rule becomes one instance of this rule.
- **Control plane / execution plane split**: an `Executor` interface (`observe`, `execute`) with `SimulatedExecutor` as the only implementation. The slots for Terraform, Ansible and AWS adapters exist and refuse loudly; they are not implemented.
- **Blast-radius tiers** for workers: canary (one node), then 20% batches (stateful nodes alone), orthogonal to the layer order.
- Layers are named `master`, `worker`, `components` and ordered master, worker, components.

## Capabilities

### New Capabilities
- `contracts`: the four schemas and the validator.
- `reconcile-loop`: step loop, probes, executor interface, reversibility rule, evidence records.

### Modified Capabilities
- `pipeline` (c0003): plan artifact is the diff contract; run directory file names change (`snapshots/baseline.json`, `diff.json`, `evidence.jsonl`, `steps.json`, `verify.json`).

## Impact

Run directory layout changes; tests are rewritten against the new artifacts. No behaviour of the gates changes in this change (gate policy comes in c0005, the CCM precondition in c0006). Human gate and rollback: unchanged from c0003 (manual sign-off via `--approve`; rollback is advice).
