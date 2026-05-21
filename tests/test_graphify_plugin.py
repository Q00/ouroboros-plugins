from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PLUGIN_PATH = REPO / "plugins" / "graphify"


class GraphifyPluginTests(unittest.TestCase):
    def _run(self, *args: str, env: dict[str, str] | None = None, cwd: Path | None = None) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-m", "graphify_plugin", *args],
            cwd=cwd or REPO,
            env={**os.environ, "PYTHONPATH": str(PLUGIN_PATH), **(env or {})},
            capture_output=True,
            text=True,
            check=False,
        )

    def test_missing_graphify_returns_blocked_result(self):
        with tempfile.TemporaryDirectory() as td:
            proc = self._run(".", cwd=Path(td), env={"PATH": ""})
        self.assertEqual(proc.returncode, 1)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["status"], "blocked")
        self.assertIn("Graphify is not installed", payload["message"])

    def test_fake_graphify_query_is_read_only(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fake_bin = root / "bin"
            fake_bin.mkdir()
            fake = fake_bin / "graphify"
            fake.write_text("#!/usr/bin/env sh\necho query-result\n", encoding="utf-8")
            fake.chmod(0o755)
            proc = self._run("query", "central modules?", cwd=root, env={"PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}"})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["command"]["family"], "query")
        self.assertEqual(payload["risk"], "read_only")
        self.assertEqual(payload["permissions_used"], ["filesystem:read", "shell:execute"])
        self.assertIn("query-result", payload["stdout_excerpt"])


if __name__ == "__main__":
    unittest.main()
