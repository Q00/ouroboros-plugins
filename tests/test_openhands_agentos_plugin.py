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


class OpenHandsAgentOSPluginTests(unittest.TestCase):
    def _run(self, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-m", "openhands_agentos", *args],
            cwd=REPO,
            env={**os.environ, "PYTHONPATH": str(PLUGIN_PATH), **(env or {})},
            capture_output=True,
            text=True,
            check=False,
        )

    def _fake_openhands(self, root: Path, *, exit_code: int = 0) -> Path:
        script = root / "fake-openhands.py"
        script.write_text(
            textwrap.dedent(
                f"""
                #!/usr/bin/env python3
                import json, os, sys
                if '--version' in sys.argv:
                    print('OpenHands 1.2.3')
                    raise SystemExit(0)
                if '--help' in sys.argv:
                    print('usage: openhands --headless --json --task TEXT --file PATH --resume ID --last')
                    raise SystemExit(0)
                print(json.dumps({{'type': 'command', 'command': 'pytest'}}))
                print(json.dumps({{'type': 'file', 'path': 'src/app.py'}}))
                print(json.dumps({{'type': 'final_answer', 'final_answer': 'done'}}))
                print('human readable log line')
                print('stderr detail', file=sys.stderr)
                assert '--headless' in sys.argv
                assert '--json' in sys.argv
                assert os.environ.get('RUNTIME') in {{'docker', 'process', 'remote'}}
                raise SystemExit({exit_code})
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )
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


    def test_inspect_reports_missing_explicit_path_as_missing(self):
        with tempfile.TemporaryDirectory() as td:
            missing = Path(td) / "missing-openhands"
            proc = self._run("--openhands-bin", str(missing), "inspect")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["status"], "missing_openhands_cli")
        self.assertFalse(payload["openhands"]["installed"])
        self.assertIsNone(payload["openhands"]["path"])

    def test_run_reports_missing_binary_as_blocked(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            missing = root / "missing-openhands"
            proc = self._run("--openhands-bin", str(missing), "run", "--workspace", str(root), "--task", "Do work", "--out", ".omx/artifacts/openhands/test/events.jsonl", "--trusted-shell-execute")
        self.assertEqual(proc.returncode, 1)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["status"], "blocked")
        self.assertIn("not executable", payload["message"])

    def test_run_requires_trusted_shell_execute(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fake = self._fake_openhands(root)
            proc = self._run(
                "--openhands-bin",
                str(fake),
                "run",
                "--workspace",
                str(root),
                "--task",
                "Do work",
                "--out",
                ".omx/artifacts/openhands/test/events.jsonl",
            )
        self.assertEqual(proc.returncode, 1)
        self.assertIn("trusted-shell-execute", proc.stdout)

    def test_run_captures_jsonl_metadata_audit_and_preserves_success(self):
        with tempfile.TemporaryDirectory(prefix="openhands agentos ") as td:
            root = Path(td)
            fake = self._fake_openhands(root)
            proc = self._run(
                "--openhands-bin",
                str(fake),
                "run",
                "--workspace",
                str(root),
                "--task",
                "Do work",
                "--out",
                ".omx/artifacts/openhands/test/events.jsonl",
                "--trusted-shell-execute",
                env={"LLM_API_KEY": "secret-token", "LLM_MODEL": "test-model"},
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = json.loads(proc.stdout)
            events = Path(payload["events_path"])
            metadata = json.loads(Path(payload["metadata_path"]).read_text(encoding="utf-8"))
            audit = Path(payload["audit_path"]).read_text(encoding="utf-8")
            stderr = Path(payload["stderr_path"]).read_text(encoding="utf-8")
            self.assertTrue(events.is_file())
            self.assertEqual(len(events.read_text(encoding="utf-8").splitlines()), 3)
            self.assertEqual(metadata["status"], "completed")
            self.assertEqual(metadata["event_count"], 3)
            self.assertEqual(metadata["environment"]["RUNTIME"], "docker")
            self.assertNotIn("secret-token", json.dumps(metadata))
            self.assertIn("plugin.invoked", audit)
            self.assertIn("plugin.completed", audit)
            self.assertIn("stderr detail", stderr)

    def test_run_preserves_nonzero_exit_code_and_failed_state(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fake = self._fake_openhands(root, exit_code=7)
            proc = self._run(
                "--openhands-bin",
                str(fake),
                "run",
                "--workspace",
                str(root),
                "--task",
                "Do work",
                "--out",
                ".omx/artifacts/openhands/test/events.jsonl",
                "--trusted-shell-execute",
            )
            payload = json.loads(proc.stdout)
            metadata = json.loads(Path(payload["metadata_path"]).read_text(encoding="utf-8"))

        self.assertEqual(proc.returncode, 7)
        self.assertEqual(metadata["status"], "failed")
        self.assertEqual(metadata["exit_code"], 7)

    def test_task_file_and_output_must_stay_inside_workspace(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fake = self._fake_openhands(root)
            outside = root.parent / "outside-task.md"
            outside.write_text("escape", encoding="utf-8")
            proc = self._run(
                "--openhands-bin",
                str(fake),
                "run",
                "--workspace",
                str(root),
                "--task-file",
                str(outside),
                "--out",
                ".omx/artifacts/openhands/test/events.jsonl",
                "--trusted-shell-execute",
            )
        self.assertEqual(proc.returncode, 2)
        self.assertIn("--task-file must stay inside", proc.stderr)

    def test_handoff_and_summarize_generate_reviewable_artifacts(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            events = root / "events.jsonl"
            metadata = root / "metadata.json"
            handoff = root / "handoff.md"
            events.write_text(
                '\n'.join([
                    json.dumps({"type": "command", "command": "pytest"}),
                    json.dumps({"type": "file", "path": "src/app.py"}),
                    json.dumps({"type": "final_answer", "final_answer": "done"}),
                ]) + '\n',
                encoding="utf-8",
            )
            metadata.write_text(json.dumps({"run_id": "r1", "status": "completed", "exit_code": 0, "task": {"kind": "inline", "value": "Do work"}, "artifacts": {"metadata": "metadata.json", "audit": "audit.jsonl", "stderr": "stderr.log"}}), encoding="utf-8")

            sproc = self._run("summarize", "--run", str(events))
            hproc = self._run("handoff", "--run", str(events), "--metadata", str(metadata), "--out", str(handoff))
            self.assertEqual(sproc.returncode, 0, sproc.stderr)
            summary = json.loads(sproc.stdout)
            self.assertEqual(summary["event_count"], 3)
            self.assertIn("pytest", summary["commands_executed"])
            self.assertEqual(hproc.returncode, 0, hproc.stderr)
            self.assertIn("OpenHands AgentOS Handoff", handoff.read_text(encoding="utf-8"))
            self.assertTrue(handoff.with_suffix(".json").is_file())

    def test_agentos_runs_and_writes_handoff(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fake = self._fake_openhands(root)
            proc = self._run(
                "--openhands-bin",
                str(fake),
                "agentos",
                "--workspace",
                str(root),
                "--goal",
                "Do work",
                "--out-dir",
                ".omx/artifacts/openhands/agentos-test",
                "--trusted-shell-execute",
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = json.loads(proc.stdout)
            handoff = Path(payload["handoff_path"])
            self.assertTrue(handoff.is_file())
            self.assertIn("OpenHands AgentOS Handoff", handoff.read_text(encoding="utf-8"))

    def test_manifest_validates_against_schema(self):
        manifest = json.loads((PLUGIN_PATH / "ouroboros.plugin.json").read_text(encoding="utf-8"))
        schema = json.loads((REPO / "schemas" / "0.1" / "plugin.schema.json").read_text(encoding="utf-8"))
        from jsonschema import Draft202012Validator

        errors = list(Draft202012Validator(schema).iter_errors(manifest))
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
