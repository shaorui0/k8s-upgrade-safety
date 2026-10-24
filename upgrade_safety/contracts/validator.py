"""A small JSON Schema validator: exactly the draft-07 subset the contracts use.

Supported: type (name or list), enum, const, required, properties,
additionalProperties (bool or schema), items, minimum, anyOf, $ref to
#/definitions/<name>, if/then, and format "date-time" (ISO 8601 check).
Unknown keywords are ignored on purpose (descriptions, examples, $id).
Collects every violation; never stops at the first.
"""
import re
from datetime import datetime

TYPES = {
    "string": lambda v: isinstance(v, str),
    "boolean": lambda v: isinstance(v, bool),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "null": lambda v: v is None,
}
DATE_TIME = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$")


class ContractError(Exception):
    def __init__(self, problems):
        self.problems = list(problems)
        super().__init__("\n".join(self.problems))


def validate_against(schema, obj):
    problems = []
    _check(schema, obj, "$", schema, problems)
    if problems:
        raise ContractError(problems)


def _resolve(ref, root):
    if not ref.startswith("#/"):
        raise ValueError(f"unsupported $ref {ref!r}")
    node = root
    for part in ref[2:].split("/"):
        node = node[part]
    return node


def _valid(schema, value, root):
    probe = []
    _check(schema, value, "$", root, probe)
    return not probe


def _check(schema, value, path, root, out):
    if "$ref" in schema:
        _check(_resolve(schema["$ref"], root), value, path, root, out)
        return
    if "type" in schema:
        names = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not any(TYPES[n](value) for n in names):
            out.append(f"{path}: expected {'|'.join(names)}, got {type(value).__name__}")
            return
    if "const" in schema and value != schema["const"]:
        out.append(f"{path}: must be {schema['const']!r}, got {value!r}")
    if "enum" in schema and value not in schema["enum"]:
        out.append(f"{path}: {value!r} is not one of {schema['enum']}")
    if "anyOf" in schema and not any(_valid(s, value, root) for s in schema["anyOf"]):
        out.append(f"{path}: matches none of the allowed shapes")
    if schema.get("format") == "date-time" and isinstance(value, str) and not _date_time(value):
        out.append(f"{path}: {value!r} is not an ISO 8601 date-time")
    if "minimum" in schema and TYPES["number"](value) and value < schema["minimum"]:
        out.append(f"{path}: {value} < minimum {schema['minimum']}")
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                out.append(f"{path}: missing required property {key!r}")
        props = schema.get("properties", {})
        extra = schema.get("additionalProperties", True)
        for key, sub in value.items():
            if key in props:
                _check(props[key], sub, f"{path}.{key}", root, out)
            elif extra is False:
                out.append(f"{path}: unexpected property {key!r}")
            elif isinstance(extra, dict):
                _check(extra, sub, f"{path}.{key}", root, out)
    if isinstance(value, list) and "items" in schema:
        for i, item in enumerate(value):
            _check(schema["items"], item, f"{path}[{i}]", root, out)
    if "if" in schema and _valid(schema["if"], value, root) and "then" in schema:
        _check(schema["then"], value, path, root, out)


def _date_time(s):
    if not DATE_TIME.match(s):
        return False
    try:
        datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True
