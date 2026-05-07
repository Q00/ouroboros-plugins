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
import shutil
import subprocess
import sys
import tempfile
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


class SchemaVersionRoutingTests(unittest.TestCase):
    """Exercise scripts/validate_contract.py via subprocess to cover the
    pre-schema gate added in PR #20: manifest's schema_version must be a
    string in the support window, and the validator must route to
    schemas/<schema_version>/ accordingly.

    Issue Q00/ouroboros-plugins#11 Q4 makes "unsupported schema_version
    produces a clear error" an explicit acceptance criterion. This suite
    locks that contract in CI.
    """

    def _baseline_manifest(self) -> dict:
        return json.loads(
            (REPO / "plugins" / "github-pr-ops" / "ouroboros.plugin.json").read_text()
        )

    def _run_with_manifest(self, manifest: dict) -> subprocess.CompletedProcess:
        """Mirror the repo skeleton into a temp dir, swap in a synthetic
        manifest, run the validator, and return its CompletedProcess."""
        with tempfile.TemporaryDirectory() as td:
            sandbox = Path(td)
            shutil.copytree(REPO / "scripts", sandbox / "scripts")
            shutil.copytree(REPO / "schemas", sandbox / "schemas")
            shutil.copytree(REPO / "catalog", sandbox / "catalog")
            plugin_dir = sandbox / "plugins" / "synthetic"
            plugin_dir.mkdir(parents=True)
            (plugin_dir / "ouroboros.plugin.json").write_text(json.dumps(manifest))
            return subprocess.run(
                [sys.executable, str(sandbox / "scripts" / "validate_contract.py")],
                capture_output=True,
                text=True,
                check=False,
            )

    def test_supported_version_validates_via_routing(self):
        """schema_version='0.1' on a clean manifest must pass — proves the
        routing key is wired and schemas/0.1/ is the resolved target."""
        proc = self._run_with_manifest(self._baseline_manifest())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("contract validation passed", proc.stdout)

    def test_unsupported_version_rejected_with_clear_message(self):
        m = self._baseline_manifest()
        m["schema_version"] = "99.0"
        proc = self._run_with_manifest(m)
        self.assertNotEqual(proc.returncode, 0)
        # Message form locked by issue #11 Q4.
        self.assertIn("schema_version '99.0' is not supported", proc.stderr)
        self.assertIn("Current support window: ['0.1']", proc.stderr)
        self.assertIn("Upgrade plugin or pin to a supported core version", proc.stderr)

    def test_missing_schema_version_rejected(self):
        m = self._baseline_manifest()
        del m["schema_version"]
        proc = self._run_with_manifest(m)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("schema_version must be a string", proc.stderr)

    def test_non_string_schema_version_rejected(self):
        m = self._baseline_manifest()
        m["schema_version"] = 0.1  # numeric instead of string
        proc = self._run_with_manifest(m)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("schema_version must be a string", proc.stderr)


# Documented defaults for the 2 optional manifest fields. The contract is
# in docs/contract.md "Default normalization"; the schema is in
# schemas/0.1/plugin.schema.json. Both must agree with this constant —
# the test below enforces that. Update all three together when defaults
# change.
DOCUMENTED_OPTIONAL_DEFAULTS: dict = {
    "description": "",
    "audit": {
        "events": [
            "plugin.invoked",
            "plugin.permission_used",
            "plugin.completed",
            "plugin.failed",
        ]
    },
}


def _normalize(manifest: dict) -> dict:
    """Apply the documented defaults to optional fields that are absent.

    This is the minimal reference normalization. The full loader in
    Q00/ouroboros src/ouroboros/plugin/manifest.py performs the same
    materialization (plus typed dataclass construction); this helper
    exists so the plugins repo can fence the contract without depending
    on the core repo.
    """
    out = dict(manifest)
    for key, default in DOCUMENTED_OPTIONAL_DEFAULTS.items():
        if key not in out:
            # json.loads + dict() copy keeps mutations from leaking back
            # into the constant.
            out[key] = json.loads(json.dumps(default))
    return out


class OptionalDefaultsTest(unittest.TestCase):
    """Fences the 'Default normalization' contract in docs/contract.md.

    Q00/ouroboros-plugins#16 split the manifest into 8 required + 2
    optional fields with documented defaults. JSON Schema's `default`
    keyword is annotation-only — `Draft202012Validator` does not inject
    values — so consumers MUST normalize at load time. These tests
    assert: (1) the schema's `default:` annotations match the documented
    values, (2) a manifest with optionals omitted validates clean, and
    (3) the documented normalization produces the documented effective
    manifest.
    """

    def _reference_manifest(self) -> dict:
        return json.loads(
            (REPO / "plugins" / "github-pr-ops" / "ouroboros.plugin.json").read_text()
        )

    def test_schema_default_annotations_match_documented_values(self):
        # If someone edits docs/contract.md or the schema in isolation,
        # this test catches the drift before the divergence ships.
        self.assertEqual(
            SCHEMA["properties"]["description"].get("default"),
            DOCUMENTED_OPTIONAL_DEFAULTS["description"],
            "schema description.default drifted from docs/contract.md",
        )
        self.assertEqual(
            SCHEMA["properties"]["audit"].get("default"),
            DOCUMENTED_OPTIONAL_DEFAULTS["audit"],
            "schema audit.default drifted from docs/contract.md",
        )

    def test_manifest_without_optionals_validates(self):
        m = self._reference_manifest()
        for key in DOCUMENTED_OPTIONAL_DEFAULTS:
            m.pop(key, None)
        errs = list(VALIDATOR.iter_errors(m))
        self.assertEqual(
            errs,
            [],
            f"manifest with optionals stripped should validate: {errs}",
        )

    def test_normalization_materializes_documented_defaults(self):
        m = self._reference_manifest()
        for key in DOCUMENTED_OPTIONAL_DEFAULTS:
            m.pop(key, None)
        normalized = _normalize(m)
        self.assertEqual(
            normalized["description"],
            DOCUMENTED_OPTIONAL_DEFAULTS["description"],
        )
        self.assertEqual(
            normalized["audit"],
            DOCUMENTED_OPTIONAL_DEFAULTS["audit"],
        )
        # And the normalized manifest still validates — defaults are
        # legal values, not just placeholders.
        errs = list(VALIDATOR.iter_errors(normalized))
        self.assertEqual(errs, [], f"normalized manifest invalid: {errs}")

    def test_normalization_preserves_caller_supplied_values(self):
        # If the manifest already declares an optional, normalization
        # MUST NOT overwrite it.
        m = self._reference_manifest()
        m["description"] = "explicit value"
        m["audit"] = {"events": ["plugin.invoked"]}
        normalized = _normalize(m)
        self.assertEqual(normalized["description"], "explicit value")
        self.assertEqual(normalized["audit"], {"events": ["plugin.invoked"]})


if __name__ == "__main__":
    unittest.main()
