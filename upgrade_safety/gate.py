"""Gate policy: the one place that turns evidence plus a policy into a decision.

  manual    an operator signs off before each step that asks for it (`--approve`,
            logged per step); a failed postcheck halts the run for the operator.
  assisted  no per-step signature. The plan gate reads the diff verdict; a step
            continues if its postcheck passed and stops if it failed. A human is
            woken only by exceptions. This is where the operator time is saved.
  auto      unattended. Decides like assisted, but also refuses a plan that carries
            warnings (nobody would read them), and is allowed only on low-risk
            cluster types.

Nothing here touches a cluster. Autonomy is bounded by cluster class, not by an
operator remembering to be careful.
"""

POLICIES = ("manual", "assisted", "auto")
AUTO_ALLOWED_TYPES = ("dev-staging", "management")


class GatePolicyError(Exception):
    pass


def validate_policy(policy, cluster_type):
    if policy not in POLICIES:
        raise GatePolicyError(f"unknown gate policy {policy!r}; known: {', '.join(POLICIES)}")
    if policy == "auto" and cluster_type not in AUTO_ALLOWED_TYPES:
        raise GatePolicyError(
            f"gate policy 'auto' is refused for a {cluster_type!r} cluster: unattended runs are allowed only on "
            f"{' and '.join(AUTO_ALLOWED_TYPES)} clusters. Use 'assisted' (a human is woken on every failure) or 'manual'")


def needs_signoff(policy, step):
    """Only manual asks for a signature, and only on steps that declare `signoff`."""
    return policy == "manual" and step["gate"]["signoff"]


def plan_gate(policy, verdict, approved):
    """Decide whether the plan may proceed. Returns (proceed, awaiting, decided_by, reason)."""
    if policy == "manual":
        if approved:
            return True, False, "operator", "plan approved"
        return False, True, "engine", "gate:plan needs a human sign-off (re-run with --approve)"
    if not verdict["safe_to_apply"]:
        return False, False, "engine", "diff verdict is not safe_to_apply"
    if policy == "auto" and verdict["warnings"]:
        return False, False, "engine", ("auto refuses a plan that carries warnings nobody will read: "
                                        + "; ".join(verdict["warnings"]))
    return True, False, "engine", f"diff verdict safe_to_apply ({policy})"


def decide(policy, postcheck_ok, operator, on_fail="stop"):
    """After a postcheck. Returns (gate_decision dict for evidence, outcome)."""
    if postcheck_ok:
        who = operator if policy == "manual" else "engine"
        why = ("postcheck passed and the operator signed off" if policy == "manual"
               else f"postcheck passed ({policy}: no human in the loop on success)")
        return {"policy": policy, "decision": "continue", "decided_by": who, "reason": why}, "applied_pass"
    if policy == "manual":
        return {"policy": policy, "decision": on_fail, "decided_by": "engine",
                "reason": "postcheck failed: stop, a human reads the evidence"}, "halted_by_operator"
    return {"policy": policy, "decision": on_fail, "decided_by": "engine",
            "reason": f"postcheck failed ({policy}): stop, a human is woken"}, "stopped_postcheck"
