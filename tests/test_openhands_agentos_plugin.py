from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PLUGIN_PATH = REPO / "plugins" / "openhands-agentos"


class OpenHandsAgentOSInspectTests(unittest.TestCase):
    def _run(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, "-m", "openhands_agentos", *args], cwd=REPO, env={**os.environ, "PYTHONPATH": str(PLUGIN_PATH)}, capture_output=True, text=True, check=False)

    def _fake_openhands(self, root: Path) -> Path:
        script = root / "fake-openhands.py"
        script.write_text(textwrap.dedent("""
            #!/usr/bin/env python3
            import sys
            if '--version' in sys.argv:
                print('OpenHands 1.2.3')
                raise SystemExit(0)
            if '--help' in sys.argv:
                print('usage: openhands --headless --json --task TEXT --file PATH --resume ID --last')
                raise SystemExit(0)
            raise SystemExit(99)
        """).strip() + "\n", encoding="utf-8")
        script.chmod(0o755)
        return script

    def test_inspect_reports_fake_cli_without_reading_config_contents(self):
        with tempfile.TemporaryDirectory() as td:
            fake = self._fake_openhands(Path(td))
            proc = self._run("--openhands-bin", str(fake), "inspect")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["status"], "installed")
        self.assertTrue(payload["openhands"]["help_supports"]["headless"])
        self.assertTrue(payload["json_headless_supported"])
        self.assertIn("Only file presence", payload["config"]["native_config"]["note"])

    def test_inspect_reports_missing_cli(self):
        proc = self._run("--openhands-bin", "definitely-missing-openhands", "inspect")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["status"], "missing_openhands_cli")
        self.assertFalse(payload["openhands"]["installed"])

    def test_inspect_reports_missing_explicit_path_as_missing(self):
        with tempfile.TemporaryDirectory() as td:
            missing = Path(td) / "missing-openhands"
            proc = self._run("--openhands-bin", str(missing), "inspect")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["status"], "missing_openhands_cli")
        self.assertFalse(payload["openhands"]["installed"])
        self.assertIsNone(payload["openhands"]["path"])

    def test_manifest_validates_against_schema(self):
        from jsonschema import Draft202012Validator
        manifest = json.loads((PLUGIN_PATH / "ouroboros.plugin.json").read_text(encoding="utf-8"))
        schema = json.loads((REPO / "schemas" / "0.1" / "plugin.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(list(Draft202012Validator(schema).iter_errors(manifest)), [])

if __name__ == "__main__":
    unittest.main()
