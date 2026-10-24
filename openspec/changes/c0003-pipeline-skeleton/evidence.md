# c0003 acceptance evidence

## 3.1 all tests (verbose)
```
$ python3 -m unittest discover -v 2>&1; python3 -m unittest discover -s tools 2>&1 | tail -3
test_clean_cluster_passes_all_eight (upgrade_safety.test_checks_plan.CheckTest.test_clean_cluster_passes_all_eight) ... ok
test_even_members_offline_and_two_leaders (upgrade_safety.test_checks_plan.CheckTest.test_even_members_offline_and_two_leaders) ... ok
test_external_alert_fails (upgrade_safety.test_checks_plan.CheckTest.test_external_alert_fails) ... ok
test_monitor_disagreement_fails (upgrade_safety.test_checks_plan.CheckTest.test_monitor_disagreement_fails) ... ok
test_node_not_ready_and_kube_system (upgrade_safety.test_checks_plan.CheckTest.test_node_not_ready_and_kube_system) ... ok
test_raft_lag_2000_fails (upgrade_safety.test_checks_plan.CheckTest.test_raft_lag_2000_fails) ... ok
test_raft_lag_boundary (upgrade_safety.test_checks_plan.CheckTest.test_raft_lag_boundary) ... ok
test_batches_stateful_first_alone_and_20_percent (upgrade_safety.test_checks_plan.PlanTest.test_batches_stateful_first_alone_and_20_percent) ... ok
test_clean_plan (upgrade_safety.test_checks_plan.PlanTest.test_clean_plan) ... ok
test_launch_template_may_only_change_ami (upgrade_safety.test_checks_plan.PlanTest.test_launch_template_may_only_change_ami) ... ok
test_not_one_minor_is_a_violation (upgrade_safety.test_checks_plan.PlanTest.test_not_one_minor_is_a_violation) ... ok
test_render_mentions_serial_and_gate (upgrade_safety.test_checks_plan.PlanTest.test_render_mentions_serial_and_gate) ... ok
test_serial_beyond_quorum_tolerance_is_a_violation (upgrade_safety.test_checks_plan.PlanTest.test_serial_beyond_quorum_tolerance_is_a_violation) ... ok
test_warnings_surface_faults_before_approval (upgrade_safety.test_checks_plan.PlanTest.test_warnings_surface_faults_before_approval) ... ok
test_minor_rejects_garbage (upgrade_safety.test_model.ArithmeticTest.test_minor_rejects_garbage) ... ok
test_nothing_newer_than_apiserver (upgrade_safety.test_model.ArithmeticTest.test_nothing_newer_than_apiserver) ... ok
test_quorum (upgrade_safety.test_model.ArithmeticTest.test_quorum) ... ok
test_skew_cm_and_scheduler (upgrade_safety.test_model.ArithmeticTest.test_skew_cm_and_scheduler) ... ok
test_skew_kubelet (upgrade_safety.test_model.ArithmeticTest.test_skew_kubelet) ... ok
test_apiserver_not_ready_fault (upgrade_safety.test_model.GroundTruthTest.test_apiserver_not_ready_fault) ... ok
test_at_least_four_distinct_fault_kinds (upgrade_safety.test_model.GroundTruthTest.test_at_least_four_distinct_fault_kinds) ... ok
test_ccm_rollout_unhealthy (upgrade_safety.test_model.GroundTruthTest.test_ccm_rollout_unhealthy) ... ok
test_clean_clusters_have_no_fault_fields (upgrade_safety.test_model.GroundTruthTest.test_clean_clusters_have_no_fault_fields) ... ok
test_flagged_exception_is_a_positive_case (upgrade_safety.test_model.GroundTruthTest.test_flagged_exception_is_a_positive_case) ... ok
test_pdb_allows_zero_disruptions (upgrade_safety.test_model.GroundTruthTest.test_pdb_allows_zero_disruptions) ... ok
test_raft_lag_2000 (upgrade_safety.test_model.GroundTruthTest.test_raft_lag_2000) ... ok
test_slow_eviction_without_flag (upgrade_safety.test_model.GroundTruthTest.test_slow_eviction_without_flag) ... ok
test_cluster_is_a_copy (upgrade_safety.test_model.LoadTest.test_cluster_is_a_copy) ... ok
test_order_canary_before_other_prod_and_management_last (upgrade_safety.test_model.LoadTest.test_order_canary_before_other_prod_and_management_last) ... ok
test_shape (upgrade_safety.test_model.LoadTest.test_shape) ... ok
test_target_ami (upgrade_safety.test_model.LoadTest.test_target_ami) ... ok
test_unknown_cluster (upgrade_safety.test_model.LoadTest.test_unknown_cluster) ... ok
test_even_master_count (upgrade_safety.test_model.ValidationTest.test_even_master_count) ... ok
test_missing_stage (upgrade_safety.test_model.ValidationTest.test_missing_stage) ... ok
test_pdb_unknown_node (upgrade_safety.test_model.ValidationTest.test_pdb_unknown_node) ... ok
test_reports_every_problem_at_once (upgrade_safety.test_model.ValidationTest.test_reports_every_problem_at_once) ... ok
test_valid_fleet_has_no_problems (upgrade_safety.test_model.ValidationTest.test_valid_fleet_has_no_problems) ... ok
test_addon_order_is_enforced (upgrade_safety.test_pipeline.AddonLayerTest.test_addon_order_is_enforced) ... ok
test_ccm_unhealthy_stops_the_addon_layer_with_a_reason (upgrade_safety.test_pipeline.AddonLayerTest.test_ccm_unhealthy_stops_the_addon_layer_with_a_reason) ... ok
test_lb_membership_is_a_separate_gate (upgrade_safety.test_pipeline.ApiserverGateTest.test_lb_membership_is_a_separate_gate) ... ok
test_leader_transfer_is_logged_as_expected (upgrade_safety.test_pipeline.ApiserverGateTest.test_leader_transfer_is_logged_as_expected) ... ok
test_member_that_does_not_come_back_is_the_danger (upgrade_safety.test_pipeline.ApiserverGateTest.test_member_that_does_not_come_back_is_the_danger) ... ok
test_next_component_refuses_if_gate_was_skipped (upgrade_safety.test_pipeline.ApiserverGateTest.test_next_component_refuses_if_gate_was_skipped) ... ok
test_readyz_alone_is_enough_to_stop (upgrade_safety.test_pipeline.ApiserverGateTest.test_readyz_alone_is_enough_to_stop) ... ok
test_readyz_failure_stops_before_next_component (upgrade_safety.test_pipeline.ApiserverGateTest.test_readyz_failure_stops_before_next_component) ... ok
test_apply_without_approve_refuses_and_prints_plan (upgrade_safety.test_pipeline.ApproveGateTest.test_apply_without_approve_refuses_and_prints_plan) ... ok
test_approving_via_resume_continues_the_same_run (upgrade_safety.test_pipeline.ApproveGateTest.test_approving_via_resume_continues_the_same_run) ... ok
test_each_master_is_signed_off_individually_in_order (upgrade_safety.test_pipeline.ApproveGateTest.test_each_master_is_signed_off_individually_in_order) ... ok
test_run_without_approve_also_refuses (upgrade_safety.test_pipeline.ApproveGateTest.test_run_without_approve_also_refuses) ... ok
test_clean_check_takes_snapshot (upgrade_safety.test_pipeline.CheckGateTest.test_clean_check_takes_snapshot) ... ok
test_raft_lag_over_1000_fails_check_and_mutates_nothing (upgrade_safety.test_pipeline.CheckGateTest.test_raft_lag_over_1000_fails_check_and_mutates_nothing) ... ok
test_run_stops_at_check_for_raft_lag (upgrade_safety.test_pipeline.CheckGateTest.test_run_stops_at_check_for_raft_lag) ... ok
test_python_dash_m_exit_codes (upgrade_safety.test_pipeline.EntryPointTest.test_python_dash_m_exit_codes) ... ok
test_complete_run_leaves_all_evidence (upgrade_safety.test_pipeline.EvidenceTest.test_complete_run_leaves_all_evidence) ... ok
test_report_escapes_hostile_data (upgrade_safety.test_pipeline.EvidenceTest.test_report_escapes_hostile_data) ... ok
test_report_exists_for_failed_and_awaiting_runs (upgrade_safety.test_pipeline.EvidenceTest.test_report_exists_for_failed_and_awaiting_runs) ... ok
test_report_html_is_escaped_and_has_the_decision (upgrade_safety.test_pipeline.EvidenceTest.test_report_html_is_escaped_and_has_the_decision) ... ok
test_clean_clusters_complete (upgrade_safety.test_pipeline.FaultMatrixTest.test_clean_clusters_complete) ... ok
test_each_fault_stops_where_expected (upgrade_safety.test_pipeline.FaultMatrixTest.test_each_fault_stops_where_expected) ... ok
test_fleet_runs_in_order_and_pauses_on_first_failure (upgrade_safety.test_pipeline.FleetTest.test_fleet_runs_in_order_and_pauses_on_first_failure) ... ok
test_fleet_without_approve_stops_at_first_gate (upgrade_safety.test_pipeline.FleetTest.test_fleet_without_approve_stops_at_first_gate) ... ok
test_unknown_cluster_and_bad_fleet (upgrade_safety.test_pipeline.FleetTest.test_unknown_cluster_and_bad_fleet) ... ok
test_four_quadrants (upgrade_safety.test_pipeline.QuadrantTest.test_four_quadrants) ... ok
test_mixed_version_counts_as_old (upgrade_safety.test_pipeline.QuadrantTest.test_mixed_version_counts_as_old) ... ok
test_existing_run_id_is_not_overwritten (upgrade_safety.test_pipeline.ResumeTest.test_existing_run_id_is_not_overwritten) ... ok
test_mutating_steps_are_idempotent (upgrade_safety.test_pipeline.ResumeTest.test_mutating_steps_are_idempotent) ... ok
test_resume_after_failure_keeps_earlier_work (upgrade_safety.test_pipeline.ResumeTest.test_resume_after_failure_keeps_earlier_work) ... ok
test_resume_does_not_repeat_completed_steps (upgrade_safety.test_pipeline.ResumeTest.test_resume_does_not_repeat_completed_steps) ... ok
test_layer_actions (upgrade_safety.test_pipeline.RollbackAdviceTest.test_layer_actions) ... ok
test_master_failure_fires_trigger_with_control_plane_actions (upgrade_safety.test_pipeline.RollbackAdviceTest.test_master_failure_fires_trigger_with_control_plane_actions) ... ok
test_pdb_stop_fires_no_trigger_and_nothing_executes (upgrade_safety.test_pipeline.RollbackAdviceTest.test_pdb_stop_fires_no_trigger_and_nothing_executes) ... ok
test_triggers_pods_services_alert_flood (upgrade_safety.test_pipeline.RollbackAdviceTest.test_triggers_pods_services_alert_flood) ... ok
test_baseline_regression_alone_blocks_proceed (upgrade_safety.test_pipeline.VerifyTest.test_baseline_regression_alone_blocks_proceed)
Criteria all pass, but fewer pods Running than the baseline: only the baseline diff can see it. ... ok
test_monitor_disagreement_blocks_proceed (upgrade_safety.test_pipeline.VerifyTest.test_monitor_disagreement_blocks_proceed) ... ok
test_new_alert_after_upgrade_is_a_regression_and_human (upgrade_safety.test_pipeline.VerifyTest.test_new_alert_after_upgrade_is_a_regression_and_human) ... ok
test_old_version_healthy_is_rerun (upgrade_safety.test_pipeline.VerifyTest.test_old_version_healthy_is_rerun) ... ok
test_verify_diffs_against_the_baseline_file (upgrade_safety.test_pipeline.VerifyTest.test_verify_diffs_against_the_baseline_file) ... ok
test_verify_refuses_an_incomplete_apply (upgrade_safety.test_pipeline.VerifyTest.test_verify_refuses_an_incomplete_apply) ... ok
test_flagged_preprod_passes (upgrade_safety.test_pipeline.WorkerLayerTest.test_flagged_preprod_passes) ... ok
test_new_node_stuck_when_ccm_unhealthy_now (upgrade_safety.test_pipeline.WorkerLayerTest.test_new_node_stuck_when_ccm_unhealthy_now) ... ok
test_pdb_blocks_drain_and_nothing_is_forced (upgrade_safety.test_pipeline.WorkerLayerTest.test_pdb_blocks_drain_and_nothing_is_forced) ... ok
test_slow_eviction_needs_the_600s_flag (upgrade_safety.test_pipeline.WorkerLayerTest.test_slow_eviction_needs_the_600s_flag) ... ok
test_stateful_nodes_go_first_and_alone (upgrade_safety.test_pipeline.WorkerLayerTest.test_stateful_nodes_go_first_and_alone) ... ok
test_workers_never_lead_the_control_plane (upgrade_safety.test_pipeline.WorkerLayerTest.test_workers_never_lead_the_control_plane) ... ok

----------------------------------------------------------------------
Ran 84 tests in 4.011s

OK

OK
FAIL leak pattern in x.md:1
exit=0
```

