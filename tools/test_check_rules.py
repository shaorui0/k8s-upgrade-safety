import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_rules  # noqa: E402


def make_tree(root, extra=None, patterns=None):
    for rel in check_rules.REQUIRED:
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("## Progress\n" if rel == "README.md" else "ok\n")
    for rel, text in (extra or {}).items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    if patterns:
        (root / ".leak_patterns.local").write_text("\n".join(patterns) + "\n")


class CheckRulesTest(unittest.TestCase):
    def test_clean_tree_passes(self):
        with tempfile.TemporaryDirectory() as d:
            make_tree(Path(d), patterns=["secretword"])
            self.assertEqual(check_rules.check(Path(d)), [])

    def test_planted_private_leak_fails_with_file_and_line(self):
        with tempfile.TemporaryDirectory() as d:
            make_tree(Path(d), {"docs/x.md": "a\nb\nthe SecretWord here\n"}, ["secretword"])
            errs = check_rules.check(Path(d))
            self.assertEqual(errs, ["leak pattern in docs/x.md:3"])

    def test_public_patterns(self):
        with tempfile.TemporaryDirectory() as d:
            # built by concatenation so this file does not trip the scan itself
            make_tree(Path(d), {"a.md": "acct " + "123456" + "789012\n", "b.md": "AK" + "IAABCDEFGHIJKLMNOP\n",
                                "c.md": "/Us" + "ers/someone/x\n", "d.md": "000000000000 placeholder\n"})
            errs = sorted(check_rules.check(Path(d)))
            self.assertEqual(errs, ["leak pattern in a.md:1", "leak pattern in b.md:1", "leak pattern in c.md:1"])

    def test_missing_required_doc_fails(self):
        with tempfile.TemporaryDirectory() as d:
            make_tree(Path(d))
            (Path(d) / "docs/METHOD.md").unlink()
            self.assertIn("missing required file: docs/METHOD.md", check_rules.check(Path(d)))

    def test_main_exit_code(self):
        with tempfile.TemporaryDirectory() as d:
            make_tree(Path(d), {"x.md": "bad\n"}, ["bad"])
            self.assertEqual(check_rules.main([d]), 1)


if __name__ == "__main__":
    unittest.main()
