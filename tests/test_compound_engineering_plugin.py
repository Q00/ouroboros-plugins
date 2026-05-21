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
PLUGIN_PATH = REPO / "plugins" / "compound-engineering"


class CompoundEngineeringPluginTests(unittest.TestCase):
    def _run(self, *args: str, repo_root: Path | None = None) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-m", "compound_engineering", *args],
            cwd=REPO,
            env={**os.environ, "PYTHONPATH": str(PLUGIN_PATH)},
            capture_output=True,
            text=True,
            check=False,
        )

    def test_manifest_exposes_every_upstream_skill(self):
        manifest = json.loads((PLUGIN_PATH / "ouroboros.plugin.json").read_text(encoding="utf-8"))
        skills = sorted(path.parent.name for path in (PLUGIN_PATH / "assets" / "skills").glob("*/SKILL.md"))
        commands = manifest["commands"]
        command_names = sorted(command["name"] for command in commands)
        expected = sorted(skill[3:] if skill.startswith("ce-") else skill for skill in skills)

        self.assertEqual(len(skills), 37)
        self.assertEqual(len(list((PLUGIN_PATH / "assets" / "agents").glob("*.agent.md"))), 49)
        self.assertEqual(command_names, expected)
        self.assertEqual({command["namespace"] for command in commands}, {"compound"})

    def test_list_commands_reports_all_commands(self):
        proc = self._run("--list-commands")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertEqual(len(payload), 37)
        self.assertIn("compound brainstorm", {row["command"] for row in payload})
        self.assertIn("compound lfg", {row["command"] for row in payload})

    def test_brainstorm_writes_handoff_and_valid_audit_event(self):
        with tempfile.TemporaryDirectory() as td:
            proc = self._run("brainstorm", "test feature", "--repo-root", td)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = json.loads(proc.stdout)
            self.assertEqual(payload["status"], "success")
            self.assertEqual(payload["source"]["skill"], "ce-brainstorm")
            self.assertIn("compound plan", payload["handoff"]["next_recommended_command"])

            root = Path(td)
            artifact_paths = [root / rel for rel in payload["artifacts"]]
            for path in artifact_paths:
                self.assertTrue(path.is_file(), path)
            audit = json.loads(artifact_paths[2].read_text(encoding="utf-8"))
            schema = json.loads((REPO / "schemas" / "0.1" / "audit-event.schema.json").read_text(encoding="utf-8"))
            errors = list(Draft202012Validator(schema).iter_errors(audit))
            self.assertEqual(errors, [])
            self.assertEqual(audit["provenance"]["upstream_skill"], "ce-brainstorm")

    def test_destructive_command_blocks_without_confirmation(self):
        with tempfile.TemporaryDirectory() as td:
            proc = self._run("clean-gone-branches", "stale branches", "--repo-root", td)
            self.assertEqual(proc.returncode, 1)
            payload = json.loads(proc.stdout)
            self.assertEqual(payload["status"], "blocked")
            self.assertEqual(payload["permissions_used"], ["filesystem:read", "filesystem:write"])
            self.assertIn("git:write", payload["required_permissions"])
            self.assertTrue(any(path.endswith("audit-event.json") for path in payload["artifacts"]))

    def test_destructive_command_can_generate_handoff_with_confirmation(self):
        with tempfile.TemporaryDirectory() as td:
            proc = self._run("lfg", "ship feature", "--confirm", "--repo-root", td)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = json.loads(proc.stdout)
            self.assertEqual(payload["status"], "success")
            self.assertEqual(payload["risk"], "destructive")
            self.assertEqual(payload["permissions_used"], ["filesystem:read", "filesystem:write"])
            self.assertIn("github:pull_request:write", payload["required_permissions"])


if __name__ == "__main__":
    unittest.main()