## 3.2 the DoD command
```
$ python3 -m upgrade_safety run --fleet testenv/fleet.yaml --cluster prod-canary --target 1.26 --approve; ls runs/*/ runs/*/snapshots; ls runs/*/report.html
[prod-canary] run: COMPLETE  run=20261023-163657-prod-canary-run  steps 36/36 completed
PLAN prod-canary (prod-canary, workload): 1.25 -> 1.26
  blast radius: 3 etcd members tolerate 1; serial=1 => worst case 1 master down (within quorum)
  control plane, per master (each master needs its own sign-off):
    gate -> apiserver -> apiserver_ready -> controller_manager -> scheduler -> kubelet -> verify
    masters in order: prod-canary-m1, prod-canary-m2, prod-canary-m3
  workers: AMI ami-synth-125 -> ami-synth-126 (kubelet 1.26); launch template changes: ami
    batches (stateful nodes first, alone): prod-canary-w1 | prod-canary-w2 | prod-canary-w3 | prod-canary-w4 | prod-canary-w5; drain timeout 600s, never forced
  addons in order: ccm -> cni -> cluster_autoscaler
  verify decision: proceed
  evidence: runs/20261023-163657-prod-canary-run/   report: runs/20261023-163657-prod-canary-run/report.html
runs/20261023-163657-prod-canary-run/:
cluster.json
diff.json
etcd-snapshot.json
execution.log
plan.json
plan.txt
report.html
snapshots
state.json

runs/20261023-163657-prod-canary-run/snapshots:
post.json
pre.json
runs/20261023-163657-prod-canary-run/report.html
exit=0
```

