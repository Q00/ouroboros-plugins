from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

REPO = Path(__file__).resolve().parents[1]
PLUGIN = REPO / "plugins" / "gsd-agentos"
AUDIT_SCHEMA = json.loads((REPO / "schemas" / "0.1" / "audit-event.schema.json").read_text())
AUDIT_VALIDATOR = Draft202012Validator(AUDIT_SCHEMA)
sys.path.insert(0, str(PLUGIN))

from gsd_agentos.command_catalog import all_commands, get_command, load_catalog  # noqa: E402
from gsd_agentos.risk_policy import check_policy  # noqa: E402
from gsd_agentos.validation import validate_catalog  # noqa: E402


def run_cli(*args: str, trust: str | None = None, runner: str | None = None, cwd: Path | None = None):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PLUGIN)
    if trust is not None:
        env["OUROBOROS_TRUST_SCOPES"] = trust
    else:
        env.pop("OUROBOROS_TRUST_SCOPES", None)
    if runner is not None:
        env["GSD_AGENTOS_UPSTREAM_RUNNER"] = runner
    return subprocess.run(
        [sys.executable, "-m", "gsd_agentos", *args],
        cwd=cwd or REPO,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


class GsdCatalogTests(unittest.TestCase):
    def test_catalog_represents_pinned_upstream_surface(self):
        catalog = load_catalog()
        commands = all_commands()
        self.assertEqual(catalog["upstream"]["commit"], "c1c8b0d10907b8e6db8fa90bc09b1608899df590")
        self.assertEqual(len(commands), 67)
        self.assertEqual(validate_catalog(catalog), [])
        self.assertEqual({c["namespace"] for c in commands}, {"gsd"})
        self.assertIn("commands/gsd/plan-phase.md", {c["upstream_file"] for c in commands})

    def test_manifest_exposes_every_catalog_command(self):
        manifest = json.loads((PLUGIN / "ouroboros.plugin.json").read_text())
        manifest_names = {c["name"] for c in manifest["commands"]}
        catalog_names = {c["canonical_name"] for c in all_commands()}
        self.assertEqual(manifest_names, catalog_names)
        self.assertEqual(manifest["name"], "gsd-agentos")

    def test_risk_examples_are_classified(self):
        self.assertEqual(get_command("help")["risk"], "read_only")
        self.assertEqual(get_command("plan-phase")["risk"], "write")
        self.assertEqual(get_command("ship")["risk"], "destructive")
        self.assertIn("shell:execute", get_command("ship")["required_permissions"])

    def test_read_only_commands_do_not_declare_mutation(self):
        mutating = [
            c["canonical_name"]
            for c in all_commands()
            if c["risk"] == "read_only" and any(c.get("mutates", {}).values())
        ]
        self.assertEqual(mutating, [])

    def test_remote_commands_require_explicit_non_shell_scope(self):
        remote = [c for c in all_commands() if c.get("mutates", {}).get("remote_systems")]
        self.assertTrue(remote, "fixture should include remote/cloud-capable commands")
        for command in remote:
            self.assertNotEqual(command["risk"], "read_only")
            self.assertTrue(
                any(scope.startswith(("network:", "github:")) for scope in command["required_permissions"]),
                command["canonical_name"],
            )


class GsdPolicyTests(unittest.TestCase):
    def test_missing_trust_scopes_block_invocation(self):
        decision = check_policy(get_command("plan-phase"), execute=False, trust=["filesystem:read"])
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.missing_scopes, ("filesystem:write",))
        self.assertIn("ouroboros plugin trust gsd-agentos", decision.message)

    def test_destructive_requires_confirmation(self):
        command = get_command("ship")
        decision = check_policy(command, execute=True, trust=command["required_permissions"])
        self.assertFalse(decision.allowed)
        self.assertTrue(decision.confirmation_required)
        self.assertTrue(check_policy(command, execute=True, confirm="ship", trust=command["required_permissions"]).allowed)


