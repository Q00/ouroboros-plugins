from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
PLUGIN_PATH = REPO / "plugins" / "swe-agent-harness"


class SweAgentHarnessPluginTests(unittest.TestCase):
    def _run(self, *args: str, extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-m", "swe_agent_harness", *args],
            cwd=REPO,
            env={**os.environ, "PYTHONPATH": str(PLUGIN_PATH), **(extra_env or {})},
            capture_output=True,
            text=True,
            check=False,
        )

    def _fixture_output(self, root: Path) -> Path:
        output = root / "swe-output" / "instance-1"
        output.mkdir(parents=True)
        (output / "instance-1.traj").write_text('{"exit_status":"submitted"}\n', encoding="utf-8")
        (output / "instance-1.pred").write_text('{"model_patch":"patch"}\n', encoding="utf-8")
        (output / "instance-1.patch").write_text(
            "diff --git a/foo.py b/foo.py\n--- a/foo.py\n+++ b/foo.py\n@@\n-print('old')\n+print('new')\n",
            encoding="utf-8",
        )
        (output / "config.yaml").write_text("agent:\n  model:\n    name: test\n", encoding="utf-8")
        (output / "run.info.log").write_text("done\n", encoding="utf-8")
        return root / "swe-output"

    def test_collect_artifacts_writes_agentos_bundle(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = self._fixture_output(root)
            bundle = root / "bundle"

            proc = self._run("collect-artifacts", str(source), "--agentos-artifact-dir", str(bundle), "--status", "submitted")

            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = json.loads(proc.stdout)
            self.assertEqual(payload["status"], "submitted")
            for name in ["run-spec.json", "provenance.json", "audit-summary.json", "handoff.json", "handoff.md", "patch.diff", "prediction.pred", "trajectory.traj"]:
                self.assertTrue((bundle / name).is_file(), name)
            handoff = json.loads((bundle / "handoff.json").read_text(encoding="utf-8"))
            self.assertEqual(handoff["edited_files"], ["foo.py"])
            self.assertIn("open PR only", "\n".join(handoff["next_steps"]))

    def test_verify_artifacts_reports_valid_bundle(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = self._fixture_output(root)
            bundle = root / "bundle"
            collect = self._run("collect-artifacts", str(source), "--agentos-artifact-dir", str(bundle))
            self.assertEqual(collect.returncode, 0, collect.stderr)

            proc = self._run("verify-artifacts", str(bundle))

            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = json.loads(proc.stdout)
            self.assertEqual(payload["status"], "valid")
            self.assertEqual(payload["missing"], [])

    def test_read_only_stats_over_existing_artifacts(self):
        with tempfile.TemporaryDirectory() as td:
            source = self._fixture_output(Path(td))

            inspect_proc = self._run("inspect", str(source))
            stats_proc = self._run("quick-stats", str(source))

            self.assertEqual(inspect_proc.returncode, 0, inspect_proc.stderr)
            self.assertEqual(stats_proc.returncode, 0, stats_proc.stderr)
            inspect_payload = json.loads(inspect_proc.stdout)
            stats_payload = json.loads(stats_proc.stdout)
            self.assertEqual(inspect_payload["risk"], "read_only")
            self.assertEqual(stats_payload["risk"], "read_only")
            self.assertEqual(stats_payload["counts"]["patch"], 1)
            self.assertEqual(stats_payload["counts"]["trajectory"], 1)

    def test_run_blocks_without_shell_runtime_trust(self):
        with tempfile.TemporaryDirectory() as td:
            bundle = Path(td) / "bundle"
            proc = self._run("run", "--agentos-artifact-dir", str(bundle), "--config", "config/default.yaml")

            self.assertEqual(proc.returncode, 1)
            payload = json.loads(proc.stdout)
            self.assertEqual(payload["status"], "blocked")
            self.assertIn("missing shell/runtime trust", payload["reason"])
            audit = json.loads((bundle / "audit-summary.json").read_text(encoding="utf-8"))
            self.assertEqual(audit["status"], "blocked")
            self.assertFalse(
                [event for event in audit["events"] if event["type"] == "plugin.permission_used"]
            )

    def test_dry_run_preserves_upstream_args_and_writes_metadata(self):
        with tempfile.TemporaryDirectory() as td:
            bundle = Path(td) / "bundle"
            proc = self._run(
                "run",
                "--agentos-dry-run",
                "--agentos-artifact-dir",
                str(bundle),
                "--config",
                "config/default.yaml",
                "--agent.model.name",
                "gpt-4o",
            )

            self.assertEqual(proc.returncode, 0, proc.stderr)
            spec = json.loads((bundle / "run-spec.json").read_text(encoding="utf-8"))
            self.assertIn("--agent.model.name", spec["upstream_command"])
            self.assertIn("--output_dir", spec["upstream_command"])
            self.assertEqual(spec["status"], "partial")

    def test_allowed_run_invokes_configured_sweagent_and_collects_patch(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fake = root / "fake-sweagent.py"
            fake.write_text(
                "#!/usr/bin/env python3\n"
                "import pathlib, sys\n"
                "args = sys.argv[1:]\n"
                "output = pathlib.Path(args[args.index('--output_dir') + 1])\n"
                "inst = output / 'inst'\n"
                "inst.mkdir(parents=True, exist_ok=True)\n"
                "(inst / 'inst.patch').write_text('diff --git a/a.py b/a.py\\n+++ b/a.py\\n')\n"
                "(inst / 'inst.traj').write_text('{}')\n"
                "(inst / 'inst.pred').write_text('{}')\n"
                "print('fake sweagent ran')\n",
                encoding="utf-8",
            )
            fake.chmod(0o755)
            bundle = root / "bundle"

            proc = self._run("run", "--agentos-allow-execute", "--agentos-sweagent-bin", str(fake), "--agentos-artifact-dir", str(bundle), "--config", "config/default.yaml")

            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = json.loads(proc.stdout)
            self.assertEqual(payload["status"], "submitted")
            self.assertTrue((bundle / "patch.diff").is_file())
            self.assertIn("fake sweagent ran", (bundle / "stdout.log").read_text(encoding="utf-8"))


    def test_symlinked_artifacts_are_not_copied_or_normalized(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "swe-output" / "instance-1"
            source.mkdir(parents=True)
            secret = root / "outside-secret.txt"
            secret.write_text("do-not-copy\n", encoding="utf-8")
            try:
                os.symlink(secret, source / "instance-1.patch")
                os.symlink(root, source / "linked-dir")
            except (OSError, NotImplementedError):
                self.skipTest("symlink creation is unavailable")
            (source / "instance-1.traj").write_text("{}", encoding="utf-8")
            bundle = root / "bundle"

            proc = self._run("collect-artifacts", str(root / "swe-output"), "--agentos-artifact-dir", str(bundle))

            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertFalse((bundle / "patch.diff").exists())
            for artifact in bundle.rglob("*"):
                if artifact.is_file() and not artifact.is_symlink():
                    self.assertNotIn("do-not-copy", artifact.read_text(encoding="utf-8", errors="ignore"))
            self.assertFalse((bundle / "swe-agent-output" / "instance-1" / "linked-dir").exists())

    def test_argv_secrets_are_redacted_from_all_metadata(self):
        with tempfile.TemporaryDirectory() as td:
            bundle = Path(td) / "bundle"
            proc = self._run(
                "run",
                "--agentos-dry-run",
                "--agentos-artifact-dir",
                str(bundle),
                "--api-key",
                "sk-test-secret",
                "--github-token=ghp_test_secret",
            )

            self.assertEqual(proc.returncode, 0, proc.stderr)
            combined = "\n".join(
                path.read_text(encoding="utf-8", errors="ignore")
                for path in bundle.rglob("*")
                if path.is_file()
            )
            self.assertNotIn("sk-test-secret", combined)
            self.assertNotIn("ghp_test_secret", combined)
            self.assertIn("<redacted>", combined)

    def test_failed_run_with_patch_remains_failed_in_audit(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fake = root / "fake-sweagent-fails.py"
            fake.write_text(
                "#!/usr/bin/env python3\n"
                "import pathlib, sys\n"
                "args = sys.argv[1:]\n"
                "output = pathlib.Path(args[args.index('--output_dir') + 1])\n"
                "inst = output / 'inst'\n"
                "inst.mkdir(parents=True, exist_ok=True)\n"
                "(inst / 'inst.patch').write_text('diff --git a/a.py b/a.py\\n+++ b/a.py\\n')\n"
                "sys.exit(2)\n",
                encoding="utf-8",
            )
            fake.chmod(0o755)
            bundle = root / "bundle"

            proc = self._run("run", "--agentos-allow-execute", "--agentos-sweagent-bin", str(fake), "--agentos-artifact-dir", str(bundle))

            self.assertEqual(proc.returncode, 1)
            payload = json.loads(proc.stdout)
            self.assertEqual(payload["status"], "failed")
            self.assertTrue((bundle / "patch.diff").is_file())
            run_spec = json.loads((bundle / "run-spec.json").read_text(encoding="utf-8"))
            audit = json.loads((bundle / "audit-summary.json").read_text(encoding="utf-8"))
            self.assertEqual(run_spec["status"], "failed")
            self.assertEqual(audit["events"][-1]["type"], "plugin.failed")

    def test_mutation_hints_stay_blocked_even_with_allow_flags(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fake = root / "fake-sweagent.py"
            fake.write_text("#!/usr/bin/env python3\nprint('should not run')\n", encoding="utf-8")
            fake.chmod(0o755)
            open_pr_bundle = root / "open-pr-bundle"
            apply_bundle = root / "apply-bundle"

            open_pr = self._run(
                "run",
                "--agentos-allow-execute",
                "--agentos-allow-open-pr",
                "--agentos-sweagent-bin",
                str(fake),
                "--agentos-artifact-dir",
                str(open_pr_bundle),
                "--open-pr",
                "true",
            )
            apply_patch = self._run(
                "run",
                "--agentos-allow-execute",
                "--agentos-allow-host-patch",
                "--agentos-sweagent-bin",
                str(fake),
                "--agentos-artifact-dir",
                str(apply_bundle),
                "--apply-to-repo",
                str(root),
            )

            self.assertEqual(open_pr.returncode, 1)
            self.assertEqual(apply_patch.returncode, 1)
            self.assertEqual(json.loads(open_pr.stdout)["status"], "blocked")
            self.assertEqual(json.loads(apply_patch.stdout)["status"], "blocked")
            self.assertEqual((open_pr_bundle / "stdout.log").read_text(encoding="utf-8"), "")
            self.assertEqual((apply_bundle / "stdout.log").read_text(encoding="utf-8"), "")


    def test_real_run_redacts_argv_secrets_from_captured_logs(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fake = root / "fake-sweagent-echo.py"
            fake.write_text(
                "#!/usr/bin/env python3\n"
                "import pathlib, sys\n"
                "args = sys.argv[1:]\n"
                "output = pathlib.Path(args[args.index('--output_dir') + 1])\n"
                "output.mkdir(parents=True, exist_ok=True)\n"
                "print('STDOUT', sys.argv)\n"
                "print('STDERR', sys.argv, file=sys.stderr)\n",
                encoding="utf-8",
            )
            fake.chmod(0o755)
            bundle = root / "bundle"

            proc = self._run(
                "run",
                "--agentos-allow-execute",
                "--agentos-sweagent-bin",
                str(fake),
                "--agentos-artifact-dir",
                str(bundle),
                "--api-key",
                "sk-real-secret",
                "--github-token=ghp_real_secret",
            )

            self.assertEqual(proc.returncode, 0, proc.stderr)
            combined = "\n".join(
                path.read_text(encoding="utf-8", errors="ignore")
                for path in bundle.rglob("*")
                if path.is_file()
            )
            self.assertNotIn("sk-real-secret", combined)
            self.assertNotIn("ghp_real_secret", combined)
            self.assertIn("<redacted>", combined)


if __name__ == "__main__":
    unittest.main()
