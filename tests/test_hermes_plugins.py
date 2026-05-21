from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
FIXTURE = REPO / "tests" / "fixtures" / "hermes-agent"
SKILL_PATH = REPO / "plugins" / "hermes-skill-assimilator"


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


if __name__ == "__main__":
    unittest.main()
