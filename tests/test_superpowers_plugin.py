from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PLUGIN_PATH = REPO / "plugins" / "superpowers"
MANIFEST = json.loads((PLUGIN_PATH / "ouroboros.plugin.json").read_text())
SKILLS_ROOT = PLUGIN_PATH / "vendor" / "superpowers" / "skills"

EXPECTED_SKILLS = {
    "brainstorming",
    "dispatching-parallel-agents",
    "executing-plans",
    "finishing-a-development-branch",
    "receiving-code-review",
    "requesting-code-review",
    "subagent-driven-development",
    "systematic-debugging",
    "test-driven-development",
    "using-git-worktrees",
    "using-superpowers",
    "verification-before-completion",
    "writing-plans",
    "writing-skills",
}


class SuperpowersPluginTests(unittest.TestCase):
    def _run(self, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-m", "superpowers_ouroboros", *args],
            cwd=cwd or REPO,
            env={**os.environ, "PYTHONPATH": str(PLUGIN_PATH)},
            capture_output=True,
            text=True,
            check=False,
        )

    def test_manifest_exposes_every_upstream_skill_command(self):
        vendored = {p.parent.name for p in SKILLS_ROOT.glob("*/SKILL.md")}
        self.assertEqual(vendored, EXPECTED_SKILLS)
        commands = {(c["namespace"], c["name"]) for c in MANIFEST["commands"]}
        for skill in vendored:
            self.assertIn(("superpowers", skill), commands)
        self.assertIn(("superpowers", "list"), commands)
        self.assertIn(("superpowers", "inspect"), commands)
        self.assertIn(("superpowers", "prepare-handoff"), commands)

    def test_list_writes_skill_index_with_upstream_provenance(self):
        with tempfile.TemporaryDirectory() as td:
            proc = self._run("--output-dir", str(Path(td) / ".omx" / "superpowers"), "list")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["skill_count"], len(EXPECTED_SKILLS))
        self.assertEqual({s["name"] for s in payload["skills"]}, EXPECTED_SKILLS)
        self.assertEqual(payload["skills"][0]["upstream_repo"], "https://github.com/obra/superpowers")
        self.assertEqual(payload["skills"][0]["upstream_version"], "v5.1.0")
        self.assertEqual(payload["skills"][0]["upstream_commit"], "f2cbfbefebbfef77321e4c9abc9e949826bea9d7")

    def test_risk_classification_keeps_destructive_workflows_non_destructive_in_v0(self):
        commands = {c["name"]: c for c in MANIFEST["commands"] if c["namespace"] == "superpowers"}
        self.assertEqual(commands["inspect"]["risk"], "read_only")
        self.assertEqual(commands["list"]["risk"], "write")
        self.assertEqual(commands["using-superpowers"]["risk"], "write")
        self.assertEqual(commands["requesting-code-review"]["risk"], "write")
        self.assertEqual(commands["verification-before-completion"]["risk"], "write")
        self.assertEqual(commands["finishing-a-development-branch"]["risk"], "write")
        self.assertTrue(all(c["risk"] != "destructive" for c in commands.values()))

    def test_prepare_handoff_writes_seed_audit_and_provenance(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / ".omx" / "superpowers"
            proc = self._run(
                "--output-dir",
                str(out),
                "prepare-handoff",
                "test-driven-development",
                "--goal",
                "Add retry behavior",
                "--input",
                "network client",
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = json.loads(proc.stdout)
            run_dir = Path(payload["run_dir"])
            for name in ["invocation.json", "provenance.json", "handoff.md", "seed.md", "evidence.json", "audit.jsonl"]:
                self.assertTrue((run_dir / name).is_file(), name)
            invocation = json.loads((run_dir / "invocation.json").read_text())
            provenance = json.loads((run_dir / "provenance.json").read_text())
            evidence = json.loads((run_dir / "evidence.json").read_text())
            handoff = (run_dir / "handoff.md").read_text()
            audit_lines = (run_dir / "audit.jsonl").read_text().splitlines()

        self.assertEqual(invocation["upstream_skill"], "test-driven-development")
        self.assertEqual(provenance["upstream_repo"], "https://github.com/obra/superpowers")
        self.assertEqual(provenance["upstream_skill"], "test-driven-development")
        self.assertIn("failing-test output", handoff)
        self.assertIn("Seed-preparation handoff", handoff)
        self.assertEqual(evidence["status"], "prepared")
        self.assertEqual([json.loads(line)["event"] for line in audit_lines], ["plugin.invoked", "plugin.permission_used", "plugin.completed"])

    def test_skill_command_alias_prepares_handoff_and_excludes_destructive_actions(self):
        with tempfile.TemporaryDirectory() as td:
            proc = self._run(
                "--output-dir",
                str(Path(td) / ".omx" / "superpowers"),
                "finishing-a-development-branch",
                "--input",
                "feature/todo",
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = json.loads(proc.stdout)
            handoff = Path(payload["handoff_path"]).read_text()
        self.assertIn("Destructive upstream actions are report-only in v0", handoff)
        self.assertIn("no merge, push, branch deletion, discard, or PR mutation", handoff)

    def test_unknown_skill_is_rejected(self):
        proc = self._run("inspect", "not-a-skill")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("unknown Superpowers skill", proc.stderr)


if __name__ == "__main__":
    unittest.main()
