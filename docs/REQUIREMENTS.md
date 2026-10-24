# Requirements: Upgrade Safety System (clean-room model)

## 1. One sentence

A runnable, evidence-producing model of the upgrade safety system I built and ran across 50 self-managed Kubernetes clusters (1.24 to 1.29, zero customer-impacting downtime): the gates, the order of operations, the rollback triggers and the fleet policy are written down as a state machine and executed by a simulator against a synthetic fleet with planted faults.

Source of truth for every number: the two public write-ups (project page and blog post). Nothing else.

## 2. Requirements

| # | Requirement | Verified by |
|---|---|---|
| R1 | The system is a pipeline `check -> plan (dry-run) -> gate (human) -> apply -> verify`, with rollback declared per layer | `docs/METHOD.md` diagram + step table |
| R2 | `check` criteria are fixed: etcd members odd and all online, raft index lag <= 1000, exactly one leader, nodes Ready, kube-system healthy, external alerts = 0, etcd snapshot taken first | unit test: lag 2000 fails check |
| R3 | `plan` is a real dry-run: kubeadm plan, worker AMI diff (kubelet = target), Launch Template diff (only the AMI may change), blast radius by quorum math | plan evidence in `runs/<id>/plan.json` |
| R4 | `apply` runs three layers in order, each with its own gate: control plane in place one master at a time with a human sign-off per master; workers replaced immutably in 20% ASG instance-refresh batches, stop on first failure; addons in order CCM, CNI, Cluster Autoscaler, each verified | simulator run + tests |
| R5 | Inside one master, the apiserver upgrades first and must pass `/readyz` and load-balancer membership before controller-manager, scheduler or kubelet is touched | test: readyz failing blocks the next component |
| R6 | Without `--approve`, `apply` stops at the plan, prints what it would do, exits non-zero | test |
| R7 | Every step writes evidence: JSON health snapshots, plan diff, execution log, per-step state (completed / in-progress / pending); `--resume` continues from state without repeating completed steps | test: resume does not re-run completed steps |
| R8 | `verify` classifies the result on version x health (target+healthy = proceed, old+healthy = re-run, any unhealthy = human), diffs against the pre-upgrade baseline file, and cross-checks against the external monitor | test: four quadrants |
| R9 | Rollback triggers are declared before execution: master upgrade fails, more than 50% of pods not Running, critical service unreachable, alert flood; actions per layer (control plane: snapshot restore + binary downgrade; workers: stop refresh + revert LT; addons: rollout undo) | rollback advice in run evidence |
| R10 | Fleet order dev -> preprod -> prod canary -> remaining prod -> management last; any failure pauses the whole fleet for a human | fleet run test |
| R11 | Hard parts are method entries, not footnotes: API deprecation (PSP to PSA warn/audit first), stateful nodes first with PDBs never forced, heterogeneity via `cluster_type` + per-cluster flags, "zero incidents" against a pre-agreed standard, leader transfer is expected while a member that does not return is the danger | `docs/METHOD.md` section 8 |
| R12 | The synthetic fleet has at least five clusters of all five stages and at least four planted faults (raft lag 2000, unhealthy CCM rollout, PDB blocking drain, slow eviction needing a 600 s flag) | `testenv/fleet.yaml` ground truth + tests |
| R13 | Every run produces `runs/<id>/report.html` | acceptance command |
| R14 | Process is the deliverable: each change is an OpenSpec change, staged commits, evidence file, local HTML report, raw blog notes | `openspec/changes/`, `reports/`, `notes/blog/` |
| R15 | Public-safe: a leak scan is part of every acceptance | `python3 tools/check_rules.py` |
| R16 | The upgrade is a level-triggered reconcile: `plan` produces a formal diff artifact (desired vs observed) and `apply` is a per-step loop (precheck, one executor call, postcheck against the baseline, gate) with one evidence record per attempt | `diff.json`, `evidence.jsonl`, reconcile tests |
| R17 | Four JSON contracts (snapshot, diff, step, evidence) with a validator; every artifact a run writes conforms | contract tests over run directories |
| R18 | Every step declares `reversible`; an irreversible step is refused without its `backup_precondition` (the etcd snapshot is one instance) | test: no snapshot, no execute |
| R19 | Control plane and execution plane are separate: the engine acts only through an `Executor` interface; only a simulated executor is implemented, real adapters are named and refuse | executor seam tests |
| R20 | Worker blast radius is tiered (canary of one node, then batches of at most 20%, stateful alone), orthogonal to layer order master, worker, components | tier tests |

## 3. Constraints

- **Data boundary.** Clean-room rewrite. Only the two public write-ups are source material. No employer name, company cluster alias, internal service name, customer name, chat-workspace domain or account number in any file, commit message or report. Private patterns live in `.leak_patterns.local` (gitignored).
- **No network, no cloud, no kubectl.** The simulator models the cluster as data; the CLI never calls out. Python 3 standard library plus PyYAML.
- **Honest scope.** The simulator proves the gate logic is consistent and its evidence is reproducible. It does not prove anything about real kubeadm behaviour. The README says so.
- **Numbers.** 50 clusters, 1.24 to 1.29, 18-21 h two-person to 6-8 h single operator, 20% batches, `serial: 1`, raft lag 1000, drain 300 s to 600 s. The roadmap items in the blog (alert gating, synthetic checks, auto-promotion after canary) are targets, not results, and are not claimed.
- **Gates are not bypassable by flag.** There is no `--force`; `--approve` is the only way past a gate and it is logged per master.