## execution log of that run: per-master sign-off, leader transfer, batches
```
$ grep -E 'SIGNOFF|EVENT|VERIFY|START (check|snapshot|plan)|COMPLETE|batch' runs/*prod-canary-run/execution.log | head -40
2026-10-23T16:36:57+00:00 INFO  START check
2026-10-23T16:36:57+00:00 INFO  START snapshot
2026-10-23T16:36:57+00:00 INFO  START plan
2026-10-23T16:36:57+00:00 INFO  SIGNOFF plan approved by operator (--approve)
2026-10-23T16:36:57+00:00 INFO  SIGNOFF master prod-canary-m1 signed off by operator (--approve), one master at a time (serial=1)
2026-10-23T16:36:57+00:00 INFO  EVENT leader transfer prod-canary-m1 -> prod-canary-m2 is expected during a master upgrade
2026-10-23T16:36:57+00:00 INFO  SIGNOFF master prod-canary-m2 signed off by operator (--approve), one master at a time (serial=1)
2026-10-23T16:36:57+00:00 INFO  EVENT leader transfer prod-canary-m2 -> prod-canary-m1 is expected during a master upgrade
2026-10-23T16:36:57+00:00 INFO  SIGNOFF master prod-canary-m3 signed off by operator (--approve), one master at a time (serial=1)
2026-10-23T16:36:57+00:00 INFO  START workers:batch1
2026-10-23T16:36:57+00:00 INFO  VERIFY service kafka on prod-canary-w1 healthy after replacement (stateful node, alone)
2026-10-23T16:36:57+00:00 INFO  DONE workers:batch1: batch 1: replaced prod-canary-w1 (drain timeout 600s, no force)
2026-10-23T16:36:57+00:00 INFO  START workers:batch2
2026-10-23T16:36:57+00:00 INFO  VERIFY service mysql on prod-canary-w2 healthy after replacement (stateful node, alone)
2026-10-23T16:36:57+00:00 INFO  DONE workers:batch2: batch 2: replaced prod-canary-w2 (drain timeout 600s, no force)
2026-10-23T16:36:57+00:00 INFO  START workers:batch3
2026-10-23T16:36:57+00:00 INFO  DONE workers:batch3: batch 3: replaced prod-canary-w3 (drain timeout 600s, no force)
2026-10-23T16:36:57+00:00 INFO  START workers:batch4
2026-10-23T16:36:57+00:00 INFO  DONE workers:batch4: batch 4: replaced prod-canary-w4 (drain timeout 600s, no force)
2026-10-23T16:36:57+00:00 INFO  START workers:batch5
2026-10-23T16:36:57+00:00 INFO  DONE workers:batch5: batch 5: replaced prod-canary-w5 (drain timeout 600s, no force)
2026-10-23T16:36:57+00:00 INFO  COMPLETE scope=run
exit=0
```

