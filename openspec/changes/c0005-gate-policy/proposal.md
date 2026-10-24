## Why

Every gate in c0003 and c0004 is manual: a human signs off before each step. That is the right first pass, and it is also where almost all the operator time goes. The design I am implementing says the cost saving lives in one jump: from a human reading every step to a human woken only by exceptions, using the same step loop and the same evidence. Autonomy has to be progressive and it has to be bounded: unattended runs belong on low-risk clusters only.

## What Changes

- Gate policy per run: `manual | assisted | auto` (`--gate`, default manual).
  - **manual**: an operator signs off before each step that asks for it (`--approve`, logged per step); a failed postcheck halts the run (`halted_by_operator`).
  - **assisted**: no per-step signature. The plan gate reads the diff `verdict`; each step continues if its postcheck passes and stops if it fails (`stopped_postcheck`). A human is needed only on exceptions.
  - **auto**: unattended. Same decisions as assisted, plus it refuses to start a plan that carries warnings (nobody would read them). Allowed only on `dev-staging` and `management` cluster types; configuring it for a `workload` (prod-class) cluster is refused before any run directory exists.
- `gate.py`: `validate_policy`, `plan_gate`, `decide`, `needs_signoff` as one small decision module; the engine and the reconcile loop call it, nothing else decides.
- Evidence records the policy and who decided (`operator` for a manual continue, `engine` otherwise).
- `--approve` stays the manual signature; it is ignored under assisted and auto.

## Capabilities

### New Capabilities
- `gate-policy`: the three policies, the prod restriction on auto, and their evidence.

### Modified Capabilities
- `reconcile-loop` (c0004): sign-off and the postcheck decision go through `gate.py`.

## Impact

Autonomy is bounded by cluster class, not by an operator remembering to be careful. Human gate: manual remains the default and the only policy that works on prod-class clusters without `--approve`-style signatures being replaced; assisted is allowed on prod-class clusters (a human is still woken by every failure). Rollback: unchanged, advice only.
