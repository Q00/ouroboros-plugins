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
PLUGIN_PATH = REPO / "plugins" / "semgrep-static-analysis"
FIXTURES = PLUGIN_PATH / "tests" / "fixtures"

sys.path.insert(0, str(PLUGIN_PATH))

from semgrep_static_analysis.normalize import SemgrepOutputError, load_semgrep_json, normalize_semgrep_output
from semgrep_static_analysis.runner import ScanRequest, SemgrepBlocked, prepare_scan


class NormalizeTests(unittest.TestCase):
    def test_empty_findings_normalize(self):
        payload = load_semgrep_json((FIXTURES / "semgrep-output-empty.json").read_text())
        normalized = normalize_semgrep_output(payload, tool_version="1.99.0")
        self.assertEqual(normalized["summary"]["finding_count"], 0)
        self.assertEqual(normalized["findings"], [])

    def test_findings_preserve_agentos_fields(self):
        payload = load_semgrep_json((FIXTURES / "semgrep-output-findings.json").read_text())
        normalized = normalize_semgrep_output(payload, tool_version="1.99.0")
        self.assertEqual(normalized["summary"]["finding_count"], 1)
        finding = normalized["findings"][0]
        self.assertEqual(finding["schema_version"], "0.1")
        self.assertEqual(finding["tool"], "semgrep")
        self.assertEqual(finding["rule_id"], "python.lang.security.audit.dangerous-subprocess-use")
        self.assertEqual(finding["severity"], "ERROR")
        self.assertEqual(finding["path"], "src/example.py")
        self.assertEqual(finding["path_trust"], "semgrep-reported")
        self.assertTrue(finding["fix_available"])
        self.assertEqual(finding["raw_result_ref"], "semgrep.raw.json#/results/0")
        self.assertIn("fingerprint", finding)

    def test_malformed_json_is_explicit_failure(self):
        with self.assertRaises(SemgrepOutputError):
            load_semgrep_json("not-json")


