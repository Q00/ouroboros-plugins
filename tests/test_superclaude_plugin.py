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
PLUGIN = REPO / "plugins" / "superclaude"
SCHEMA = json.loads((REPO / "schemas" / "0.1" / "plugin.schema.json").read_text())
AUDIT_SCHEMA = json.loads((REPO / "schemas" / "0.1" / "audit-event.schema.json").read_text())
MANIFEST = json.loads((PLUGIN / "ouroboros.plugin.json").read_text())
CATALOG = json.loads((PLUGIN / "command_catalog.json").read_text())

EXPECTED_UPSTREAM_COMMANDS = {
    "agent",
    "analyze",
    "brainstorm",
    "build",
    "business-panel",
    "cleanup",
    "design",
    "document",
    "estimate",
    "explain",
    "git",
    "help",
    "implement",
    "improve",
    "index",
    "index-repo",
    "load",
    "pm",
    "recommend",
    "reflect",
    "research",
    "save",
    "sc",
    "select-tool",
    "spawn",
    "spec-panel",
    "task",
    "test",
    "troubleshoot",
    "workflow",
}
EXPECTED_SKILLS = {
    "brainstorm",
    "confidence-check",
    "deep-research",
    "pm",
    "token-efficiency",
    "troubleshoot",
}


class SuperClaudeManifestTests(unittest.TestCase):
    def test_manifest_validates(self):
        errs = list(Draft202012Validator(SCHEMA).iter_errors(MANIFEST))
        self.assertEqual(errs, [], f"superclaude manifest invalid: {errs}")

    def test_manifest_enumerates_all_upstream_commands(self):
        commands = {cmd["name"]: cmd for cmd in MANIFEST["commands"] if cmd["namespace"] == "superclaude"}
        names = set(commands)
        self.assertTrue(EXPECTED_UPSTREAM_COMMANDS.issubset(names))
        self.assertIn("skill", names)
        self.assertIn("confidence-check", names)
        self.assertIn("token-efficiency", names)
        self.assertEqual(commands["skill"]["risk"], "write")

    def test_sc_alias_is_not_declared_as_namespace(self):
        namespaces = {cmd["namespace"] for cmd in MANIFEST["commands"]}
        self.assertEqual(namespaces, {"superclaude"})

    def test_catalog_records_every_concrete_skill_route(self):
        skills = {item["name"]: item for item in CATALOG["items"] if item["kind"] == "skill"}
        self.assertEqual(set(skills), EXPECTED_SKILLS)
        for name, item in skills.items():
            self.assertTrue((PLUGIN / item["source"]).is_file(), name)
            self.assertIn("ooo superclaude", item["route"])

    def test_agent_and_mode_assets_are_packaged(self):
        agents = [item for item in CATALOG["items"] if item["kind"] == "agent"]
        modes = [item for item in CATALOG["items"] if item["kind"] == "mode"]
        self.assertEqual(len(agents), 20)
        self.assertEqual(len(modes), 7)
        for item in agents + modes:
            self.assertTrue((PLUGIN / item["source"]).is_file(), item)


