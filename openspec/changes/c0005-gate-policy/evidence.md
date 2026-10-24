# c0005 acceptance evidence

## 3.1 all tests (tail), gate tests (verbose), mutation check
```
$ python3 -m unittest discover 2>&1 | tail -4; python3 -m unittest -v upgrade_safety.test_gate 2>&1 | grep -E 'ok$|Ran|OK|FAIL' ; python3 tools/mutation_check.py
----------------------------------------------------------------------
Ran 146 tests in 8.347s

OK
test_assisted_ignores_approve_and_manual_does_not_run_without_it (upgrade_safety.test_gate.AssistedTest.test_assisted_ignores_approve_and_manual_does_not_run_without_it) ... ok
test_completes_a_prod_class_cluster_without_a_signature (upgrade_safety.test_gate.AssistedTest.test_completes_a_prod_class_cluster_without_a_signature) ... ok
test_manual_same_failure_is_halted_by_operator (upgrade_safety.test_gate.AssistedTest.test_manual_same_failure_is_halted_by_operator) ... ok
test_policy_is_kept_across_resume (upgrade_safety.test_gate.AssistedTest.test_policy_is_kept_across_resume) ... ok
test_precheck_failures_still_stop_under_assisted (upgrade_safety.test_gate.AssistedTest.test_precheck_failures_still_stop_under_assisted) ... ok
test_steps_json_records_the_policy (upgrade_safety.test_gate.AssistedTest.test_steps_json_records_the_policy) ... ok
test_stops_at_the_failed_postcheck_and_nothing_after_it_runs (upgrade_safety.test_gate.AssistedTest.test_stops_at_the_failed_postcheck_and_nothing_after_it_runs) ... ok
test_allowed_on_dev_and_management_unattended (upgrade_safety.test_gate.AutoOnProdIsRefusedTest.test_allowed_on_dev_and_management_unattended) ... ok
test_check_and_plan_are_refused_too (upgrade_safety.test_gate.AutoOnProdIsRefusedTest.test_check_and_plan_are_refused_too) ... ok
test_engine_constructor_refuses_too (upgrade_safety.test_gate.AutoOnProdIsRefusedTest.test_engine_constructor_refuses_too) ... ok
test_fleet_with_auto_pauses_at_the_first_prod_class_cluster (upgrade_safety.test_gate.AutoOnProdIsRefusedTest.test_fleet_with_auto_pauses_at_the_first_prod_class_cluster) ... ok
test_refused_before_a_run_directory_exists (upgrade_safety.test_gate.AutoOnProdIsRefusedTest.test_refused_before_a_run_directory_exists) ... ok
test_auto_refuses_a_plan_with_warnings_assisted_accepts_it (upgrade_safety.test_gate.AutoTest.test_auto_refuses_a_plan_with_warnings_assisted_accepts_it) ... ok
test_auto_stops_on_a_failed_postcheck_unattended (upgrade_safety.test_gate.AutoTest.test_auto_stops_on_a_failed_postcheck_unattended) ... ok
test_manual_without_approve_stays_awaiting (upgrade_safety.test_gate.AutoTest.test_manual_without_approve_stays_awaiting) ... ok
test_auto_only_on_low_risk_types (upgrade_safety.test_gate.PolicyTableTest.test_auto_only_on_low_risk_types) ... ok
test_decision_table (upgrade_safety.test_gate.PolicyTableTest.test_decision_table) ... ok
test_manual_and_assisted_allowed_everywhere (upgrade_safety.test_gate.PolicyTableTest.test_manual_and_assisted_allowed_everywhere) ... ok
test_plan_gate (upgrade_safety.test_gate.PolicyTableTest.test_plan_gate) ... ok
test_signoff_only_under_manual (upgrade_safety.test_gate.PolicyTableTest.test_signoff_only_under_manual) ... ok
test_unknown_policy (upgrade_safety.test_gate.PolicyTableTest.test_unknown_policy) ... ok
Ran 21 tests in 1.846s
OK
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
killed   auto allowed on prod-class clusters
killed   failed postcheck continues
killed   auto accepts plan warnings
killed   assisted demands a signature
killed   contract enum not enforced
killed   contract required not enforced

23/23 mutations killed
exit=0
```

## auto is refused on a prod-class cluster: exit 2, no run directory
```
$ python3 -m upgrade_safety run $F --cluster prod-canary --gate auto --run-id acc-auto-prod; echo cli-exit=$?; if [ -d runs/acc-auto-prod ]; then echo 'run directory exists'; else echo 'no run directory was created'; fi
[prod-canary] REFUSED: gate policy 'auto' is refused for a 'workload' cluster: unattended runs are allowed only on dev-staging and management clusters. Use 'assisted' (a human is woken on every failure) or 'manual'
cli-exit=2
no run directory was created
exit=0
```

