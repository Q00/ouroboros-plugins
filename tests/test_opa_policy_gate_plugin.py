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
PLUGIN_PATH = REPO / "plugins" / "opa-policy-gate"


FAKE_OPA = r'''
#!/usr/bin/env python3
from __future__ import annotations
import json
import pathlib
import sys

mode = pathlib.Path(__file__).with_name("mode.txt").read_text().strip()
args = sys.argv[1:]
if args[:3] == ["version", "--format", "json"] or args[:2] == ["version", "--format"]:
    print(json.dumps({"Version": "1.16.2", "Commit": "fake"}))
    raise SystemExit(0)
if args[:1] == ["version"]:
    print("Version: 1.16.2")
    raise SystemExit(0)
if not args:
    raise SystemExit(2)
command = args[0]
if command == "eval":
    if mode == "env_probe":
        print(json.dumps({"env_secret_visible": "SECRET_REVIEW_TOKEN" in __import__("os").environ, "result": [{"expressions": [{"value": True}]}]}))
        raise SystemExit(0)
    if mode == "sleep":
        __import__("time").sleep(5)
        print(json.dumps({"result": [{"expressions": [{"value": True}]}]}))
        raise SystemExit(0)
    if mode == "eval_true":
        print(json.dumps({"result": [{"expressions": [{"value": True}]}]}))
        raise SystemExit(0)
    if mode == "eval_false":
        print(json.dumps({"result": [{"expressions": [{"value": False}]}]}))
        raise SystemExit(0)
    if mode == "eval_undefined":
        print(json.dumps({"result": []}))
        raise SystemExit(0)
    print(json.dumps({"errors": [{"message": "eval failed"}]}))
    print("eval stderr", file=sys.stderr)
    raise SystemExit(1)
if command == "test":
    if mode == "test_fail":
        print(json.dumps({"failures": [{"name": "test_allow", "location": {"file": "policy.rego"}}]}))
        print("test stderr", file=sys.stderr)
        raise SystemExit(1)
    print(json.dumps({"files": {"policy.rego": []}}))
    raise SystemExit(0)
if command == "check":
    if mode == "check_fail":
        print(json.dumps({"errors": [{"message": "rego_parse_error"}]}))
        print("check stderr", file=sys.stderr)
        raise SystemExit(1)
    print(json.dumps({"errors": []}))
    raise SystemExit(0)
if command == "build":
    out = pathlib.Path(args[args.index("-o") + 1])
    out.write_bytes(b"fake bundle")
    print(json.dumps({"bundle": str(out)}))
    raise SystemExit(0)
raise SystemExit(2)
'''


