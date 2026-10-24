# c0006 acceptance evidence

## 3.1 all tests (tail), CCM tests (verbose), mutation check
```
$ python3 -m unittest discover 2>&1 | tail -4; python3 -m unittest -v upgrade_safety.test_pipeline.AddonLayerTest upgrade_safety.test_pipeline.WorkerLayerTest 2>&1 | grep -E 'ccm|Ran|OK|FAIL'; python3 tools/mutation_check.py
----------------------------------------------------------------------
Ran 149 tests in 8.239s

OK
test_addon_layer_still_verifies_the_ccm_rollout (upgrade_safety.test_pipeline.AddonLayerTest.test_addon_layer_still_verifies_the_ccm_rollout) ... ok
test_ccm_broken_by_the_new_control_plane_stops_the_worker_layer_before_any_worker (upgrade_safety.test_pipeline.AddonLayerTest.test_ccm_broken_by_the_new_control_plane_stops_the_worker_layer_before_any_worker) ... ok
test_ccm_unhealthy_mid_layer_stops_the_next_batch (upgrade_safety.test_pipeline.AddonLayerTest.test_ccm_unhealthy_mid_layer_stops_the_next_batch) ... ok
test_every_worker_step_carries_the_ccm_precheck (upgrade_safety.test_pipeline.WorkerLayerTest.test_every_worker_step_carries_the_ccm_precheck) ... ok
test_new_node_stuck_when_ccm_unhealthy_now (upgrade_safety.test_pipeline.WorkerLayerTest.test_new_node_stuck_when_ccm_unhealthy_now) ... ok
Ran 12 tests in 1.121s
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
killed   CCM precheck on workers always passes
killed   new apiserver no longer breaks the old CCM
killed   contract enum not enforced
killed   contract required not enforced

25/25 mutations killed
exit=0
```

## 3.2 F2 on prod-south: stop at the worker layer's precheck, control plane done, nothing replaced
```
$ python3 -m upgrade_safety run $F --cluster prod-south --approve --run-id acc-south | grep -E '^\[|STOPPED' | cut -c1-250; python3 - <<'PY'
import json
w = json.load(open('runs/acc-south/cluster.json'))
print('masters components:', sorted({m[k] for m in w['masters'] for k in ('apiserver','controller_manager','scheduler','kubelet')}))
print('asg ami:', w['workers']['asg']['ami'], '| launch template ami:', w['workers']['asg']['launch_template']['ami'], '| worker amis:', sorted({n['ami'] for n in w['workers']['nodes']}))
print('addon versions:', {k: v['version'] for k, v in w['addons'].items()}, '| ccm healthy:', w['addons']['ccm']['healthy'])
last = [json.loads(l) for l in open('runs/acc-south/evidence.jsonl')][-1]
print('last evidence:', last['step_id'], last['outcome'], 'failed:', [a['id'] for a in last['assertions'] if not a['passed']], '| executed:', 'execute' in last)
r = json.load(open('runs/acc-south/rollback.json'))
print('rollback triggers fired:', r['fired_triggers'], '| layer:', r['layer'])
PY
[prod-south] run: FAILED  run=acc-south  gate=manual  steps 22/33 completed
STOPPED at workers:launch_template: precheck 'ccm-healthy' failed: an unhealthy cloud-controller-manager would strand new workers on the uninitialized taint (ccm is UNHEALTHY)
masters components: ['1.26']
asg ami: ami-synth-125 | launch template ami: ami-synth-125 | worker amis: ['ami-synth-125']
addon versions: {'ccm': '1.25', 'cluster_autoscaler': '1.25', 'cni': '1.25'} | ccm healthy: False
last evidence: workers:launch_template stopped_precheck failed: ['ccm-healthy'] | executed: False
rollback triggers fired: [] | layer: worker
exit=0
```

## the check does not see it (it runs before the new control plane exists)
```
$ python3 -m upgrade_safety check $F --cluster prod-south --run-id acc-south-check | head -1
[prod-south] check: COMPLETE  run=acc-south-check  gate=manual  steps 2/33 completed
exit=0
```

## fault matrix: every planted fault stops where the ground truth says
```
$ for c in prod-east prod-south prod-west prod-eu prod-north; do python3 -m upgrade_safety run $F --cluster $c --approve --run-id acc-m-$c > /dev/null; python3 -c "import json,yaml; s=json.load(open('runs/acc-m-$c/state.json')); f=[x for x in yaml.safe_load(open('testenv/fleet.yaml'))['faults'] if x['cluster']=='$c'][0]; print('%-11s %s stopped_at=%-42s expected=%s' % ('$c', f['id'], s['stopped_at'], f['expect_stop']))"; done
prod-east   F1 stopped_at=check                                      expected=check
prod-south  F2 stopped_at=workers:launch_template                    expected=workers:launch_template
prod-west   F3 stopped_at=workers:canary                             expected=workers:canary
prod-eu     F4 stopped_at=workers:batch2                             expected=workers:batch
prod-north  F5 stopped_at=master:prod-north-m2:apiserver_ready       expected=master:prod-north-m2:apiserver_ready
exit=0
```

## addon-layer verification still exists (unit test with a purpose-built fleet)
```
$ python3 -m unittest -v upgrade_safety.test_pipeline.AddonLayerTest.test_addon_layer_still_verifies_the_ccm_rollout 2>&1 | tail -5

----------------------------------------------------------------------
Ran 1 test in 0.141s

OK
exit=0
```

## no document still claims F2 stops in the addon layer
```
$ grep -n 'addon layer stops' README.md docs/*.md testenv/README.md | wc -l; grep -n 'F2' testenv/README.md docs/*.md | cut -c1-160; grep -n -A2 -B1 'F2' testenv/fleet.yaml | cut -c1-200 | head -12
       0
testenv/README.md:12:| `prod-south` | prod | workload | **F2** the old CCM is healthy at `check` but unhealthy once the new control plane is up: the worker laye
docs/REQUIREMENTS.md:35:| R23 | Cloud-controller-manager health is a precheck of every worker-layer step (an unhealthy CCM strands new workers on the uninitiali
1191-  criterion: etcd_raft_lag
1192:- id: F2
1193-  cluster: prod-south
1194-  kind: ccm_unhealthy
exit=0
```

## 3.3 scan, independent grep, openspec
```
$ python3 tools/check_rules.py; grep -rniE -f .leak_patterns.local --exclude-dir=.git --exclude=.leak_patterns.local --exclude-dir=runs --exclude-dir=__pycache__ . | wc -l; openspec validate c0006-ccm-worker-precondition
check_rules: OK
       0
Change 'c0006-ccm-worker-precondition' is valid
exit=0
```
