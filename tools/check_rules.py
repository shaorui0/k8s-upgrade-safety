#!/usr/bin/env python3
"""Self-check for the public safety of the repository.

Checks:
  1. required documents exist (and README has a Progress table)
  2. no leak pattern appears in any tracked-or-new text file

Leak patterns = generic public ones below + private ones from
`.leak_patterns.local` (one regex per line, gitignored, so the repo never
contains the words it guards against).

Exit 0 = pass, 1 = fail. Usage: python3 tools/check_rules.py [repo_root]
"""
import re
import subprocess
import sys
from pathlib import Path

REQUIRED = [
    "LICENSE",
    "README.md",
    "docs/REQUIREMENTS.md",
    "docs/METHOD.md",
    ".claude/skills/upgrade-change-loop/SKILL.md",
]
PUBLIC_LEAKS = [
    r"(?<![\w.-])\d{12}(?![\w.])",  # cloud account id (all-same-digit placeholders are allowed)
    r"AKIA[0-9A-Z]{16}",           # access key id
    r"/Users/[A-Za-z0-9_.-]+/",    # local home paths
]
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv"}
TEXT_EXT = {".md", ".py", ".json", ".yaml", ".yml", ".html", ".txt", ".sh", ".toml", ""}


def leak_patterns(root):
    pats = list(PUBLIC_LEAKS)
    local = root / ".leak_patterns.local"
    if local.exists():
        pats += [l.strip() for l in local.read_text().splitlines()
                 if l.strip() and not l.startswith("#")]
    return [re.compile(p, re.IGNORECASE) for p in pats]


def repo_files(root):
    try:
        out = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
            cwd=root, capture_output=True, text=True, check=True,
        ).stdout.splitlines()
        return [root / p for p in out if p]
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return [p for p in root.rglob("*") if p.is_file() and not SKIP_DIRS & set(p.parts)]


def check(root, require_docs=True):
    errors = []
    if require_docs:
        for rel in REQUIRED:
            if not (root / rel).exists():
                errors.append(f"missing required file: {rel}")
        readme = root / "README.md"
        if readme.exists() and "## Progress" not in readme.read_text():
            errors.append("README.md has no '## Progress' table")

    pats = leak_patterns(root)
    for f in repo_files(root):
        if f.suffix not in TEXT_EXT or not f.is_file() or f.name == ".leak_patterns.local":
            continue
        try:
            text = f.read_text()
        except UnicodeDecodeError:
            continue
        for p in pats:
            m = next((m for m in p.finditer(text) if len(set(m.group())) > 1), None)
            if m:
                line = text.count("\n", 0, m.start()) + 1
                errors.append(f"leak pattern in {f.relative_to(root)}:{line}")
    return errors


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    root = Path(argv[0]) if argv else Path(__file__).resolve().parent.parent
    errors = check(root)
    for e in errors:
        print(f"FAIL {e}")
    if not errors:
        print("check_rules: OK")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
