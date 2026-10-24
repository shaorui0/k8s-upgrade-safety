# k8s_upgrade_safety

A clean-room, runnable model of the upgrade safety system I built and ran across 50 self-managed clusters, 1.24 -> 1.29, with zero customer-impacting downtime.

The original was a Python CLI orchestrating Ansible, boto3 and kubectl against real fleets. This repository is not that code. It is the *model* behind it, written as a state machine with gates ([`docs/METHOD.md`](docs/METHOD.md)) and executed by a simulator against a synthetic fleet with planted faults, so every gate can be run, broken and inspected. Source material is the two public write-ups plus my own design framework (concepts only, re-implemented from scratch: no employer code, schemas or names); see the data boundary in [`docs/REQUIREMENTS.md`](docs/REQUIREMENTS.md).

## Quickstart

```bash
pip install -r requirements.txt            # PyYAML only
python3 -m unittest discover               # model, checks, plan, pipeline, fault matrix
python3 -m upgrade_safety run --fleet testenv/fleet.yaml --cluster prod-canary --target 1.26 --approve
open runs/*/report.html                    # decision, steps, criteria, plan, diff, evidence records, log
ls runs/*/                                 # snapshots/, diff.json, steps.json, evidence.jsonl, state.json, ...
```

No cloud account, no kubectl, no network: the cluster is data. Try the gates:

```bash
# no --approve: stops at the printed plan, exit code 2, nothing changes
python3 -m upgrade_safety apply --fleet testenv/fleet.yaml --cluster prod-canary --target 1.26

# planted faults, each stopping at the step the method says it should
python3 -m upgrade_safety run --fleet testenv/fleet.yaml --cluster prod-east  --approve   # raft lag 2000: stops at check
python3 -m upgrade_safety run --fleet testenv/fleet.yaml --cluster prod-north --approve   # apiserver /readyz: stops before controller-manager
python3 -m upgrade_safety run --fleet testenv/fleet.yaml --cluster prod-west  --approve   # PDB blocks the canary drain: nothing forced
python3 -m upgrade_safety run --fleet testenv/fleet.yaml --cluster prod-south --approve   # CCM broken by the new control plane: worker layer stops before any worker

# progressive autonomy
python3 -m upgrade_safety run --fleet testenv/fleet.yaml --cluster prod-canary --gate auto        # refused: exit 2, no run created
python3 -m upgrade_safety run --fleet testenv/fleet.yaml --cluster prod-canary --gate assisted    # no signatures; stops only on failure
python3 -m upgrade_safety run --fleet testenv/fleet.yaml --cluster dev-1       --gate auto        # unattended, dev-staging only

# interrupt, then continue without repeating completed steps
python3 -m upgrade_safety run --fleet testenv/fleet.yaml --cluster dev-1 --approve --run-id demo --interrupt-at workers:batch1
python3 -m upgrade_safety run --fleet testenv/fleet.yaml --cluster dev-1 --approve --resume demo

# the whole fleet in order; pauses at the first failure (here prod-east)
python3 -m upgrade_safety run --fleet testenv/fleet.yaml --approve
```

Commands: `check`, `plan` (dry-run, no mutation), `apply` (through the addon layer), `verify` (needs `--resume <run>` for the baseline diff), `run` (apply + verify). Exit codes: 0 ok, 1 a gate stopped the run, 2 awaiting approval, a refused policy or a usage error, 130 interrupted.

**Scope of the claim.** The simulator shows the gate logic is consistent and its evidence is reproducible. It says nothing about real kubeadm, real etcd or real AWS behaviour. Sources are the two public write-ups of the original system; the numbers (50 clusters, 1.24 -> 1.29, 18-21 h with two people to 6-8 h with one operator, 20% batches, `serial: 1`, raft lag 1000, drain 300 s to 600 s) come from there. The roadmap items in the write-up (alert gating, synthetic checks, auto-promotion after canary) are targets, not results, and are not claimed here.

---

## How I think about it

Each answer traces to a numbered requirement in [`docs/REQUIREMENTS.md`](docs/REQUIREMENTS.md).

