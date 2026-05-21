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

    def test_missing_graphify_returns_blocked_handoff(self):
        with tempfile.TemporaryDirectory() as td:
            proc = self._run("--no-handoff", ".", cwd=Path(td), env={"PATH": ""})

        self.assertEqual(proc.returncode, 1)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["status"], "blocked")
        self.assertIn("Graphify is not installed", payload["message"])
        self.assertEqual(payload["plugin"]["name"], "graphify")
        self.assertEqual(payload["command"]["family"], "build")

    def test_network_add_is_blocked_without_sensitive_allow(self):
        with tempfile.TemporaryDirectory() as td:
            proc = self._run("--no-handoff", "add", "https://example.com/doc", cwd=Path(td))

        self.assertEqual(proc.returncode, 1)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["status"], "blocked")
        self.assertIn("network:read", payload["permission_sensitive_operations"])
        self.assertTrue(payload["requires_confirmation"])

    def test_fake_graphify_success_records_artifacts_and_graph_stats(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fake_bin = root / "bin"
            fake_bin.mkdir()
            fake = fake_bin / "graphify"
            fake.write_text(
                textwrap.dedent(
                    """\
                    #!/usr/bin/env python3
                    import json, pathlib, sys
                    out = pathlib.Path('graphify-out')
                    out.mkdir(exist_ok=True)
                    (out / 'GRAPH_REPORT.md').write_text('# Report\\n')
                    (out / 'graph.json').write_text(json.dumps({'nodes': [{'id': 'A'}, {'id': 'B'}], 'edges': [{'source': 'A', 'target': 'B'}]}))
                    print('fake graphify ran', ' '.join(sys.argv[1:]))
                    """
                ),
                encoding="utf-8",
            )
            fake.chmod(0o755)

            proc = self._run(
                "--handoff-out",
                "handoff.json",
                ".",
                cwd=root,
                env={"PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}"},
            )

            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = json.loads(proc.stdout)
            self.assertEqual(payload["status"], "completed")
            self.assertEqual(payload["graph_stats"], {"nodes": 2, "edges": 1, "communities": 0})
            artifact_paths = {a["path"] for a in payload["artifacts"]}
            self.assertIn("graphify-out/GRAPH_REPORT.md", artifact_paths)
            self.assertIn("graphify-out/graph.json", artifact_paths)
            handoff = json.loads((root / "handoff.json").read_text(encoding="utf-8"))
            self.assertEqual(handoff["status"], "completed")

    def test_fake_graphify_query_is_read_only(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fake_bin = root / "bin"
            fake_bin.mkdir()
            fake = fake_bin / "graphify"
            fake.write_text("#!/usr/bin/env sh\necho query-result\n", encoding="utf-8")
            fake.chmod(0o755)

            proc = self._run(
                "--no-handoff",
                "query",
                "central modules?",
                cwd=root,
                env={"PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}"},
            )

            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = json.loads(proc.stdout)
            self.assertEqual(payload["command"]["family"], "query")
            self.assertEqual(payload["risk"], "read_only")
            self.assertEqual(payload["permissions_used"], ["filesystem:read", "shell:execute"])
            self.assertIn("query-result", payload["stdout_excerpt"])

    def test_sensitive_allow_flag_works_after_forwarded_args(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fake_bin = root / "bin"
            fake_bin.mkdir()
            fake = fake_bin / "graphify"
            fake.write_text("#!/usr/bin/env sh\necho sensitive-ok\n", encoding="utf-8")
            fake.chmod(0o755)

            proc = self._run(
                "add",
                "https://example.com/doc",
                "--allow-sensitive",
                "--no-handoff",
                cwd=root,
                env={"PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}"},
            )

            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = json.loads(proc.stdout)
            self.assertEqual(payload["status"], "completed")
            self.assertIn("sensitive-ok", payload["stdout_excerpt"])
            self.assertIn("network:read", payload["permission_sensitive_operations"])

    def test_local_paths_must_stay_inside_workspace(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            outside = root.parent / "outside-graphify-target"
            outside.mkdir(exist_ok=True)
            proc = self._run("--no-handoff", str(outside), cwd=root)

        self.assertEqual(proc.returncode, 2)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["status"], "blocked")
        self.assertIn("must stay inside", payload["message"])

    def test_handoff_path_must_stay_inside_workspace(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            proc = self._run(".", "--handoff-out", "../handoff.json", cwd=root)

        self.assertEqual(proc.returncode, 2)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["status"], "blocked")
        self.assertIn("--handoff-out must stay inside", payload["message"])


if __name__ == "__main__":
    unittest.main()
