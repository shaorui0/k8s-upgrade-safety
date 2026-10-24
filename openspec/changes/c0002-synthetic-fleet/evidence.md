# c0002 acceptance evidence

## 3.1 all tests
```
$ python3 -m unittest discover -v 2>&1 | tail -40
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

----------------------------------------------------------------------
Ran 23 tests in 0.517s

OK
exit=0
```

## 3.2 loader table and fault ground truth
```
$ python3 - <<'PY'
from upgrade_safety import model
f = model.load_fleet('testenv/fleet.yaml')
print('%-12s %-12s %-12s %-8s %-6s %s' % ('cluster','stage','type','workers','flag','max_raft_lag'))
for c in f.ordered():
    print('%-12s %-12s %-12s %-8d %-6d %d' % (c['name'], c['stage'], c['cluster_type'], len(c['workers']['nodes']), c['flags']['drain_timeout_s'], max(model.raft_lag(c['etcd']).values())))
print()
for x in f.faults:
    print(x['id'], x['cluster'], x['kind'], '->', x['expect_stop'])
PY
cluster      stage        type         workers  flag   max_raft_lag
dev-1        dev          dev-staging  3        300    80
preprod-1    preprod      dev-staging  4        600    80
prod-canary  prod-canary  workload     5        600    80
prod-east    prod         workload     5        300    2000
prod-eu      prod         workload     5        300    80
prod-north   prod         workload     5        300    80
prod-south   prod         workload     5        300    80
prod-west    prod         workload     5        300    80
mgmt-1       management   management   4        300    80

F1 prod-east raft_lag -> check
F2 prod-south ccm_unhealthy -> addon:ccm
F3 prod-west pdb_blocks_drain -> workers:batch1
F4 prod-eu slow_eviction -> workers:batch
F5 prod-north apiserver_not_ready -> master:prod-north-m2:apiserver_ready
exit=0
```

## regenerating the fleet is byte-identical
```
$ python3 testenv/gen_fleet.py | diff - testenv/fleet.yaml && echo identical
identical
exit=0
```

## 3.3 scan and openspec
```
$ python3 tools/check_rules.py; grep -rniE -f .leak_patterns.local --exclude-dir=.git --exclude=.leak_patterns.local . | wc -l; openspec validate c0002-synthetic-fleet
check_rules: OK
       0
Change 'c0002-synthetic-fleet' is valid
exit=0
```
