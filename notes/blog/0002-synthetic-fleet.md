# 0002-synthetic-fleet notes

- A fault is only evidence for a gate if it is planted before the gate exists. Ground truth (`faults:` in the data) comes first, then each test asserts "this gate stops this fault at this step".
- Faults are data fields, never code keyed on a cluster name. If the simulator branched on `prod-east` the whole exercise would be a fixture built to pass.
- The CCM fault is "healthy today, rollout unhealthy after the upgrade". If the cluster were already unhealthy, `check` would stop it and the addon-layer gate would never be exercised. Where in the pipeline a fault becomes visible is part of the design of the fault.
- Every fault needs a positive twin: a node that evicts in 540 s fails without the 600 s flag and passes with it. Without the twin you cannot tell "the gate works" from "the gate always fails".
- Comments do not survive `yaml.safe_dump`, so the explanation lives in the data (`faults:` list) and a generator, not in YAML comments. Byte-identical regeneration is part of acceptance.
- Validation reports every problem at once. A loader that stops at the first error makes you fix a fleet file one error per run.
- A tiny pit: an unused "bad AMI" fixture sat in the first draft. Deleted: an unexercised fixture is a claim nobody tests.
