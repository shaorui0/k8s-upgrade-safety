# c0004 acceptance evidence

## 4.1 all tests (verbose, tail), tools tests, mutation check
```
$ python3 -m unittest discover -v 2>&1 | tail -40; python3 -m unittest discover -s tools 2>&1 | tail -3; python3 tools/mutation_check.py
Criteria all pass, but fewer pods Running than the baseline: only the baseline diff can see it. ... ok
test_monitor_disagreement_blocks_proceed (upgrade_safety.test_pipeline.VerifyTest.test_monitor_disagreement_blocks_proceed) ... ok
test_new_alert_after_upgrade_is_a_regression_and_human (upgrade_safety.test_pipeline.VerifyTest.test_new_alert_after_upgrade_is_a_regression_and_human) ... ok
test_old_version_healthy_is_rerun (upgrade_safety.test_pipeline.VerifyTest.test_old_version_healthy_is_rerun) ... ok
test_verify_diffs_against_the_baseline_file (upgrade_safety.test_pipeline.VerifyTest.test_verify_diffs_against_the_baseline_file) ... ok
test_verify_refuses_an_incomplete_apply (upgrade_safety.test_pipeline.VerifyTest.test_verify_refuses_an_incomplete_apply) ... ok
test_canary_runs_before_any_batch_and_is_one_node (upgrade_safety.test_pipeline.WorkerLayerTest.test_canary_runs_before_any_batch_and_is_one_node) ... ok
test_flagged_preprod_passes (upgrade_safety.test_pipeline.WorkerLayerTest.test_flagged_preprod_passes) ... ok
test_new_node_stuck_when_ccm_unhealthy_now (upgrade_safety.test_pipeline.WorkerLayerTest.test_new_node_stuck_when_ccm_unhealthy_now) ... ok
test_pdb_blocks_drain_and_nothing_is_forced (upgrade_safety.test_pipeline.WorkerLayerTest.test_pdb_blocks_drain_and_nothing_is_forced) ... ok
test_slow_eviction_needs_the_600s_flag (upgrade_safety.test_pipeline.WorkerLayerTest.test_slow_eviction_needs_the_600s_flag) ... ok
test_stateful_nodes_go_first_and_alone (upgrade_safety.test_pipeline.WorkerLayerTest.test_stateful_nodes_go_first_and_alone) ... ok
test_workers_never_lead_the_control_plane (upgrade_safety.test_pipeline.WorkerLayerTest.test_workers_never_lead_the_control_plane) ... ok
test_complete_run_artifacts_conform (upgrade_safety.test_reconcile.ContractsOnRunsTest.test_complete_run_artifacts_conform) ... ok
test_converged_skip_is_recorded_on_resume_of_a_failed_step (upgrade_safety.test_reconcile.ContractsOnRunsTest.test_converged_skip_is_recorded_on_resume_of_a_failed_step) ... ok
test_doctored_artifact_is_caught (upgrade_safety.test_reconcile.ContractsOnRunsTest.test_doctored_artifact_is_caught) ... ok
test_evidence_is_append_only_across_resume (upgrade_safety.test_reconcile.ContractsOnRunsTest.test_evidence_is_append_only_across_resume) ... ok
test_evidence_outcomes_for_each_kind_of_stop (upgrade_safety.test_reconcile.ContractsOnRunsTest.test_evidence_outcomes_for_each_kind_of_stop) ... ok
test_failed_and_awaiting_runs_conform_too (upgrade_safety.test_reconcile.ContractsOnRunsTest.test_failed_and_awaiting_runs_conform_too) ... ok
test_snapshot_role_enum_rejects_other_roles (upgrade_safety.test_reconcile.ContractsOnRunsTest.test_snapshot_role_enum_rejects_other_roles) ... ok
test_cli_reports_missing_adapter (upgrade_safety.test_reconcile.ExecutorSeamTest.test_cli_reports_missing_adapter) ... ok
test_engine_acts_only_through_the_executor (upgrade_safety.test_reconcile.ExecutorSeamTest.test_engine_acts_only_through_the_executor) ... ok
test_unimplemented_adapters_refuse_loudly (upgrade_safety.test_reconcile.ExecutorSeamTest.test_unimplemented_adapters_refuse_loudly) ... ok
test_baseline_relative_probe_ignores_pre_existing_breakage (upgrade_safety.test_reconcile.ProbeTest.test_baseline_relative_probe_ignores_pre_existing_breakage) ... ok
test_target_tokens_resolve_from_the_snapshot (upgrade_safety.test_reconcile.ProbeTest.test_target_tokens_resolve_from_the_snapshot) ... ok
test_unknown_probe_is_an_error_not_a_pass (upgrade_safety.test_reconcile.ProbeTest.test_unknown_probe_is_an_error_not_a_pass) ... ok
test_a_stale_snapshot_does_not_count (upgrade_safety.test_reconcile.ReversibilityTest.test_a_stale_snapshot_does_not_count) ... ok
test_every_step_declares_reversibility_and_irreversible_ones_name_a_backup (upgrade_safety.test_reconcile.ReversibilityTest.test_every_step_declares_reversibility_and_irreversible_ones_name_a_backup) ... ok
test_irreversible_step_without_backup_is_refused_and_executor_not_called (upgrade_safety.test_reconcile.ReversibilityTest.test_irreversible_step_without_backup_is_refused_and_executor_not_called) ... ok
test_snapshot_is_one_instance_of_the_rule_not_a_special_case (upgrade_safety.test_reconcile.ReversibilityTest.test_snapshot_is_one_instance_of_the_rule_not_a_special_case) ... ok
test_with_a_fresh_snapshot_the_same_step_runs (upgrade_safety.test_reconcile.ReversibilityTest.test_with_a_fresh_snapshot_the_same_step_runs) ... ok
test_signed_step_executes (upgrade_safety.test_reconcile.SignoffTest.test_signed_step_executes) ... ok
test_step_waits_for_a_signature_and_does_not_execute (upgrade_safety.test_reconcile.SignoffTest.test_step_waits_for_a_signature_and_does_not_execute) ... ok
test_built_steps_validate (upgrade_safety.test_reconcile.StepSchemaTest.test_built_steps_validate) ... ok
test_ten_stateless_workers_canary_then_batches_of_two (upgrade_safety.test_reconcile.TierTest.test_ten_stateless_workers_canary_then_batches_of_two) ... ok

----------------------------------------------------------------------
Ran 125 tests in 6.245s

OK

OK
FAIL leak pattern in x.md:1
killed   raft lag limit 1000 -> 3000
killed   apiserver /readyz probe always true
killed   apiserver LB-membership probe always true
killed   next-component guard always passes
killed   step sign-off ignored
killed   plan sign-off ignored
killed   completed steps re-executed on resume
killed   PDB zero-disruption not a blocker
killed   drain timeout ignored
killed   addon order not enforced
killed   CCM rollout health ignored
killed   irreversible step runs without backup
killed   already_done skip disabled
killed   canary widened to the whole first batch
killed   quadrant: unhealthy still proceeds
killed   baseline regressions ignored
killed   serial may exceed quorum
killed   contract enum not enforced
killed   contract required not enforced

19/19 mutations killed
exit=0
```

