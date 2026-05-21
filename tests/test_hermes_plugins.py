from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
FIXTURE = REPO / "tests" / "fixtures" / "hermes-agent"
SKILL_PATH = REPO / "plugins" / "hermes-skill-assimilator"
CRON_PATH = REPO / "plugins" / "hermes-automation-adapter"
RUNNER_PATH = REPO / "plugins" / "hermes-agent-runner"


class HermesSkillAssimilatorTests(unittest.TestCase):
    def _run(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, "-m", "ouroboros_hermes_skill", *args], cwd=REPO, env={**os.environ, "PYTHONPATH": str(SKILL_PATH)}, capture_output=True, text=True, check=False)

    def test_inspect_is_static_and_classifies_risk(self):
        proc = self._run("inspect", str(FIXTURE))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["summary"]["skill_count"], 1)
        self.assertFalse(payload["safety"]["executed_instructions"])
        skill = payload["skills"][0]
        self.assertEqual(skill["name"], "domain-intel")
        self.assertEqual(skill["risk"], "destructive")
        self.assertIn("shell_execution", skill["risk_categories"])
        self.assertIn("shell:execute", skill["permissions"])
        self.assertIn("network:read", skill["permissions"])
        self.assertIn("HERMES_API_KEY", skill["environment_variables"])
        self.assertEqual(payload["summary"]["plugin_manifest_count"], 1)

    def test_convert_writes_handoff_artifacts(self):
        with tempfile.TemporaryDirectory() as td:
            proc = self._run("convert", str(FIXTURE / "skills" / "research" / "domain-intel"), "--out", td)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = json.loads(proc.stdout)
            self.assertEqual(payload["status"], "converted")
            files = set(payload["artifacts"])
            self.assertIn("seed-handoff.md", files)
            self.assertIn("permission-review.md", files)
            cap = json.loads((Path(td) / "hermes-skill-capability-map.json").read_text())
            self.assertFalse(cap["executed_instructions"])
            self.assertIn("shell:execute", cap["permissions_detected"])
            draft = json.loads((Path(td) / "ouroboros.plugin.draft.json").read_text())
            shell_permission = next(p for p in draft["permissions"] if p["scope"] == "shell:execute")
            self.assertEqual(shell_permission["risk"], "destructive")




if __name__ == "__main__":
    unittest.main()
