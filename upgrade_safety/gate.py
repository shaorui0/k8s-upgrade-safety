"""Gate policy: turns "did the postcheck pass?" plus a policy into a decision.

Only `manual` exists in this change: a human signs off before a step executes
(`--approve`, logged per step) and the step continues only if its postcheck
passes. Progressive autonomy (assisted, auto) is the next change.
"""

POLICIES = ("manual",)


class GatePolicyError(Exception):
    pass


def validate_policy(policy, cluster_type):
    if policy not in POLICIES:
        raise GatePolicyError(f"gate policy {policy!r} is not available; known: {', '.join(POLICIES)}")


def needs_signoff(policy, step):
    return policy == "manual" and step["gate"]["signoff"]


def decide(policy, postcheck_ok, operator, on_fail="stop"):
    """Returns the evidence gate_decision dict and the outcome it implies."""
    if postcheck_ok:
        return {"policy": policy, "decision": "continue", "decided_by": operator,
                "reason": "postcheck passed and the operator signed off"}, "applied_pass"
    return {"policy": policy, "decision": on_fail, "decided_by": "engine",
            "reason": "postcheck failed: stop, a human reads the evidence"}, "halted_by_operator"