class OpaPolicyGatePluginTests(unittest.TestCase):
    def setUp(self) -> None:
        self.td = tempfile.TemporaryDirectory()
        self.root = Path(self.td.name)
        self.fake_dir = self.root / "bin"
        self.fake_dir.mkdir()
        self.fake_opa = self.fake_dir / "opa"
        self.fake_opa.write_text(FAKE_OPA.lstrip().replace("#!/usr/bin/env python3", f"#!{sys.executable}", 1), encoding="utf-8")
        self.fake_opa.chmod(0o755)
        (self.fake_dir / "mode.txt").write_text("eval_true", encoding="utf-8")
        (self.root / "policy.rego").write_text(
            textwrap.dedent(
                """
                package example
                import rego.v1
                default allow := false
                allow if input.user == "alice"
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )
        (self.root / "data.json").write_text('{"roles":{"alice":"admin"}}\n', encoding="utf-8")
        (self.root / "input.json").write_text('{"user":"alice"}\n', encoding="utf-8")

    def tearDown(self) -> None:
        self.td.cleanup()

    def write_config(self, name: str, payload: dict) -> str:
        path = self.root / name
        path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
        return name

    def set_mode(self, mode: str) -> None:
        (self.fake_dir / "mode.txt").write_text(mode, encoding="utf-8")

    def run_plugin(self, command: str, config: str = "gate.json", *, extra_args: list[str] | None = None, env_extra: dict[str, str] | None = None, path: str | None = None) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-m", "opa_policy_gate", command, "--config", config, *(extra_args or [])],
            cwd=self.root,
            env={**os.environ, "PYTHONPATH": str(PLUGIN_PATH), "PATH": path or str(self.fake_dir), **(env_extra or {})},
            text=True,
            capture_output=True,
            check=False,
        )

    def parse(self, proc: subprocess.CompletedProcess) -> dict:
        try:
            return json.loads(proc.stdout)
        except json.JSONDecodeError as exc:  # pragma: no cover - assertion helper
            self.fail(f"stdout was not JSON: {proc.stdout!r}; stderr={proc.stderr!r}; {exc}")

    def eval_config(self, **extra) -> str:
        payload = {
            "query": "data.example.allow",
            "data": ["policy.rego", "data.json"],
            "input": "input.json",
            "fail": True,
            "timeout": "10s",
        }
        payload.update(extra)
        return self.write_config("gate.json", payload)

    def test_eval_success_writes_raw_normalized_provenance_and_handoff(self):
        self.set_mode("eval_true")
        proc = self.run_plugin("eval", self.eval_config())
        payload = self.parse(proc)

        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(payload["status"], "completed")
        self.assertIs(payload["decision"], True)
        self.assertEqual(payload["tool_version"], "1.16.2")
        artifacts = payload["artifacts"]
        for key in ["raw-stdout.json", "raw-stderr.txt", "normalized-result.json", "provenance.json", "handoff.md", "repro.sh"]:
            self.assertIn(key, artifacts)
            self.assertTrue((self.root / artifacts[key]).is_file(), key)
        raw = json.loads((self.root / artifacts["raw-stdout.json"]).read_text(encoding="utf-8"))
        self.assertEqual(raw["result"][0]["expressions"][0]["value"], True)
        provenance = json.loads((self.root / artifacts["provenance.json"]).read_text(encoding="utf-8"))
        self.assertEqual(provenance["opa"]["version"], "1.16.2")
        self.assertEqual(provenance["path_hashes"]["input"]["path"], "input.json")
        self.assertIn("opa eval", payload["repro_command"])

    def test_eval_false_preserves_decision_as_completed_review(self):
        self.set_mode("eval_false")
        proc = self.run_plugin("eval", self.eval_config())
        payload = self.parse(proc)

        self.assertEqual(proc.returncode, 0)
        self.assertEqual(payload["status"], "completed")
        self.assertIs(payload["decision"], False)
        self.assertEqual(payload["next_action"], "review_decision")

    def test_eval_undefined_maps_to_failed_decision_evidence(self):
        self.set_mode("eval_undefined")
        proc = self.run_plugin("eval", self.eval_config(fail=False))
        payload = self.parse(proc)

        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["reason"], "undefined_decision")

    def test_test_failures_are_validation_failures_with_raw_stderr(self):
        self.set_mode("test_fail")
        cfg = self.write_config("gate.json", {"data": ["policy.rego"], "timeout": "10s"})
        proc = self.run_plugin("test", cfg)
        payload = self.parse(proc)

        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["next_action"], "fix_policy_tests")
        stderr_path = self.root / payload["artifacts"]["raw-stderr.txt"]
        self.assertIn("test stderr", stderr_path.read_text(encoding="utf-8"))

    def test_check_parse_errors_are_policy_source_failures(self):
        self.set_mode("check_fail")
        cfg = self.write_config("gate.json", {"data": ["policy.rego"]})
        proc = self.run_plugin("check", cfg)
        payload = self.parse(proc)

        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["next_action"], "fix_policy_source")

    def test_path_traversal_is_blocked_without_running_opa(self):
        cfg = self.write_config("gate.json", {"query": "data.example.allow", "data": ["../policy.rego"]})
        proc = self.run_plugin("eval", cfg)
        payload = self.parse(proc)

        self.assertEqual(proc.returncode, 0)
        self.assertEqual(payload["status"], "blocked")
        self.assertEqual(payload["reason"], "invalid_request")
        self.assertIn("must stay inside", payload["message"])

    def test_missing_opa_binary_blocks(self):
        proc = self.run_plugin("eval", self.eval_config(), path=str(self.root / "empty-bin"))
        payload = self.parse(proc)

        self.assertEqual(proc.returncode, 0)
        self.assertEqual(payload["status"], "blocked")
        self.assertEqual(payload["reason"], "opa_binary_missing")

    def test_artifact_root_must_stay_under_omx_opa_boundary(self):
        proc = self.run_plugin("eval", self.eval_config(), extra_args=["--artifact-root", "plugins/opa-policy-gate"])
        payload = self.parse(proc)

        self.assertEqual(proc.returncode, 0)
        self.assertEqual(payload["status"], "blocked")
        self.assertEqual(payload["reason"], "invalid_request")
        self.assertIn(".omx/artifacts/opa", payload["message"])

    def test_opa_subprocess_does_not_inherit_secret_environment(self):
        self.set_mode("env_probe")
        proc = self.run_plugin("eval", self.eval_config(), env_extra={"SECRET_REVIEW_TOKEN": "should-not-leak"})
        payload = self.parse(proc)

        self.assertEqual(proc.returncode, 0, proc.stderr)
        raw = json.loads((self.root / payload["artifacts"]["raw-stdout.json"]).read_text(encoding="utf-8"))
        self.assertIs(raw["env_secret_visible"], False)

    def test_opa_subprocess_timeout_blocks(self):
        self.set_mode("sleep")
        proc = self.run_plugin("eval", self.eval_config(timeout="1s"))
        payload = self.parse(proc)

        self.assertEqual(proc.returncode, 0)
        self.assertEqual(payload["status"], "blocked")
        self.assertIn("timed out", payload["message"])

    def test_unsupported_command_blocks_as_json(self):
        proc = self.run_plugin("run-server", self.eval_config())
        payload = self.parse(proc)

        self.assertEqual(proc.returncode, 0)
        self.assertEqual(payload["status"], "blocked")
        self.assertEqual(payload["reason"], "invalid_request")
        self.assertIn("unsupported command", payload["message"])

    def test_build_handoff_writes_bundle_only_under_artifact_root(self):
        self.set_mode("build_ok")
        cfg = self.write_config("gate.json", {"data": ["policy.rego", "data.json"], "output_name": "bundle.tar.gz"})
        proc = self.run_plugin("build-handoff", cfg)
        payload = self.parse(proc)

        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(payload["status"], "completed")
        bundle_path = self.root / payload["artifacts"]["bundle.tar.gz"]
        self.assertTrue(bundle_path.is_file())
        self.assertTrue(bundle_path.resolve().is_relative_to((self.root / ".omx" / "artifacts" / "opa").resolve()))


class OpaPolicyGateManifestTests(unittest.TestCase):
    def test_manifest_validates_against_current_schema(self):
        from jsonschema import Draft202012Validator

        schema = json.loads((REPO / "schemas" / "0.1" / "plugin.schema.json").read_text(encoding="utf-8"))
        manifest = json.loads((PLUGIN_PATH / "ouroboros.plugin.json").read_text(encoding="utf-8"))
        errors = list(Draft202012Validator(schema).iter_errors(manifest))
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
