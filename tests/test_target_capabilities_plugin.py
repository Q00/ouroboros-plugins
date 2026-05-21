from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
PLUGIN_PATH = REPO / "plugins" / "target-capabilities"


class TargetCapabilitiesPluginTests(unittest.TestCase):
    def _run(self, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-m", "target_capabilities", *args],
            cwd=cwd or REPO,
            env={**os.environ, "PYTHONPATH": str(PLUGIN_PATH)},
            capture_output=True,
            text=True,
            check=False,
        )

    def test_list_commands_writes_handoff_artifacts(self):
        with tempfile.TemporaryDirectory() as td:
            cwd = Path(td)
            proc = self._run("list-commands", cwd=cwd)

            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = json.loads(proc.stdout)
            self.assertEqual(payload["status"], "completed")
            self.assertEqual(payload["risk"], "read_only")
            self.assertIn("inspect", {cmd["name"] for cmd in payload["commands"]})
            result_path = cwd / payload["artifacts"]["result.json"]
            handoff_path = cwd / payload["handoff"]
            self.assertTrue(result_path.is_file())
            self.assertTrue(handoff_path.is_file())
            handoff = json.loads(handoff_path.read_text(encoding="utf-8"))
            self.assertEqual(handoff["plugin"], "target-capabilities")
            self.assertEqual(handoff["command"], "list-commands")

    def test_inspect_reports_capability_hints(self):
        with tempfile.TemporaryDirectory() as td:
            cwd = Path(td) / "caller"
            cwd.mkdir()
            target = Path(td) / "target repo"
            target.mkdir()
            (target / "README.md").write_text("# Target\n", encoding="utf-8")
            (target / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")

            proc = self._run(
                "inspect",
                "--target-root",
                str(target),
                "--target-repository",
                "owner/target",
                "--require-file",
                "README.md",
                cwd=cwd,
            )

            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = json.loads(proc.stdout)
            self.assertEqual(payload["status"], "completed")
            self.assertEqual(payload["assimilated_repository"], "owner/target")
            self.assertIn("documentation", {item["capability"] for item in payload["capability_hints"]})
            self.assertIn("python-project", {item["capability"] for item in payload["capability_hints"]})

    def test_inspect_blocks_missing_required_file(self):
        with tempfile.TemporaryDirectory() as td:
            cwd = Path(td) / "caller"
            cwd.mkdir()
            target = Path(td) / "target"
            target.mkdir()
            proc = self._run("inspect", "--target-root", str(target), "--require-file", "README.md", cwd=cwd)

            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = json.loads(proc.stdout)
            self.assertEqual(payload["status"], "blocked")
            self.assertEqual(payload["reason"], "target_required_files_missing")
            self.assertEqual(payload["missing_required_files"], ["README.md"])

    def test_member_paths_must_stay_inside_target(self):
        with tempfile.TemporaryDirectory() as td:
            cwd = Path(td) / "caller"
            cwd.mkdir()
            target = Path(td) / "target"
            target.mkdir()
            proc = self._run("inspect", "--target-root", str(target), "--require-file", "../secret", cwd=cwd)

            self.assertNotEqual(proc.returncode, 0)
            payload = json.loads(proc.stdout)
            self.assertEqual(payload["status"], "blocked")
            self.assertEqual(payload["reason"], "invalid_request")
            self.assertIn("must stay inside", payload["message"])

    def test_doctor_fails_closed_without_target_dependency(self):
        with tempfile.TemporaryDirectory() as td:
            cwd = Path(td)
            proc = self._run("doctor", cwd=cwd)

            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = json.loads(proc.stdout)
            self.assertEqual(payload["status"], "blocked")
            self.assertEqual(payload["reason"], "target_dependency_not_found")



if __name__ == "__main__":
    unittest.main()
