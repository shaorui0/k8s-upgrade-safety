"""The four contracts between layers: snapshot, diff, step, evidence.

Plain JSON Schema (draft-07 subset) files plus a standard-library validator.
Producers validate nothing at runtime; tests validate every artifact a run writes.
"""
import json
from pathlib import Path

from .validator import ContractError, validate_against

KINDS = ("snapshot", "diff", "step", "evidence")
_DIR = Path(__file__).resolve().parent
_cache = {}


def schema(kind):
    if kind not in KINDS:
        raise KeyError(f"unknown contract {kind!r}; known: {', '.join(KINDS)}")
    if kind not in _cache:
        _cache[kind] = json.loads((_DIR / f"{kind}.schema.json").read_text())
    return _cache[kind]


def validate(kind, obj):
    """Raise ContractError listing every violation, or return obj."""
    validate_against(schema(kind), obj)
    return obj


def validate_jsonl(kind, text):
    """Validate every non-empty line of a JSONL document; returns the parsed records."""
    out = []
    for i, line in enumerate(text.splitlines(), 1):
        if line.strip():
            try:
                out.append(validate(kind, json.loads(line)))
            except ContractError as ex:
                raise ContractError([f"line {i}: {p}" for p in ex.problems]) from None
    return out


__all__ = ["ContractError", "KINDS", "schema", "validate", "validate_jsonl"]