## state file: every step completed
```
$ python3 -c "import json,glob,collections; s=json.load(open(glob.glob('runs/*prod-canary-run/state.json')[0])); print(collections.Counter(x['status'] for x in s['steps'])); print(s['status'], s['decision'])"
Counter({'completed': 36})
complete proceed
exit=0
```

## no --approve: stops at the plan, exit 2, nothing changes
```
$ python3 -m upgrade_safety apply --fleet testenv/fleet.yaml --cluster dev-1 --target 1.26 --run-id acc-noapprove > acc-noapprove.out; echo "apply exit code: $?"; tail -4 acc-noapprove.out; rm acc-noapprove.out; echo "log lines mentioning a master step: $(grep -c 'master:' runs/acc-noapprove/execution.log)"; python3 -c "import json; w=json.load(open('runs/acc-noapprove/cluster.json')); print('masters apiserver versions:', sorted({m['apiserver'] for m in w['masters']}))"
apply exit code: 2
    batches (stateful nodes first, alone): dev-1-w1 | dev-1-w2 | dev-1-w3; drain timeout 300s, never forced
  addons in order: ccm -> cni -> cluster_autoscaler
NOT APPROVED: stopped at gate:plan; nothing was changed. Review the plan, then re-run with --approve (or --resume acc-noapprove --approve). Each master is signed off individually.
  evidence: runs/acc-noapprove/   report: runs/acc-noapprove/report.html
log lines mentioning a master step: 0
masters apiserver versions: ['1.25']
exit=0
```