| Question | My answer |
|---|---|
| **What was the real problem?** | Not manual versus automated. At any step nobody could answer "what evidence says it is safe to proceed?" The knowledge was in senior heads, the evidence scattered, postmortems impossible. (R1) |
| **What is a gate?** | A written criterion with a fixed threshold that is evaluated by code and leaves a JSON record. Raft lag over 1000 fails the gate; nobody decides on the day. (R2) |
| **Why a dry-run that can fail?** | A plan document cannot fail. A plan that diffs AMIs, Launch Templates and quorum arithmetic can, and failing early is cheap. Blast radius is a design input: 3 masters tolerate 1, `serial: 1` caps the worst case at 1. (R3) |
| **Why is the apiserver the gate?** | It anchors version skew. Nothing else on a master moves until it passes `/readyz` and is a healthy load-balancer member. (R5) |
| **What is the engine, really?** | A level-triggered reconcile: desired versus observed gives a diff, the diff becomes steps, each step is precheck, one action, postcheck against the baseline, gate, with one evidence record. Drift is a difference, not a surprise. (R16) |
| **Who is allowed to touch the cluster?** | Only an executor behind a narrow interface (`observe`, `execute`). The engine decides from snapshots and never acts; the simulator is the one implementation, real Terraform or Ansible adapters are named and refuse. (R19) |
| **Can everything be undone?** | No, and each step says so. An irreversible step (control-plane components) is refused unless a fresh etcd snapshot exists; "snapshot first" is one instance of that rule. (R18) |
| **How does it go unattended?** | Progressively. Manual: a signature per step. Assisted: continue on a passing postcheck, a human only on failure. Auto: same, nobody present, only on dev-staging and management clusters; asking for it on a prod-class cluster is refused before anything exists. (R21, R22) |
| **What does "done" mean?** | A version x health quadrant against a baseline file written before the upgrade, cross-checked with an external monitor. Not an engineer's memory. (R8) |
| **When do you roll back?** | Triggers are declared before execution, per layer: control plane is snapshot restore plus binary downgrade, workers stop the refresh and revert the template, addons roll out undo. (R9) |
| **What stops the whole fleet?** | Any failure. Order is dev, preprod, prod canary, remaining prod, management last. A human restarts it. (R10) |
| **How do you know the model is not fiction?** | The simulator has planted faults and the tests assert each gate catches its own. The scope of that claim is the gate logic, not real kubeadm. (R12) |
| **What stays private?** | Everything from any employer. Clean-room, one leak scan per change. (R15) |

---

## Repo layout

```
docs/METHOD.md            the model: state machine, step table, apiserver gate, quadrant, rollback, fleet order
docs/REQUIREMENTS.md      R1.. requirement table and the data-boundary constraints
upgrade_safety/contracts/ snapshot, diff, step, evidence JSON Schemas + stdlib validator
upgrade_safety/           control plane: engine, reconcile loop, steps, probes, gate, plan (diff), verify, report, cli
upgrade_safety/executors.py  execution plane interface; SimulatedExecutor is the only implementation
testenv/                  fleet.yaml (9 clusters, 5 planted faults) and its generator
tools/check_rules.py      leak scan; private patterns live in a gitignored .leak_patterns.local
tools/mutation_check.py   break each gate once; the tests must go red (make mutation)
openspec/changes/         one OpenSpec change per row of Progress, each with evidence.md
reports/  notes/blog/     local HTML report and raw blog notes per change
.claude/skills/upgrade-change-loop/   the per-change loop
runs/                     evidence of each run (gitignored): snapshots, plan, log, state, report.html
```

## Progress

One change = one OpenSpec change = staged commits, evidence, an HTML report and raw notes ([`.claude/skills/upgrade-change-loop`](.claude/skills/upgrade-change-loop/SKILL.md)).

| Change | Date | What | Takeaway | Report · Notes |
|---|---|---|---|---|
| c0001 requirements-and-method | 2026-10-24 | Requirements R1-R15, the state-machine method (gates, apiserver gate, quadrant, rollback, fleet order), leak scan | The real problem was never manual vs automated; it was that nobody could answer "what evidence says it is safe to proceed". | [report](reports/0001-requirements-and-method.html) · [notes](notes/blog/0001-requirements-and-method.md) |
| c0002 synthetic-fleet | 2026-10-24 | Nine-cluster synthetic fleet, five planted faults with ground truth, loader/validator, skew and quorum math | A fault is only evidence for a gate if it is planted before the gate exists, as data, never as code keyed on a cluster name. | [report](reports/0002-synthetic-fleet.html) · [notes](notes/blog/0002-synthetic-fleet.md) |
| c0003 pipeline-skeleton | 2026-10-24 | check/plan/apply/verify/run CLI: approval gate, per-master sign-off, apiserver gate, never-forced drains, addon order, quadrant vs baseline, rollback advice, resume, fleet order, HTML report | Evidence is the product: every step writes a snapshot, a log line and a state transition, and the report is only a view over those files. | [report](reports/0003-pipeline-skeleton.html) · [notes](notes/blog/0003-pipeline-skeleton.md) |
| c0004 contracts-and-reconcile | 2026-10-24 | Four JSON contracts, plan as a diff artifact, per-step reconcile loop with evidence.jsonl, executor seam, reversibility guard, canary tier | The decisions moved out of the engine into data: a step is a record, probes read snapshots, the executor only acts. | [report](reports/0004-contracts-and-reconcile.html) · [notes](notes/blog/0004-contracts-and-reconcile.md) |
| c0005 gate-policy | 2026-10-24 | `--gate manual\|assisted\|auto`; auto refused on prod-class clusters before any run exists; assisted continues on a passing postcheck | Autonomy is a dial on who decides to continue, bounded by cluster class in code; auto needs a cleaner plan, not a more permissive one. | [report](reports/0005-gate-policy.html) · [notes](notes/blog/0005-gate-policy.md) |
| c0006 ccm-worker-precondition | 2026-10-24 | CCM health is a precheck of every worker step; F2 re-planted (old CCM broken by the new control plane) and stops at the worker layer | A failure belongs where it is cheapest to find: before anything is replaced, as a dependency edge between layers rather than a reordering. | [report](reports/0006-ccm-worker-precondition.html) · [notes](notes/blog/0006-ccm-worker-precondition.md) |

## License

MIT, Rui Shao. See [`LICENSE`](LICENSE).
