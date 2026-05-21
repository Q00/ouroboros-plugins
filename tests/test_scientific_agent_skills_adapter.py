from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PLUGIN_PATH = REPO / "plugins" / "scientific-agent-skills-adapter"
REGISTRY_PATH = PLUGIN_PATH / "scientific_agent_skills_adapter" / "registry.generated.json"
MANIFEST_PATH = PLUGIN_PATH / "ouroboros.plugin.json"


class ScientificAgentSkillsAdapterTests(unittest.TestCase):
    def _run(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-m", "scientific_agent_skills_adapter", *args],
            cwd=REPO,
            env={**os.environ, "PYTHONPATH": str(PLUGIN_PATH)},
            capture_output=True,
            text=True,
            check=False,
        )

    def _json(self, proc: subprocess.CompletedProcess) -> dict:
        try:
            return json.loads(proc.stdout)
        except json.JSONDecodeError as exc:  # pragma: no cover - failure helper
            self.fail(f"stdout was not JSON: {proc.stdout!r}; stderr={proc.stderr!r}; {exc}")

    def test_registry_contains_all_upstream_skills_with_provenance(self):
        registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        skills = registry["skills"]
        self.assertEqual(len(skills), 138)
        slugs = {skill["slug"] for skill in skills}
        self.assertEqual(len(slugs), 138)
        for expected in {"rdkit", "scanpy", "database-lookup", "opentrons-integration"}:
            self.assertIn(expected, slugs)
        for skill in skills:
            self.assertIn(skill["risk"], {"read_only", "write", "destructive"})
            self.assertGreaterEqual(skill["package"].keys(), {"references", "scripts", "assets"})
            self.assertEqual(skill["provenance"]["repository"], "https://github.com/K-Dense-AI/scientific-agent-skills")
            self.assertRegex(skill["provenance"]["source_hash"], r"^[0-9a-f]{64}$")
            self.assertTrue(skill["permissions"])

    def test_manifest_exposes_every_skill_alias(self):
        registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        command_names = {command["name"] for command in manifest["commands"] if command["namespace"] == "scientific"}
        for generic in {"list", "inspect", "explain", "prepare", "run", "trust-report", "doctor"}:
            self.assertIn(generic, command_names)
        for skill in registry["skills"]:
            self.assertIn(skill["slug"], command_names)

    def test_doctor_reports_alias_and_skill_counts(self):
        proc = self._run("doctor")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = self._json(proc)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["skill_count"], 138)
        self.assertEqual(payload["alias_count"], 138)
        self.assertTrue(payload["safety_defaults"]["handoff_first"])

    def test_list_supports_domain_and_risk_filters(self):
        proc = self._run("list", "--domain", "chemistry")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = self._json(proc)
        self.assertGreater(payload["count"], 0)
        self.assertTrue(all(skill["domain"] == "chemistry" for skill in payload["skills"]))

        proc = self._run("list", "--risk", "destructive")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = self._json(proc)
        self.assertGreater(payload["count"], 0)
        self.assertTrue(all(skill["risk"] == "destructive" for skill in payload["skills"]))

    def test_inspect_and_trust_report_include_boundary_metadata(self):
        proc = self._run("inspect", "rdkit")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = self._json(proc)
        self.assertEqual(payload["skill"]["slug"], "rdkit")
        self.assertIn("agentos_boundary", payload)
        self.assertIn("provenance", payload["skill"])

        proc = self._run("trust-report", "opentrons-integration")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = self._json(proc)
        self.assertEqual(payload["skill"], "opentrons-integration")
        self.assertEqual(payload["policy"]["run"], "blocked for write/destructive/manual-review skills; no high-risk upstream script execution")

    def test_prepare_writes_handoff_seed_and_audit_artifacts(self):
        with tempfile.TemporaryDirectory() as td:
            proc = self._run("prepare", "rdkit", "--task", "cluster these molecules", "--output", td)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = self._json(proc)
            self.assertEqual(payload["status"], "prepared")
            self.assertEqual(payload["skill"]["slug"], "rdkit")
            for key in ("handoff", "seed", "audit"):
                self.assertTrue(Path(payload["paths"][key]).is_file(), key)
            handoff = json.loads(Path(payload["paths"]["handoff"]).read_text(encoding="utf-8"))
            self.assertEqual(handoff["task"], "cluster these molecules")
            self.assertIn("auto_handoff", handoff["resume"])
            audit = json.loads(Path(payload["paths"]["audit"]).read_text(encoding="utf-8"))
            self.assertEqual(audit["schema_version"], "0.1")
            self.assertEqual(audit["event_type"], "plugin.completed")
            self.assertIn("skill=rdkit", audit["result"]["message"])

    def test_dry_run_alias_prepares_without_execution(self):
        with tempfile.TemporaryDirectory() as td:
            proc = self._run("scanpy", "--task", "analyze a 10X dataset", "--dry-run", "--output", td)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = self._json(proc)
            self.assertEqual(payload["status"], "dry_run_prepared")
            self.assertEqual(payload["execution"], "not_executed")

    def test_actual_high_risk_run_is_blocked_and_audited(self):
        with tempfile.TemporaryDirectory() as td:
            proc = self._run("run", "opentrons-integration", "--task", "execute protocol", "--output", td)
            self.assertEqual(proc.returncode, 1)
            payload = self._json(proc)
            self.assertEqual(payload["status"], "blocked")
            self.assertTrue(Path(payload["audit_path"]).is_file())
            audit = json.loads(Path(payload["audit_path"]).read_text(encoding="utf-8"))
            self.assertEqual(audit["schema_version"], "0.1")
            self.assertEqual(audit["event_type"], "plugin.failed")
            self.assertEqual(audit["result"]["status"], "blocked")


    def test_generated_audit_events_match_contract_schema(self):
        from jsonschema import Draft202012Validator

        schema = json.loads((REPO / "schemas" / "0.1" / "audit-event.schema.json").read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema)
        with tempfile.TemporaryDirectory() as td:
            proc = self._run("prepare", "rdkit", "--task", "cluster these molecules", "--output", td)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = self._json(proc)
            audit = json.loads(Path(payload["paths"]["audit"]).read_text(encoding="utf-8"))
        self.assertEqual(list(validator.iter_errors(audit)), [])

    def test_unknown_skill_suggests_close_matches(self):
        proc = self._run("inspect", "rdkitt")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("Did you mean", proc.stderr)
        self.assertIn("rdkit", proc.stderr)


if __name__ == "__main__":
    unittest.main()