class RunnerBoundaryTests(unittest.TestCase):
    def _fake_semgrep(self, root: Path) -> Path:
        fake = root / "semgrep"
        fake.write_text("#!/bin/sh\necho '1.99.0'\n", encoding="utf-8")
        fake.chmod(0o755)
        return fake

    def test_prepare_scan_builds_safe_local_first_argv(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "src").mkdir()
            (root / "rules").mkdir()
            (root / "rules" / "ci.yml").write_text("rules: []\n", encoding="utf-8")
            fake = self._fake_semgrep(root)
            req = ScanRequest(root=root, target_path="src", config="rules/ci.yml", output_dir=root / ".omx" / "artifacts", semgrep_bin=str(fake))

            prepared = prepare_scan(req)

        self.assertEqual(prepared.config_kind, "local")
        self.assertIn("--metrics=off", prepared.argv)
        self.assertIn("--disable-version-check", prepared.argv)
        self.assertEqual(prepared.argv[-1], "src")
        self.assertEqual(prepared.permissions_used, ["filesystem:read", "shell:execute"])
        self.assertNotIn("network:read", prepared.permissions_used)

    def test_remote_config_requires_explicit_opt_in(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "src").mkdir()
            fake = self._fake_semgrep(root)
            req = ScanRequest(root=root, target_path="src", config="p/ci", output_dir=root / ".omx" / "artifacts", semgrep_bin=str(fake))
            with self.assertRaises(SemgrepBlocked):
                prepare_scan(req)

    def test_remote_config_adds_network_permission_when_allowed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "src").mkdir()
            fake = self._fake_semgrep(root)
            req = ScanRequest(root=root, target_path="src", config="p/ci", output_dir=root / ".omx" / "artifacts", semgrep_bin=str(fake), allow_remote_config=True)
            prepared = prepare_scan(req)
        self.assertEqual(prepared.config_kind, "remote")
        self.assertIn("network:read", prepared.permissions_used)


    def test_output_dir_must_stay_inside_repository(self):
        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as outside:
            root = Path(td)
            (root / "src").mkdir()
            (root / "rules.yml").write_text("rules: []\n", encoding="utf-8")
            fake = self._fake_semgrep(root)
            req = ScanRequest(root=root, target_path="src", config="rules.yml", output_dir=Path(outside), semgrep_bin=str(fake))
            with self.assertRaises(ValueError):
                prepare_scan(req)

    def test_target_must_stay_inside_repository(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fake = self._fake_semgrep(root)
            req = ScanRequest(root=root, target_path="../outside", config="rules.yml", output_dir=root / ".omx" / "artifacts", semgrep_bin=str(fake))
            with self.assertRaises(ValueError):
                prepare_scan(req)


class CliIntegrationTests(unittest.TestCase):
    def _write_fake_semgrep(self, root: Path, payload: str, *, code: int = 0) -> Path:
        fake = root / "semgrep"
        fake.write_text(
            textwrap.dedent(
                f"""
                #!/usr/bin/env python3
                import sys
                from pathlib import Path
                if sys.argv[1:] == ['--version']:
                    print('1.99.0')
                    raise SystemExit(0)
                if '--sarif-output' in sys.argv:
                    Path(sys.argv[sys.argv.index('--sarif-output') + 1]).write_text('{{"version":"2.1.0","runs":[]}}')
                print({payload!r})
                raise SystemExit({code})
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )
        fake.chmod(0o755)
        return fake

    def _run_cli(self, *args: str, cwd: Path) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-m", "semgrep_static_analysis", *args],
            cwd=REPO,
            env={**os.environ, "PYTHONPATH": str(PLUGIN_PATH)},
            capture_output=True,
            text=True,
            check=False,
        )

    def test_scan_writes_handoff_bundle(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "src").mkdir()
            (root / "rules.yml").write_text("rules: []\n", encoding="utf-8")
            fake = self._write_fake_semgrep(root, (FIXTURES / "semgrep-output-findings.json").read_text())
            proc = self._run_cli(
                "scan",
                "src",
                "--config",
                "rules.yml",
                "--repository-root",
                str(root),
                "--output-dir",
                str(root / ".omx" / "artifacts" / "semgrep"),
                "--semgrep-bin",
                str(fake),
                "--sarif",
                cwd=root,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            result = json.loads(proc.stdout)
            self.assertEqual(result["status"], "success")
            handoff = json.loads(Path(result["handoff_path"]).read_text(encoding="utf-8"))
            self.assertTrue(Path(result["artifact_dir"], "semgrep.raw.json").is_file())
            self.assertTrue(Path(result["artifact_dir"], "semgrep.raw.sarif").is_file())
            self.assertTrue(Path(result["artifact_dir"], "semgrep.provenance.json").is_file())
            self.assertTrue(handoff["downstream"]["raw_semgrep_output_preserved"])
            findings = json.loads(Path(result["artifact_dir"], "semgrep.findings.json").read_text(encoding="utf-8"))
            self.assertEqual(findings["summary"]["finding_count"], 1)
            self.assertEqual(findings["findings"][0]["scan_root"], "src")
            provenance = json.loads(Path(result["artifact_dir"], "semgrep.provenance.json").read_text(encoding="utf-8"))
            self.assertIn("semgrep.handoff.json", provenance["artifacts"])
            self.assertIn("semgrep.audit.json", provenance["artifacts"])
            self.assertNotIn("semgrep.provenance.json", provenance["artifacts"])
            audit = json.loads(Path(result["artifact_dir"], "semgrep.audit.json").read_text(encoding="utf-8"))
            self.assertTrue(all(event["provenance"].get("audit_payload_mode") == "plugin-prepared" for event in audit["events"]))


    def test_error_mode_preserves_semgrep_findings_exit_code(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "src").mkdir()
            (root / "rules.yml").write_text("rules: []\n", encoding="utf-8")
            fake = self._write_fake_semgrep(root, (FIXTURES / "semgrep-output-findings.json").read_text(), code=1)
            proc = self._run_cli(
                "scan",
                "src",
                "--config",
                "rules.yml",
                "--repository-root",
                str(root),
                "--output-dir",
                str(root / ".omx" / "artifacts" / "semgrep"),
                "--semgrep-bin",
                str(fake),
                "--error",
                cwd=root,
            )
            self.assertEqual(proc.returncode, 1, proc.stderr)
            result = json.loads(proc.stdout)
            self.assertEqual(result["status"], "success")
            self.assertEqual(result["semgrep_exit_code"], 1)


    def test_invalid_output_dir_blocks_without_writing_outside_repo(self):
        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as outside:
            root = Path(td)
            (root / "src").mkdir()
            (root / "rules.yml").write_text("rules: []\n", encoding="utf-8")
            outside_path = Path(outside) / "semgrep-artifacts"
            proc = self._run_cli(
                "scan",
                "src",
                "--config",
                "rules.yml",
                "--repository-root",
                str(root),
                "--output-dir",
                str(outside_path),
                "--semgrep-bin",
                str(root / "missing-semgrep"),
                cwd=root,
            )
            self.assertEqual(proc.returncode, 3)
            result = json.loads(proc.stdout)
            self.assertEqual(result["status"], "blocked")
            self.assertFalse(outside_path.exists())
            self.assertTrue(Path(result["artifact_dir"]).is_relative_to(root.resolve()))

    def test_cli_blocks_remote_config_without_opt_in(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "src").mkdir()
            fake = self._write_fake_semgrep(root, (FIXTURES / "semgrep-output-empty.json").read_text())
            proc = self._run_cli(
                "scan",
                "src",
                "--config",
                "p/ci",
                "--repository-root",
                str(root),
                "--semgrep-bin",
                str(fake),
                cwd=root,
            )
            self.assertEqual(proc.returncode, 3)
            self.assertEqual(json.loads(proc.stdout)["status"], "blocked")


if __name__ == "__main__":
    unittest.main()
