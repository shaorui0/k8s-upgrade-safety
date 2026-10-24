# 0001-requirements-and-method notes

- The real problem was never "manual versus automated". It was that nobody could answer "what evidence says it is safe to do the next step". So the deliverable is a set of gates, not a script.
- Writing the model first forced decisions that prose lets you skip: what exactly fails the check (a number, not "lag looks high"), who is allowed to retry (nobody: every failure ends at a human), what rollback means per layer.
- Counter-intuitive: the rollback is advice, not an action. The triggers are declared before the run; the execution stays with a person, because the control-plane rollback (snapshot restore plus binary downgrade) is the one thing you do not want automated on a bad day.
- The apiserver is the gate inside a master. It anchors version skew, so nothing else on that master moves until `/readyz` and load-balancer membership both pass. "Upgraded" without LB membership means "removed from service".
- Leader transfer during a master upgrade is expected. A member that does not come back is the danger. Gates are framed around the second.
- Clean-room is a design constraint, not paperwork: private patterns in a gitignored file, so the repo never contains the words it guards against. The scan found my own test file first (a fake account number in a unit test), so the test builds it by concatenation.
- The roadmap items in the public write-up (alert gating, synthetic checks, auto-promotion) are targets. The model does not claim them.
