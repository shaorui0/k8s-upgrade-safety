PY ?= python3

.PHONY: test check demo mutation

test:   ## unit tests (model, checks, plan, pipeline, scan)
	$(PY) -m unittest discover
	$(PY) -m unittest discover -s tools

check:  ## leak scan + required docs
	$(PY) tools/check_rules.py

demo:   ## upgrade the clean canary cluster end to end, then show the evidence
	$(PY) -m upgrade_safety run --fleet testenv/fleet.yaml --cluster prod-canary --target 1.26 --approve

mutation:  ## break each gate once; the suite must go red every time
	$(PY) tools/mutation_check.py
