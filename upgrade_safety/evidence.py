"""The run directory: every step leaves evidence here."""
import json
from datetime import datetime, timezone
from pathlib import Path


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class RunDir:
    def __init__(self, base, run_id, create=True):
        self.run_id = run_id
        self.path = Path(base) / run_id
        if create:
            (self.path / "snapshots").mkdir(parents=True, exist_ok=True)

    def exists(self, name):
        return (self.path / name).exists()

    def write_json(self, name, obj):
        p = self.path / name
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")
        tmp.replace(p)  # atomic: a crash never leaves a half-written state file

    def read_json(self, name):
        return json.loads((self.path / name).read_text())

    def write_text(self, name, text):
        p = self.path / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)

    def read_text(self, name):
        p = self.path / name
        return p.read_text() if p.exists() else ""

    def log(self, message, level="INFO"):
        with open(self.path / "execution.log", "a") as fh:
            fh.write(f"{now()} {level:<5} {message}\n")

    def append_jsonl(self, name, obj):
        """Append-only: one JSON object per line, never rewritten."""
        with open(self.path / name, "a") as fh:
            fh.write(json.dumps(obj, sort_keys=True) + "\n")