class SuperClaudeRuntimeTests(unittest.TestCase):
    def _run(self, *args: str, scopes: str | None = None) -> subprocess.CompletedProcess:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(PLUGIN)
        if scopes is not None:
            env["OUROBOROS_TRUSTED_SCOPES"] = scopes
        return subprocess.run(
            [sys.executable, "-m", "superclaude_ouroboros", *args],
            cwd=REPO,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

    def _json(self, proc: subprocess.CompletedProcess) -> dict:
        self.assertTrue(proc.stdout, proc.stderr)
        return json.loads(proc.stdout)

    def test_read_only_analyze_runs_without_write_scope(self):
        proc = self._run("analyze", "src", "--focus", "security")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = self._json(proc)
        self.assertEqual(payload["status"], "success")
        self.assertEqual(payload["required_scopes"], [])
        self.assertEqual(payload["assets"]["command"]["path"], "assets/commands/analyze.md")

    def test_write_command_blocks_without_trust(self):
        proc = self._run("brainstorm", "AgentOS plugin assimilation")
        self.assertEqual(proc.returncode, 1)
        payload = self._json(proc)
        self.assertEqual(payload["status"], "blocked")
        self.assertIn("filesystem:write", payload["missing"])

    def test_write_command_creates_handoff_with_trust(self):
        with tempfile.TemporaryDirectory() as td:
            proc = self._run(
                "brainstorm",
                "AgentOS plugin assimilation",
                "--artifact-dir",
                td,
                scopes="filesystem:write",
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = self._json(proc)
            self.assertEqual(payload["status"], "success")
            handoff = Path(payload["handoff_artifact"])
            self.assertTrue(handoff.is_file())
            self.assertIn("SuperClaude Handoff", handoff.read_text())

    def test_skill_dispatcher_exposes_confidence_check(self):
        proc = self._run("skill", "confidence-check", "implement adapter")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = self._json(proc)
        self.assertEqual(payload["command"]["display"], "skill confidence-check")
        self.assertEqual(payload["assets"]["skill"]["path"], "assets/skills/confidence-check/SKILL.md")


    def test_agent_command_loads_named_agent(self):
        proc = self._run("agent", "security-engineer")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = self._json(proc)
        self.assertEqual(payload["command"]["display"], "agent security-engineer")
        self.assertEqual(payload["assets"]["agent"]["path"], "assets/agents/security-engineer.md")

    def test_sc_dispatcher_routes_nested_command(self):
        proc = self._run("sc", "analyze", "src")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = self._json(proc)
        self.assertEqual(payload["command"]["name"], "analyze")
        self.assertEqual(payload["command"]["display"], "sc analyze")

    def test_research_loads_deep_research_skill(self):
        proc = self._run("research", "AgentOS")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = self._json(proc)
        self.assertEqual(payload["assets"]["skill"]["path"], "assets/skills/deep-research/SKILL.md")

    def test_deep_research_web_requires_network_scope(self):
        proc = self._run("skill", "deep-research", "AgentOS", "--web")
        self.assertEqual(proc.returncode, 1)
        payload = self._json(proc)
        self.assertIn("network:read", payload["missing"])
        proc = self._run("skill", "deep-research", "AgentOS", "--web", scopes="network:read")
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_agent_and_mode_selection_load_assets(self):
        proc = self._run("analyze", "src", "--agent", "security-engineer", "--mode", "DeepResearch")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = self._json(proc)
        self.assertEqual(payload["assets"]["agent"]["path"], "assets/agents/security-engineer.md")
        self.assertEqual(payload["assets"]["mode"]["path"], "assets/modes/MODE_DeepResearch.md")

    def test_destructive_git_requires_scope_and_confirmation(self):
        proc = self._run("git", "reset", "--hard", scopes="shell:execute git:write")
        self.assertEqual(proc.returncode, 1)
        payload = self._json(proc)
        self.assertIn("confirmation:destructive", payload["missing"])
        proc = self._run("git", "reset", "--hard", "--confirm-destructive", scopes="shell:execute git:write")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self._json(proc)["status"], "success")

    def test_audit_events_validate(self):
        with tempfile.TemporaryDirectory() as td:
            proc = self._run("analyze", "src", "--audit-dir", td, scopes="filesystem:write")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = self._json(proc)
            validator = Draft202012Validator(AUDIT_SCHEMA)
            for event in payload["audit_events"]:
                self.assertEqual(list(validator.iter_errors(event)), [])
            audit_lines = (Path(td) / "superclaude-audit.jsonl").read_text().splitlines()
            self.assertEqual(len(audit_lines), len(payload["audit_events"]))


if __name__ == "__main__":
    unittest.main()
