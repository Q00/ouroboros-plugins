"""Smoke tests for scripts/validate_contract.py.

The happy path is exercised by the script itself (CI runs it). This file
verifies that each negative fixture under tests/fixtures/ is rejected and
that the rejection points at the expected JSON Pointer / message hint.

Run with:
    python3 -m pytest tests/test_validator.py
or:
    python3 tests/test_validator.py  # falls back to a stdlib runner
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from jsonschema import Draft202012Validator  # noqa: E402


SCHEMA = json.loads((REPO / "schemas" / "0.1" / "plugin.schema.json").read_text())
VALIDATOR = Draft202012Validator(SCHEMA)


def first_error(instance: dict):
    errs = sorted(VALIDATOR.iter_errors(instance), key=lambda e: list(e.absolute_path))
    return errs[0] if errs else None


def pointer(err) -> str:
    return "/" + "/".join(str(p) for p in err.absolute_path) if err.absolute_path else ""


class NegativeFixtureTests(unittest.TestCase):
    """Each fixture violates exactly one schema rule; the validator must catch it."""

    def _load(self, name: str) -> dict:
        return json.loads((REPO / "tests" / "fixtures" / name).read_text())

    def test_bad_name_pattern(self):
        err = first_error(self._load("bad-name-pattern.json"))
        self.assertIsNotNone(err, "bad-name-pattern was accepted")
        self.assertEqual(pointer(err), "/name")
        self.assertIn("does not match", err.message)

    def test_bad_unknown_capability(self):
        err = first_error(self._load("bad-unknown-capability.json"))
        self.assertIsNotNone(err)
        self.assertEqual(pointer(err), "/capabilities/0/name")
        self.assertIn("not one of", err.message)

    def test_bad_unknown_source_type(self):
        err = first_error(self._load("bad-unknown-source-type.json"))
        self.assertIsNotNone(err)
        self.assertEqual(pointer(err), "/source/type")

    def test_bad_additional_property(self):
        err = first_error(self._load("bad-additional-property.json"))
        self.assertIsNotNone(err)
        self.assertEqual(pointer(err), "")
        self.assertIn("Additional properties", err.message)

    def test_bad_missing_required(self):
        err = first_error(self._load("bad-missing-required.json"))
        self.assertIsNotNone(err)
        self.assertEqual(pointer(err), "")
        self.assertIn("'name'", err.message)


class ReferenceManifestTest(unittest.TestCase):
    """The reference manifest must validate cleanly."""

    def test_github_pr_ops_validates(self):
        m = json.loads(
            (REPO / "plugins" / "github-pr-ops" / "ouroboros.plugin.json").read_text()
        )
        errs = list(VALIDATOR.iter_errors(m))
        self.assertEqual(errs, [], f"reference manifest invalid: {errs}")


if __name__ == "__main__":
    unittest.main()