class GsdCliTests(unittest.TestCase):
    def test_list_and_explain(self):
        proc = run_cli("list", "--risk", "read_only")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("gsd help", proc.stdout)
        explain = run_cli("explain", "plan-phase", "--json")
        self.assertEqual(explain.returncode, 0, explain.stderr)
        data = json.loads(explain.stdout)
        self.assertEqual(data["canonical_name"], "plan-phase")

    def test_read_only_invocation_records_audit(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            proc = run_cli("invoke", "help", "--target-repo", str(root), trust="filesystem:read")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            result = json.loads(proc.stdout)
            self.assertEqual(result["status"], "completed")
            self.assertEqual(len(result["audit_events"]), 2)
            for event in result["audit_events"]:
                self.assertEqual(list(AUDIT_VALIDATOR.iter_errors(event)), [])
            self.assertFalse((root / ".ouroboros").exists(), "read-only invocation must not write target repo without filesystem:write")

    def test_blocked_invocation_with_write_only_trust_does_not_mutate_target(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            proc = run_cli(
                "invoke",
                "help",
                "--target-repo",
                str(root),
                trust="filesystem:write",
            )
            self.assertEqual(proc.returncode, 3)
            self.assertIn("missing trust scopes", proc.stderr)
            self.assertFalse((root / ".ouroboros").exists())

    def test_execute_without_runner_is_blocked_not_completed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            proc = run_cli(
                "invoke",
                "verify-work",
                "1",
                "--target-repo",
                str(root),
                "--execute",
                trust="filesystem:read,filesystem:write,shell:execute",
            )
            self.assertEqual(proc.returncode, 3)
            result = json.loads(proc.stdout)
            self.assertEqual(result["status"], "blocked")
            self.assertEqual(result["runner"]["mode"], "blocked")
            self.assertNotEqual(result["audit_events"][-1]["result"]["status"], "success")

    def test_write_invocation_creates_handoff_projection(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            planning = root / ".planning"
            planning.mkdir()
            (planning / "PROJECT.md").write_text("# Project\n", encoding="utf-8")
            (planning / "REQUIREMENTS.md").write_text("# Requirements\n", encoding="utf-8")
            (planning / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
            (planning / "STATE.md").write_text("# State\n", encoding="utf-8")
            proc = run_cli("invoke", "plan-phase", "1", "--target-repo", str(root), "--handoff", trust="filesystem:read,filesystem:write")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            result = json.loads(proc.stdout)
            handoff = Path(result["handoff"])
            self.assertTrue(handoff.is_file())
            audit_path = root / ".ouroboros" / "handoffs" / "gsd" / "audit.jsonl"
            events = [json.loads(line) for line in audit_path.read_text().splitlines()]
            self.assertTrue(events)
            for event in events:
                self.assertEqual(list(AUDIT_VALIDATOR.iter_errors(event)), [])
            payload = json.loads(handoff.read_text())
            projections = {p["projection"] for p in payload["handoff"]["planning_projection"] if p["exists"]}
            self.assertIn("project_context", projections)
            self.assertIn("staged_plan_phase_graph", projections)

    def test_shell_execute_uses_bounded_runner(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            runner = f"{sys.executable} -c 'import sys; print(\"ran\", sys.argv[1:])'"
            proc = run_cli("invoke", "verify-work", "1", "--target-repo", str(root), "--execute", trust="filesystem:read,filesystem:write,shell:execute", runner=runner)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            result = json.loads(proc.stdout)
            self.assertEqual(result["runner"]["mode"], "shell")
            self.assertIn("verify-work", result["runner"]["stdout_excerpt"])

    def test_destructive_cli_blocks_without_confirmation(self):
        with tempfile.TemporaryDirectory() as td:
            proc = run_cli("invoke", "ship", "1", "--target-repo", td, "--execute", trust="filesystem:read,filesystem:write,shell:execute,network:read")
            self.assertEqual(proc.returncode, 3)
            self.assertIn("requires explicit confirmation", proc.stderr)


if __name__ == "__main__":
    unittest.main()
