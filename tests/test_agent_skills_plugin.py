from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator


REPO = Path(__file__).resolve().parents[1]
PLUGIN_PATH = REPO / "plugins" / "agent-skills"
MANIFEST = PLUGIN_PATH / "ouroboros.plugin.json"
AUDIT_SCHEMA = REPO / "schemas" / "0.1" / "audit-event.schema.json"
EXPECTED_SKILLS = {
    "api-and-interface-design",
    "browser-testing-with-devtools",
    "ci-cd-and-automation",
    "code-review-and-quality",
    "code-simplification",
    "context-engineering",
    "debugging-and-error-recovery",
    "deprecation-and-migration",
    "documentation-and-adrs",
    "doubt-driven-development",
    "frontend-ui-engineering",
    "git-workflow-and-versioning",
    "idea-refine",
    "incremental-implementation",
    "interview-me",
    "performance-optimization",
    "planning-and-task-breakdown",
    "security-and-hardening",
    "shipping-and-launch",
    "source-driven-development",
    "spec-driven-development",
    "test-driven-development",
    "using-agent-skills",
}
EXPECTED_LIFECYCLE = {"spec", "plan", "build", "test", "review", "code-simplify", "ship"}


class AgentSkillsPluginTests(unittest.TestCase):
    def _run(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-m", "agent_skills_adapter", *args],
            cwd=REPO,
            env={**os.environ, "PYTHONPATH": str(PLUGIN_PATH)},
            capture_output=True,
            text=True,
            check=False,
        )

    def test_manifest_exposes_all_lifecycle_aliases_and_skills(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        command_names = {command["name"] for command in manifest["commands"]}
        self.assertTrue(EXPECTED_LIFECYCLE.issubset(command_names))
        self.assertTrue(EXPECTED_SKILLS.issubset(command_names))
        self.assertEqual(len(manifest["commands"]), 30)
        self.assertEqual({command["namespace"] for command in manifest["commands"]}, {"agent-skills"})
        self.assertEqual(manifest["source"]["repository"], "https://github.com/addyosmani/agent-skills")

    def test_list_skills_reports_upstream_commit(self):
        proc = self._run("--list-skills")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["upstream_commit"], "f17c6e88c904dc747381c374312c2d58e10647ae")
        self.assertEqual(len(payload["skills"]), 23)
        self.assertEqual(len(payload["lifecycle_aliases"]), 7)

    def test_review_writes_handoff_and_audit_artifacts(self):
        with tempfile.TemporaryDirectory() as td:
            proc = self._run(
                "review",
                "--scope",
                "HEAD",
                "--output-dir",
                td,
                "--evidence",
                "unit test evidence",
                "--verification-command",
                "python scripts/validate_contract.py",
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            result = json.loads(proc.stdout)
            handoff = Path(result["handoff_json"])
            audit = Path(result["audit_event_path"])
            self.assertTrue(handoff.is_file())
            self.assertTrue(audit.is_file())
            payload = json.loads(handoff.read_text(encoding="utf-8"))
            event = json.loads(audit.read_text(encoding="utf-8"))
            self.assertEqual(payload["command"]["invoked"], "review")
            self.assertEqual(payload["command"]["upstream_skill"], "code-review-and-quality")
            self.assertEqual(payload["provenance"]["commit"], "f17c6e88c904dc747381c374312c2d58e10647ae")
            self.assertIn("filesystem:write", payload["permissions_used"])
            self.assertTrue(payload["result"]["suitable_for_ooo_auto_handoff"])
            schema = json.loads(AUDIT_SCHEMA.read_text(encoding="utf-8"))
            errors = sorted(
                Draft202012Validator(schema).iter_errors(event),
                key=lambda err: list(err.absolute_path),
            )
            self.assertEqual(errors, [])
            self.assertEqual(event["event_type"], "plugin.completed")
            self.assertEqual(event["result"]["status"], "success")

    def test_browser_command_blocks_without_browser_authority(self):
        with tempfile.TemporaryDirectory() as td:
            proc = self._run("browser-testing-with-devtools", "--scope", "http://localhost:3000", "--output-dir", td)
            self.assertEqual(proc.returncode, 1)
            result = json.loads(proc.stdout)
            self.assertEqual(result["status"], "blocked")
            self.assertTrue(any("browser:devtools" in item for item in result["blocked_conditions"]))

    def test_ship_records_persona_fanout(self):
        with tempfile.TemporaryDirectory() as td:
            proc = self._run("ship", "--scope", "release", "--output-dir", td, "--allow-shell")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = json.loads(Path(json.loads(proc.stdout)["handoff_json"]).read_text(encoding="utf-8"))
            self.assertEqual(payload["ship_fanout"], ["code-reviewer", "security-auditor", "test-engineer"])
            self.assertIn("shell:execute", payload["permissions_used"])


if __name__ == "__main__":
    unittest.main()