## 3.3 fault matrix: each planted fault vs ground truth
```
$ for c in prod-east prod-south prod-west prod-eu prod-north; do python3 -m upgrade_safety run --fleet testenv/fleet.yaml --cluster $c --approve --run-id acc-$c > /dev/null; python3 -c "import json,yaml; s=json.load(open('runs/acc-$c/state.json')); f=[x for x in yaml.safe_load(open('testenv/fleet.yaml'))['faults'] if x['cluster']=='$c'][0]; print('%-11s %s stopped_at=%-42s expected=%s' % ('$c', f['id'], s['stopped_at'], f['expect_stop']))"; done
prod-east   F1 stopped_at=check                                      expected=check
prod-south  F2 stopped_at=addon:ccm                                  expected=addon:ccm
prod-west   F3 stopped_at=workers:batch1                             expected=workers:batch1
prod-eu     F4 stopped_at=workers:batch3                             expected=workers:batch
prod-north  F5 stopped_at=master:prod-north-m2:apiserver_ready       expected=master:prod-north-m2:apiserver_ready
exit=0
```

## the apiserver gate in the log (prod-north)
```
$ grep -E 'master:prod-north-m2|prod-north-m3' runs/acc-prod-north/execution.log; python3 -c "import json; m={x['name']:x for x in json.load(open('runs/acc-prod-north/cluster.json'))['masters']}; [print(n, 'apiserver', m[n]['apiserver'], 'cm', m[n]['controller_manager'], 'sched', m[n]['scheduler'], 'kubelet', m[n]['kubelet']) for n in sorted(m)]"; cat runs/acc-prod-north/rollback.json
2026-10-23T16:36:58+00:00 INFO  START master:prod-north-m2:gate
2026-10-23T16:36:58+00:00 INFO  DONE master:prod-north-m2:gate: prod-north-m2 signed off
2026-10-23T16:36:58+00:00 INFO  START master:prod-north-m2:apiserver
2026-10-23T16:36:58+00:00 INFO  DONE master:prod-north-m2:apiserver: apiserver 1.26 started; etcd leader moved prod-north-m2 -> prod-north-m1 (expected, election 1-2 s); readiness is the next gate
2026-10-23T16:36:58+00:00 INFO  START master:prod-north-m2:apiserver_ready
2026-10-23T16:36:58+00:00 ERROR FAIL master:prod-north-m2:apiserver_ready: prod-north-m2: apiserver /readyz failed after upgrade; controller-manager, scheduler and kubelet on this master and all later masters are untouched
prod-north-m1 apiserver 1.26 cm 1.26 sched 1.26 kubelet 1.26
prod-north-m2 apiserver 1.26 cm 1.25 sched 1.25 kubelet 1.25
prod-north-m3 apiserver 1.25 cm 1.25 sched 1.25 kubelet 1.25
{
  "actions": [
    "restore the etcd snapshot taken in this run (data)",
    "downgrade the control-plane binaries on the touched masters (the snapshot does not restore binaries)"
  ],
  "failed_step": "master:prod-north-m2:apiserver_ready",
  "fired_triggers": [
    "master_upgrade_failed"
  ],
  "layer": "control_plane",
  "note": "Declared trigger(s) fired: a human decides and executes; the system never rolls back on its own.",
  "reason": "prod-north-m2: apiserver /readyz failed after upgrade; controller-manager, scheduler and kubelet on this master and all later masters are untouched",
  "recommended": true
}
exit=0
```

