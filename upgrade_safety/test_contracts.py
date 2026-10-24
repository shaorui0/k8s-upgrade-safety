import json
import unittest

from upgrade_safety import contracts
from upgrade_safety.contracts import ContractError
from upgrade_safety.contracts.validator import validate_against

NOW = "2026-10-24T01:02:03+00:00"


def evidence(**kw):
    rec = {"step_id": "master:m1:apiserver", "run_id": "r1", "cluster": "dev-1", "started_at": NOW,
           "finished_at": NOW, "outcome": "applied_pass", "baseline_snapshot": "snapshots/steps/a.baseline.json",
           "postcheck_snapshot": "snapshots/steps/a.postcheck.json", "dry_run_diff": "diff.json", "assertions": [],
           "gate_decision": {"policy": "manual", "decision": "continue", "decided_by": "operator", "reason": "ok"},
           "operator": "operator"}
    rec.update(kw)
    return rec


def step(**kw):
    s = {"id": "x", "goal": "g", "layer": "master", "reversible": True, "precheck": [], "postcheck": [],
         "execute": {"engine": "ansible", "action": "a", "idempotent": True},
         "gate": {"policy": "manual", "signoff": True, "on_fail": "stop"}}
    s.update(kw)
    return s


class ValidatorTest(unittest.TestCase):
    def problems(self, schema, obj):
        try:
            validate_against(schema, obj)
        except ContractError as ex:
            return ex.problems
        return []

    def test_type_enum_required_and_paths(self):
        sch = {"type": "object", "required": ["a"], "additionalProperties": False,
               "properties": {"a": {"type": "string", "enum": ["x", "y"]}, "n": {"type": "integer", "minimum": 1}}}
        self.assertEqual(self.problems(sch, {"a": "x", "n": 3}), [])
        p = self.problems(sch, {"a": "z", "n": 0, "extra": 1})
        self.assertEqual(len(p), 3)
        self.assertTrue(any(x.startswith("$.a:") for x in p))
        self.assertTrue(any("minimum" in x for x in p))
        self.assertTrue(any("unexpected property 'extra'" in x for x in p))
        self.assertIn("$: missing required property 'a'", self.problems(sch, {}))

    def test_bool_is_not_integer_and_null_union(self):
        self.assertTrue(self.problems({"type": "integer"}, True))
        self.assertEqual(self.problems({"type": ["string", "null"]}, None), [])

    def test_items_ref_anyof_const(self):
        sch = {"definitions": {"p": {"type": "string"}}, "type": "array", "items": {"$ref": "#/definitions/p"}}
        self.assertEqual(self.problems(sch, ["a", "b"]), [])
        self.assertIn("$[1]: expected string, got int", self.problems(sch, ["a", 2]))
        self.assertTrue(self.problems({"anyOf": [{"type": "null"}, {"type": "string"}]}, 3))
        self.assertTrue(self.problems({"const": True}, False))

    def test_date_time_format(self):
        sch = {"type": "string", "format": "date-time"}
        self.assertEqual(self.problems(sch, NOW), [])
        self.assertTrue(self.problems(sch, "yesterday"))
        self.assertTrue(self.problems(sch, "2026-13-40T00:00:00+00:00"))


class EvidenceContractTest(unittest.TestCase):
    def test_valid_record(self):
        contracts.validate("evidence", evidence())

    def test_every_outcome_is_accepted_and_others_rejected(self):
        for o in ("converged_skipped", "applied_pass", "stopped_precheck", "stopped_postcheck", "rolled_back",
                  "halted_by_operator"):
            contracts.validate("evidence", evidence(outcome=o))
        with self.assertRaises(ContractError) as cm:
            contracts.validate("evidence", evidence(outcome="done"))
        self.assertIn("$.outcome", str(cm.exception))

    def test_missing_gate_decision_and_bad_policy(self):
        rec = evidence()
        del rec["gate_decision"]
        with self.assertRaises(ContractError):
            contracts.validate("evidence", rec)
        with self.assertRaises(ContractError):
            contracts.validate("evidence", evidence(gate_decision={"policy": "yolo", "decision": "continue",
                                                                  "decided_by": "x", "reason": "r"}))

    def test_jsonl_names_the_line(self):
        text = json.dumps(evidence()) + "\n" + json.dumps(evidence(outcome="nope")) + "\n"
        with self.assertRaises(ContractError) as cm:
            contracts.validate_jsonl("evidence", text)
        self.assertIn("line 2", str(cm.exception))


class StepContractTest(unittest.TestCase):
    def test_reversible_step_needs_no_backup(self):
        contracts.validate("step", step())

    def test_irreversible_step_requires_backup_precondition(self):
        with self.assertRaises(ContractError) as cm:
            contracts.validate("step", step(reversible=False))
        self.assertIn("backup_precondition", str(cm.exception))
        contracts.validate("step", step(reversible=False, backup_precondition="etcd-snapshot-fresh"))

    def test_execute_must_be_idempotent_and_layer_enumerated(self):
        with self.assertRaises(ContractError):
            contracts.validate("step", step(execute={"engine": "ansible", "action": "a", "idempotent": False}))
        with self.assertRaises(ContractError):
            contracts.validate("step", step(layer="addons"))

    def test_assertion_shape(self):
        a = {"id": "a", "probe": "etcd.max_raft_lag", "op": "<=", "expected": 1000, "severity": "block", "why": "w"}
        contracts.validate("step", step(precheck=[a]))
        with self.assertRaises(ContractError):
            contracts.validate("step", step(precheck=[dict(a, op="~=")]))

    def test_all_four_schemas_load_and_have_no_employer_domain_in_id(self):
        for k in contracts.KINDS:
            s = contracts.schema(k)
            self.assertTrue(s["$id"].startswith("upgrade_safety/contracts/"))


if __name__ == "__main__":
    unittest.main()