## auto on dev-1 runs unattended (no --approve)
```
$ python3 -m upgrade_safety run $F --cluster dev-1 --gate auto --run-id acc-auto-dev | head -1; echo cli-exit=${PIPESTATUS[0]}; grep -c SIGNOFF runs/acc-auto-dev/execution.log; python3 -c "import json; r=[json.loads(l) for l in open('runs/acc-auto-dev/evidence.jsonl')]; print(len(r), 'records; policies', sorted({x['gate_decision']['policy'] for x in r}), 'decided_by', sorted({x['gate_decision']['decided_by'] for x in r}))"
[dev-1] run: COMPLETE  run=acc-auto-dev  gate=auto  steps 31/31 completed
cli-exit=0
0
31 records; policies ['auto'] decided_by ['engine']
exit=0
```

## assisted completes a prod-class cluster with no signatures
```
$ python3 -m upgrade_safety run $F --cluster prod-canary --gate assisted --run-id acc-assisted | head -1; echo cli-exit=${PIPESTATUS[0]}; echo SIGNOFF lines: $(grep -c SIGNOFF runs/acc-assisted/execution.log); grep 'GATE plan' runs/acc-assisted/execution.log; python3 -c "import json; r=[json.loads(l) for l in open('runs/acc-assisted/evidence.jsonl')]; print(len(r), 'records; policies', sorted({x['gate_decision']['policy'] for x in r}), 'decided_by', sorted({x['gate_decision']['decided_by'] for x in r}), 'outcomes', sorted({x['outcome'] for x in r}))"
[prod-canary] run: COMPLETE  run=acc-assisted  gate=assisted  steps 33/33 completed
cli-exit=0
SIGNOFF lines: 0
2026-10-24T05:34:45+00:00 INFO  GATE plan passed by the engine (assisted): diff verdict safe_to_apply (assisted)
33 records; policies ['assisted'] decided_by ['engine'] outcomes ['applied_pass']
exit=0
```

## assisted stops at the failed postcheck; manual halts for the operator on the same failure
```
$ python3 -m upgrade_safety run $F --cluster prod-north --gate assisted --run-id acc-as-north | head -1 | cut -c1-110; python3 -m upgrade_safety run $F --cluster prod-north --approve --run-id acc-man-north | head -1 | cut -c1-110; for r in acc-as-north acc-man-north; do python3 -c "import json; r=[json.loads(l) for l in open('runs/$r/evidence.jsonl')][-1]; print('%-14s %-40s %-20s decision=%s by %s' % ('$r', r['step_id'], r['outcome'], r['gate_decision']['decision'], r['gate_decision']['decided_by']))"; done; python3 -c "import json; m={x['name']:x for x in json.load(open('runs/acc-as-north/cluster.json'))['masters']}; print('m2 apiserver', m['prod-north-m2']['apiserver'], 'cm', m['prod-north-m2']['controller_manager'], '| m3 apiserver', m['prod-north-m3']['apiserver'])"
[prod-north] run: FAILED  run=acc-as-north  gate=assisted  steps 11/33 completed
[prod-north] run: FAILED  run=acc-man-north  gate=manual  steps 11/33 completed
acc-as-north   master:prod-north-m2:apiserver_ready     stopped_postcheck    decision=stop by engine
acc-man-north  master:prod-north-m2:apiserver_ready     halted_by_operator   decision=stop by engine
m2 apiserver 1.26 cm 1.25 | m3 apiserver 1.25
exit=0
```

## auto refuses a plan with warnings; assisted accepts the same plan (unit tests)
```
$ python3 -m unittest -v upgrade_safety.test_gate.AutoTest 2>&1 | tail -9
test_auto_refuses_a_plan_with_warnings_assisted_accepts_it (upgrade_safety.test_gate.AutoTest.test_auto_refuses_a_plan_with_warnings_assisted_accepts_it) ... ok
test_auto_stops_on_a_failed_postcheck_unattended (upgrade_safety.test_gate.AutoTest.test_auto_stops_on_a_failed_postcheck_unattended) ... ok
test_manual_without_approve_stays_awaiting (upgrade_safety.test_gate.AutoTest.test_manual_without_approve_stays_awaiting) ... ok

----------------------------------------------------------------------
Ran 3 tests in 0.337s

OK
exit=0
```

## fleet with --gate auto pauses at the first prod-class cluster
```
$ python3 -m upgrade_safety run $F --gate auto --run-id acc-fleet | grep -E '^\[|FLEET' | cut -c1-120; echo cli-exit=${PIPESTATUS[0]}
[dev-1] run: COMPLETE  run=acc-fleet-dev-1  gate=auto  steps 31/31 completed
[preprod-1] run: COMPLETE  run=acc-fleet-preprod-1  gate=auto  steps 32/32 completed
[prod-canary] REFUSED: gate policy 'auto' is refused for a 'workload' cluster: unattended runs are allowed only on dev-s
FLEET PAUSED at prod-canary: a human decides how to continue. Not started: prod-east, prod-eu, prod-north, prod-south, p
cli-exit=2
exit=0
```

## 3.3 scan, independent grep, openspec
```
$ python3 tools/check_rules.py; grep -rniE -f .leak_patterns.local --exclude-dir=.git --exclude=.leak_patterns.local --exclude-dir=runs --exclude-dir=__pycache__ . | wc -l; openspec validate c0005-gate-policy
check_rules: OK
       0
Change 'c0005-gate-policy' is valid
exit=0
```