## PDB: nothing forced (prod-west)
```
$ grep -E 'FAIL|ROLLBACK' runs/acc-prod-west/execution.log; python3 -c "import json; print('worker AMIs still in use:', sorted({n['ami'] for n in json.load(open('runs/acc-prod-west/cluster.json'))['workers']['nodes']}))"
2026-10-23T16:36:58+00:00 ERROR FAIL workers:batch1: drain of prod-west-w1 blocked by PDB mysql-pdb (allows 0 disruptions); not forced. A human must wait for the PDB or lower minAvailable explicitly. No node in batch 1 was replaced; later batches untouched
2026-10-23T16:36:58+00:00 WARN  ROLLBACK-ADVICE layer=workers fired=none (advice only; a human executes)
worker AMIs still in use: ['ami-synth-125']
exit=0
```

## resume: interrupt, then continue without repeating completed steps
```
$ python3 -m upgrade_safety run --fleet testenv/fleet.yaml --cluster dev-1 --approve --run-id acc-demo --interrupt-at workers:batch1 > /dev/null; echo "interrupted run exit code: $?"; python3 -m upgrade_safety run --fleet testenv/fleet.yaml --cluster dev-1 --approve --resume acc-demo | head -1; echo 'START check lines (completed step, must be 1):'; grep -c 'START check$' runs/acc-demo/execution.log; echo 'START workers:batch1 lines (in-progress step re-ran, must be 2):'; grep -c 'START workers:batch1$' runs/acc-demo/execution.log; echo 'SKIP lines (completed steps not repeated):'; grep -c ' SKIP ' runs/acc-demo/execution.log; grep -E 'INTERRUPT|COMPLETE' runs/acc-demo/execution.log
interrupted run exit code: 130
[dev-1] run: COMPLETE  run=acc-demo  steps 34/34 completed
START check lines (completed step, must be 1):
1
START workers:batch1 lines (in-progress step re-ran, must be 2):
2
SKIP lines (completed steps not repeated):
26
2026-10-23T16:36:59+00:00 WARN  INTERRUPT at workers:batch1 (simulated crash; step left in-progress)
2026-10-23T16:36:59+00:00 INFO  COMPLETE scope=run
exit=0
```