## 4.2 DoD run on prod-canary, then every artifact validated against the four contracts
```
$ python3 -m upgrade_safety run --fleet testenv/fleet.yaml --cluster prod-canary --target 1.26 --approve --run-id acc-canary | head -3; ls runs/acc-canary; python3 - <<'PY'
import json, pathlib
from upgrade_safety import contracts
rd = pathlib.Path('runs/acc-canary')
snaps = list((rd/'snapshots').rglob('*.json'))
for f in snaps: contracts.validate('snapshot', json.loads(f.read_text()))
contracts.validate('diff', json.loads((rd/'diff.json').read_text()))
steps = json.loads((rd/'steps.json').read_text())
for s in steps: contracts.validate('step', s)
ev = contracts.validate_jsonl('evidence', (rd/'evidence.jsonl').read_text())
print('snapshots valid:', len(snaps), '| steps valid:', len(steps), '| evidence records valid:', len(ev))
print('roles:', sorted({json.loads(f.read_text())['meta']['role'] for f in snaps}))
print('outcomes:', sorted({e['outcome'] for e in ev}))
d = json.loads((rd/'diff.json').read_text())
print('diff.reversible:', d['reversible'], '| changes:', len(d['changes']), '| verdict:', d['verdict']['safe_to_apply'])
print('worker tiers:', [(t['phase'], len(t['nodes'])) for t in d['blast_radius']['worker_tiers']])
print('irreversible steps:', sorted({s['id'].split(':')[-1] for s in steps if not s['reversible']}), 'backup:', {s['backup_precondition'] for s in steps if not s['reversible']})
PY
[prod-canary] run: COMPLETE  run=acc-canary  steps 33/33 completed
PLAN prod-canary (prod-canary, workload): 1.25 -> 1.26
  desired vs observed: 18 change(s); diff is IRREVERSIBLE (control plane in place): needs the etcd snapshot
cluster.json
criteria-baseline.json
criteria-final.json
diff.json
etcd-snapshot.json
evidence.jsonl
execution.log
plan.txt
report.html
snapshots
state.json
steps.json
verify.json
snapshots valid: 60 | steps valid: 29 | evidence records valid: 33
roles: ['baseline', 'postcheck']
outcomes: ['applied_pass']
diff.reversible: False | changes: 18 | verdict: True
worker tiers: [('canary', 1), ('batch', 1), ('rollout', 1), ('rollout', 1), ('rollout', 1)]
irreversible steps: ['apiserver', 'controller_manager', 'kubelet', 'scheduler'] backup: {'etcd-snapshot-fresh'}
exit=0
```

