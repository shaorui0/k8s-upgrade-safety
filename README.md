# k8s_upgrade_safety

A clean-room, runnable model of the upgrade safety system I built and ran across 50 self-managed clusters, 1.24 -> 1.29, with zero customer-impacting downtime.

The original was a Python CLI orchestrating Ansible, boto3 and kubectl against real fleets. This repository is not that code. It is the *model* behind it, written as a state machine with gates ([`docs/METHOD.md`](docs/METHOD.md)) and executed by a simulator against a synthetic fleet with planted faults, so every gate can be run, broken and inspected. Source material is the two public write-ups only; see the data boundary in [`docs/REQUIREMENTS.md`](docs/REQUIREMENTS.md).

---

## How I think about it

Each answer traces to a numbered requirement in [`docs/REQUIREMENTS.md`](docs/REQUIREMENTS.md).

| Question | My answer |
|---|---|
| **What was the real problem?** | Not manual versus automated. At any step nobody could answer "what evidence says it is safe to proceed?" The knowledge was in senior heads, the evidence scattered, postmortems impossible. (R1) |
| **What is a gate?** | A written criterion with a fixed threshold that is evaluated by code and leaves a JSON record. Raft lag over 1000 fails the gate; nobody decides on the day. (R2) |
| **Why a dry-run that can fail?** | A plan document cannot fail. A plan that diffs AMIs, Launch Templates and quorum arithmetic can, and failing early is cheap. Blast radius is a design input: 3 masters tolerate 1, `serial: 1` caps the worst case at 1. (R3) |
| **Why is the apiserver the gate?** | It anchors version skew. Nothing else on a master moves until it passes `/readyz` and is a healthy load-balancer member. (R5) |
| **What does "done" mean?** | A version x health quadrant against a baseline file written before the upgrade, cross-checked with an external monitor. Not an engineer's memory. (R8) |
| **When do you roll back?** | Triggers are declared before execution, per layer: control plane is snapshot restore plus binary downgrade, workers stop the refresh and revert the template, addons roll out undo. (R9) |
| **What stops the whole fleet?** | Any failure. Order is dev, preprod, prod canary, remaining prod, management last. A human restarts it. (R10) |
| **How do you know the model is not fiction?** | The simulator has planted faults and the tests assert each gate catches its own. The scope of that claim is the gate logic, not real kubeadm. (R12) |
| **What stays private?** | Everything from any employer. Clean-room, one leak scan per change. (R15) |

---

## Progress

One change = one OpenSpec change = staged commits, evidence, an HTML report and raw notes ([`.claude/skills/upgrade-change-loop`](.claude/skills/upgrade-change-loop/SKILL.md)).

| Change | Date | What | Takeaway | Report · Notes |
|---|---|---|---|---|

## License

MIT, Rui Shao. See [`LICENSE`](LICENSE).