## fleet order and pause on first failure
```
$ python3 -m upgrade_safety run --fleet testenv/fleet.yaml --approve --run-id acc-fleet | grep -E '^\[|FLEET'; python3 -c 'import json; d=json.load(open("runs/acc-fleet/fleet.json")); print("order:", d["order"]); print("stopped_at:", d["stopped_at"]); print("started:", list(d["runs"]))'
[dev-1] run: COMPLETE  run=acc-fleet-dev-1  steps 34/34 completed
[preprod-1] run: COMPLETE  run=acc-fleet-preprod-1  steps 35/35 completed
[prod-canary] run: COMPLETE  run=acc-fleet-prod-canary  steps 36/36 completed
[prod-east] run: FAILED  run=acc-fleet-prod-east  steps 0/36 completed
FLEET PAUSED at prod-east: a human decides how to continue. Not started: prod-eu, prod-north, prod-south, prod-west, mgmt-1
order: ['dev-1', 'preprod-1', 'prod-canary', 'prod-east', 'prod-eu', 'prod-north', 'prod-south', 'prod-west', 'mgmt-1']
stopped_at: prod-east
started: ['dev-1', 'preprod-1', 'prod-canary', 'prod-east']
exit=0
```

## mutation check: can the tests fail?
```
$ python3 tools/mutation_check.py
killed   raft lag limit 1000 -> 3000
killed   apiserver /readyz gate removed
killed   apiserver LB-membership gate removed
killed   next-component guard removed
killed   approval gate removed
killed   completed steps re-executed on resume
killed   PDB check removed from drain
killed   drain timeout ignored
killed   addon order not enforced
killed   CCM rollout health ignored
killed   quadrant: unhealthy still proceeds
killed   baseline regressions ignored
killed   serial may exceed quorum

13/13 mutations killed
exit=0
```

## 3.4 scan, independent grep, openspec
```
$ python3 tools/check_rules.py; grep -rniE -f .leak_patterns.local --exclude-dir=.git --exclude=.leak_patterns.local --exclude-dir=runs . | wc -l; openspec validate c0003-pipeline-skeleton
check_rules: OK
       0
Change 'c0003-pipeline-skeleton' is valid
exit=0
```
