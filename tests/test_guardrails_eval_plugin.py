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
PLUGIN_PATH = REPO / "plugins" / "guardrails-eval"


class GuardrailsEvalPluginTests(unittest.TestCase):
    def _write_fake_guardrails(self, parent: Path, *, missing: bool = False) -> None:
        package = parent / "guardrails"
        package.mkdir(parents=True)
        if missing:
            (package / "__init__.py").write_text("raise ImportError('forced missing')\n", encoding="utf-8")
            return
        (package / "__init__.py").write_text(
            textwrap.dedent(
                """
                class Outcome:
                    def __init__(self, text):
                        self.raw_llm_output = text
                        self.validated_output = {"echo": text}
                        self.validation_passed = "bad" not in text
                        self.validation_summaries = [{"validator": "fake"}]
                        self.reask = None
                        self.error = None if self.validation_passed else "contains bad"

                class Guard:
                    @classmethod
                    def from_dict(cls, obj):
                        return cls()

                    @classmethod
                    def for_rail(cls, path):
                        return cls()

                    def parse(self, llm_output, metadata=None, num_reasks=0):
                        if "raise" in llm_output:
                            raise RuntimeError("validator exploded")
                        return Outcome(llm_output)
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )

    def _run(self, *args: str, fake_guardrails: bool = True, missing_guardrails: bool = False) -> subprocess.CompletedProcess:
        with tempfile.TemporaryDirectory(prefix="fake-guardrails-") as fake_dir:
            fake_path = Path(fake_dir)
            if fake_guardrails or missing_guardrails:
                self._write_fake_guardrails(fake_path, missing=missing_guardrails)
            pythonpath_parts = []
            if fake_guardrails or missing_guardrails:
                pythonpath_parts.append(str(fake_path))
            pythonpath_parts.append(str(PLUGIN_PATH))
            return subprocess.run(
                [sys.executable, "-m", "guardrails_eval", *args],
                cwd=REPO,
                env={
                    **os.environ,
                    "PYTHONPATH": os.pathsep.join(pythonpath_parts),
                    "PYTHONNOUSERSITE": "1",
                },
                capture_output=True,
                text=True,
                check=False,
            )

    def _repo_tmp(self):
        return tempfile.TemporaryDirectory(dir=REPO, prefix=".guardrails-eval-test-")

    def _rel(self, path: Path) -> str:
        return str(path.relative_to(REPO))

    def test_validate_output_writes_success_report_and_handoff(self):
        with self._repo_tmp() as td:
            root = Path(td)
            spec = root / "spec.json"
            output = root / "output.txt"
            metadata = root / "metadata.json"
            report = root / "report.json"
            handoff = root / "handoff.json"
            spec.write_text('{"name":"fake"}\n', encoding="utf-8")
            output.write_text("safe text", encoding="utf-8")
            metadata.write_text('{"tenant":"example"}\n', encoding="utf-8")

            proc = self._run(
                "validate-output",
                "--spec",
                self._rel(spec),
                "--output",
                self._rel(output),
                "--metadata",
                self._rel(metadata),
                "--report",
                self._rel(report),
                "--handoff",
                self._rel(handoff),
            )

            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = json.loads(report.read_text(encoding="utf-8"))
            handoff_payload = json.loads(handoff.read_text(encoding="utf-8"))
            self.assertTrue(payload["guardrails_outcome"]["validation_passed"])
            self.assertEqual(payload["input"]["target"]["kind"], "llm_output")
            self.assertTrue(payload["guardrails_outcome"]["raw_llm_output"]["redacted"])
            self.assertIn("filesystem:write", payload["ouroboros_result"]["permissions_used"])
            self.assertIn("handoff:attach", payload["ouroboros_result"]["capabilities_used"])
            self.assertEqual(handoff_payload["artifact_status"], "accepted")

    def test_validate_output_failure_exits_nonzero_unless_opted_out(self):
        with self._repo_tmp() as td:
            root = Path(td)
            spec = root / "spec.json"
            spec.write_text('{"name":"fake"}\n', encoding="utf-8")
            proc = self._run(
                "validate-output",
                "--spec",
                self._rel(spec),
                "--text",
                "bad text",
            )
            self.assertEqual(proc.returncode, 1)
            self.assertIn("validation_passed=False", proc.stdout)

            proc = self._run(
                "validate-output",
                "--spec",
                self._rel(spec),
                "--text",
                "bad text",
                "--no-fail-on-validation-fail",
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_validate_artifact_and_summarize_report(self):
        with self._repo_tmp() as td:
            root = Path(td)
            spec = root / "spec.rail"
            artifact = root / "artifact.md"
            report = root / "artifact-report.json"
            spec.write_text("<rail></rail>\n", encoding="utf-8")
            artifact.write_text("safe artifact", encoding="utf-8")

            proc = self._run(
                "validate-artifact",
                "--spec",
                self._rel(spec),
                "--artifact",
                self._rel(artifact),
                "--report",
                self._rel(report),
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(payload["input"]["target"]["kind"], "artifact")

            summary = self._run("summarize-report", "--report", self._rel(report))
            self.assertEqual(summary.returncode, 0, summary.stderr)
            self.assertIn("guardrails success", summary.stdout)

    def test_validator_exception_is_reported_as_validation_failure(self):
        with self._repo_tmp() as td:
            root = Path(td)
            spec = root / "spec.json"
            report = root / "exception-report.json"
            spec.write_text('{"name":"fake"}\n', encoding="utf-8")
            proc = self._run(
                "validate-output",
                "--spec",
                self._rel(spec),
                "--text",
                "raise during validation",
                "--report",
                self._rel(report),
            )
            self.assertEqual(proc.returncode, 1)
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertFalse(payload["guardrails_outcome"]["validation_passed"])
            self.assertEqual(payload["guardrails_outcome"]["error"], "validator exploded")

    def test_paths_must_stay_inside_repository(self):
        with self._repo_tmp() as td:
            root = Path(td)
            spec = root / "spec.json"
            spec.write_text('{"name":"fake"}\n', encoding="utf-8")
            proc = self._run(
                "validate-output",
                "--spec",
                self._rel(spec),
                "--output",
                "../outside.txt",
            )
            self.assertEqual(proc.returncode, 2)
            self.assertIn("must stay inside", proc.stderr)

    def test_missing_guardrails_dependency_is_clear(self):
        with self._repo_tmp() as td:
            root = Path(td)
            spec = root / "spec.json"
            spec.write_text('{"name":"fake"}\n', encoding="utf-8")
            proc = self._run(
                "validate-output",
                "--spec",
                self._rel(spec),
                "--text",
                "safe",
                fake_guardrails=False,
                missing_guardrails=True,
            )
            self.assertEqual(proc.returncode, 1)
            self.assertIn("guardrails-ai is required", proc.stderr)

    def test_unsupported_python_specs_are_not_executed(self):
        with self._repo_tmp() as td:
            root = Path(td)
            spec = root / "guard.py"
            spec.write_text("raise RuntimeError('must not execute')\n", encoding="utf-8")
            proc = self._run(
                "validate-output",
                "--spec",
                self._rel(spec),
                "--text",
                "safe",
            )
            self.assertEqual(proc.returncode, 2)
            self.assertIn("MVP supports .rail and .json", proc.stderr)


if __name__ == "__main__":
    unittest.main()
