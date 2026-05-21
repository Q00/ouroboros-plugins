from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PLUGIN_PATH = REPO / "plugins" / "langfuse-observability"
sys.path.insert(0, str(PLUGIN_PATH))

from langfuse_observability.artifacts import coerce_score_value, parse_trace_reference, redact


FIXTURE = PLUGIN_PATH / "tests" / "fixtures" / "langfuse-trace.json"


class LangfuseObservabilityPluginTests(unittest.TestCase):
    def _run(self, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
        clean_env = {k: v for k, v in os.environ.items() if not k.startswith("LANGFUSE_")}
        clean_env.update(env or {})
        return subprocess.run(
            [sys.executable, "-m", "langfuse_observability", *args],
            cwd=REPO,
            env={**clean_env, "PYTHONPATH": str(PLUGIN_PATH)},
            capture_output=True,
            text=True,
            check=False,
        )

    def test_manifest_risks_match_issue_27_contract_boundary(self):
        manifest = json.loads((PLUGIN_PATH / "ouroboros.plugin.json").read_text(encoding="utf-8"))
        commands = {command["name"]: command for command in manifest["commands"]}
        self.assertEqual(commands["inspect"]["risk"], "write")
        self.assertFalse(commands["inspect"].get("requires_confirmation", False))
        self.assertEqual(commands["score"]["risk"], "write")
        self.assertTrue(commands["score"]["requires_confirmation"])
        permissions = {(permission["scope"], permission["risk"]) for permission in manifest["permissions"]}
        self.assertIn(("network:read", "read_only"), permissions)
        self.assertIn(("filesystem:write", "write"), permissions)
        self.assertIn(("network:write", "write"), permissions)

    def test_parse_trace_url_and_raw_id(self):
        self.assertEqual(
            parse_trace_reference("https://cloud.langfuse.com/project/p/traces/trace_123")[:2],
            ("trace_123", "https://cloud.langfuse.com"),
        )
        self.assertEqual(parse_trace_reference("trace_abc", "https://cloud.langfuse.com")[0], "trace_abc")

    def test_redaction_removes_secrets_and_truncates_large_payloads(self):
        payload = redact({"secret_key": "sk-lf-secret", "text": "x" * 600})
        self.assertEqual(payload["secret_key"], "[REDACTED]")
        self.assertIn("[TRUNCATED]", payload["text"])

    def test_redaction_removes_langfuse_key_values_inside_strings(self):
        payload = redact(
            {
                "comment": "do not leak sk-lf-super-secret or pk-lf-public",
                "error": "Authorization failed for Bearer abc.def.ghi",
            }
        )
        serialized = json.dumps(payload)
        self.assertNotIn("sk-lf-super-secret", serialized)
        self.assertNotIn("pk-lf-public", serialized)
        self.assertNotIn("Bearer abc.def.ghi", serialized)
        self.assertIn("[REDACTED]", serialized)

    def test_inspect_fixture_writes_json_and_markdown_artifacts(self):
        with tempfile.TemporaryDirectory() as td:
            proc = self._run("inspect", "trace_123", "--offline-fixture", str(FIXTURE), "--output-dir", td)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            result = json.loads(proc.stdout)
            json_path = Path(result["json_path"])
            md_path = Path(result["markdown_path"])
            self.assertTrue(json_path.is_file())
            self.assertTrue(md_path.is_file())
            handoff = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(handoff["trace"]["id"], "trace_123")
            self.assertEqual(handoff["summary"]["observations_count"], 1)
            self.assertEqual(handoff["summary"]["scores_count"], 1)
            serialized = json.dumps(handoff)
            self.assertNotIn("sk-lf-secret", serialized)
            self.assertNotIn("super-secret", serialized)
            self.assertIn("Langfuse Trace Handoff", md_path.read_text(encoding="utf-8"))

    def test_inspect_without_fixture_requires_credentials(self):
        proc = self._run("inspect", "trace_123")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("missing Langfuse configuration", proc.stderr)

    def test_score_dry_run_writes_payload_without_credentials(self):
        with tempfile.TemporaryDirectory() as td:
            inspect_proc = self._run("inspect", "trace_123", "--offline-fixture", str(FIXTURE), "--output-dir", td)
            artifact = json.loads(inspect_proc.stdout)["json_path"]
            proc = self._run("score", artifact, "--name", "correctness", "--value", "0.8", "--dry-run", "--output-dir", td)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            result = json.loads(proc.stdout)
            self.assertEqual(result["status"], "dry_run")
            self.assertEqual(result["payload"]["traceId"], "trace_123")
            self.assertEqual(result["payload"]["value"], 0.8)
            self.assertTrue(Path(result["result_path"]).is_file())

    def test_score_real_write_requires_confirmation_before_credentials(self):
        with tempfile.TemporaryDirectory() as td:
            inspect_proc = self._run("inspect", "trace_123", "--offline-fixture", str(FIXTURE), "--output-dir", td)
            artifact = json.loads(inspect_proc.stdout)["json_path"]
            proc = self._run("score", artifact, "--name", "correctness", "--value", "0.8")
            self.assertEqual(proc.returncode, 2)
            self.assertIn("requires --confirm", proc.stderr)

    def test_score_confirm_requires_credentials_without_leaking_secret(self):
        with tempfile.TemporaryDirectory() as td:
            artifact = Path(td) / "artifact.json"
            artifact.write_text(json.dumps({"trace": {"id": "trace_123"}}), encoding="utf-8")
            proc = self._run(
                "score", str(artifact), "--name", "correctness", "--value", "0.8", "--confirm", env={"LANGFUSE_SECRET_KEY": "sk-lf-super-secret"}
            )
            self.assertEqual(proc.returncode, 2)
            self.assertIn("LANGFUSE_BASE_URL", proc.stderr)
            self.assertNotIn("sk-lf-super-secret", proc.stderr)

    def test_cli_errors_are_redacted_before_stderr(self):
        proc = self._run(
            "inspect",
            "trace_123",
            "--offline-fixture",
            "sk-lf-secret-missing.json",
        )
        self.assertEqual(proc.returncode, 2)
        self.assertNotIn("sk-lf-secret", proc.stderr)
        self.assertIn("[REDACTED]", proc.stderr)

    def test_score_value_coercion(self):
        self.assertEqual(coerce_score_value("1"), 1)
        self.assertEqual(coerce_score_value("0.5"), 0.5)
        self.assertEqual(coerce_score_value("true"), 1)
        self.assertEqual(coerce_score_value("false"), 0)
        self.assertEqual(coerce_score_value("low"), "low")


if __name__ == "__main__":
    unittest.main()