## irreversible step refused without a snapshot; executor never called
```
$ python3 -m unittest -v upgrade_safety.test_reconcile.ReversibilityTest 2>&1 | tail -12
test_a_stale_snapshot_does_not_count (upgrade_safety.test_reconcile.ReversibilityTest.test_a_stale_snapshot_does_not_count) ... ok
test_every_step_declares_reversibility_and_irreversible_ones_name_a_backup (upgrade_safety.test_reconcile.ReversibilityTest.test_every_step_declares_reversibility_and_irreversible_ones_name_a_backup) ... ok
test_irreversible_step_without_backup_is_refused_and_executor_not_called (upgrade_safety.test_reconcile.ReversibilityTest.test_irreversible_step_without_backup_is_refused_and_executor_not_called) ... ok
test_snapshot_is_one_instance_of_the_rule_not_a_special_case (upgrade_safety.test_reconcile.ReversibilityTest.test_snapshot_is_one_instance_of_the_rule_not_a_special_case) ... ok
test_with_a_fresh_snapshot_the_same_step_runs (upgrade_safety.test_reconcile.ReversibilityTest.test_with_a_fresh_snapshot_the_same_step_runs) ... ok

----------------------------------------------------------------------
Ran 5 tests in 0.025s

OK
exit=0
```

## evidence outcome for each kind of stop (last record per run)
```
$ for c in prod-east prod-north prod-west; do python3 -m upgrade_safety run --fleet testenv/fleet.yaml --cluster $c --approve --run-id acc-$c > /dev/null; python3 -c "import json; r=[json.loads(l) for l in open('runs/acc-$c/evidence.jsonl')][-1]; print('%-11s %-40s %-18s failed=%s' % ('$c', r['step_id'], r['outcome'], [a['id'] for a in r['assertions'] if not a['passed']]))"; done; python3 -m upgrade_safety run --fleet testenv/fleet.yaml --cluster dev-1 --run-id acc-gate > /dev/null; python3 -c "import json; r=[json.loads(l) for l in open('runs/acc-gate/evidence.jsonl')][-1]; print('dev-1 (no --approve)', r['step_id'], r['outcome'], r['gate_decision']['decision'])"
prod-east   check                                    stopped_precheck   failed=['etcd_raft_lag']
prod-north  master:prod-north-m2:apiserver_ready     halted_by_operator failed=['readyz', 'lb-member']
prod-west   workers:canary                           stopped_precheck   failed=['no-pdb-block']
dev-1 (no --approve) gate:plan halted_by_operator stop
exit=0
```

## executor seam: real adapters refuse
```
$ python3 -m upgrade_safety check --fleet testenv/fleet.yaml --cluster dev-1 --executor terraform --run-id acc-tf; echo cli-exit=$?
error: no terraform adapter: this repository ships only the simulated executor; a real adapter implements Executor.observe and Executor.execute
cli-exit=2
exit=0
```

## 4.3 scan, independent grep, openspec
```
$ python3 tools/check_rules.py; grep -rniE -f .leak_patterns.local --exclude-dir=.git --exclude=.leak_patterns.local --exclude-dir=runs . | wc -l; openspec validate c0004-contracts-and-reconcile
check_rules: OK
      24
Change 'c0004-contracts-and-reconcile' is valid
exit=0
```
