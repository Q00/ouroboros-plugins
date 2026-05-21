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


class HermesCronAdapterTests(unittest.TestCase):
    def _run(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, "-m", "ouroboros_hermes_cron", *args], cwd=REPO, env={**os.environ, "PYTHONPATH": str(CRON_PATH)}, capture_output=True, text=True, check=False)

    def test_inspect_preserves_job_metadata_without_execution(self):
        proc = self._run("inspect", str(FIXTURE / "cron" / "jobs.json"))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["summary"]["job_count"], 1)
        self.assertFalse(payload["safety"]["scheduled_jobs"])
        self.assertFalse(payload["safety"]["executed_scripts"])
        job = payload["jobs"][0]
        self.assertEqual(job["id"], "daily-domain-intel")
        self.assertEqual(job["schedule"], "0 9 * * *")
        self.assertEqual(job["risk"], "destructive")
        self.assertIn("shell_execution", job["risk_categories"])
        self.assertIn("shell:execute", job["permissions"])
        self.assertIn("network:write", job["permissions"])

    def test_import_writes_seed_drafts_and_handoff(self):
        with tempfile.TemporaryDirectory() as td:
            proc = self._run("import", str(FIXTURE), "--out", td)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = json.loads(proc.stdout)
            self.assertEqual(payload["status"], "imported")
            self.assertIn("daily-domain-intel.md", payload["seed_drafts"])
            draft = (Path(td) / "seed-drafts" / "daily-domain-intel.md").read_text()
            self.assertIn("Do not schedule it by default", draft)
            self.assertTrue((Path(td) / "hermes-cron-risk-map.json").is_file())




if __name__ == "__main__":
    unittest.main()
