from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PLUGIN = REPO / "plugins" / "anthropic-agent-skills"
ENV = {"PYTHONPATH": str(PLUGIN)}


def run_agent_skills(*args: str) -> dict:
    proc = subprocess.run(
        [sys.executable, "-m", "agent_skills", *args],
        cwd=REPO,
        env=ENV,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    return json.loads(proc.stdout)


class AgentSkillsPluginTests(unittest.TestCase):
    def test_manifest_validates_against_contract(self):
        proc = subprocess.run(
            [sys.executable, "scripts/validate_contract.py"],
            cwd=REPO,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("plugin manifest", proc.stdout)

    def test_inspect_inventory_preserves_progressive_disclosure_boundary(self):
        data = run_agent_skills("inspect", "tests/fixtures/anthropic-agent-skill-basic")
        self.assertEqual(data["name"], "basic-skill")
        self.assertEqual(len(data["resources"]["scripts"]), 1)
        self.assertTrue(data["progressive_disclosure"]["resource_inventory_only"])
        self.assertFalse(data["progressive_disclosure"]["scripts_references_assets_loaded"])

    def test_builtin_catalog_covers_all_issue_33_skills(self):
        data = run_agent_skills("catalog", "--builtin")
        names = {skill["source_skill"] for skill in data["skills"]}
        expected = {
            "algorithmic-art", "brand-guidelines", "canvas-design", "claude-api",
            "doc-coauthoring", "docx", "frontend-design", "internal-comms",
            "mcp-builder", "pdf", "pptx", "skill-creator", "slack-gif-creator",
            "theme-factory", "web-artifacts-builder", "webapp-testing", "xlsx",
        }
        self.assertEqual(names, expected)
        for restricted in ["docx", "pdf", "pptx", "xlsx"]:
            entry = next(skill for skill in data["skills"] if skill["source_skill"] == restricted)
            self.assertEqual(entry["assimilation_mode"], "adapter-only")
            self.assertEqual(entry["license_classification"], "source-available")

    def test_resolver_returns_firewalled_candidate(self):
        data = run_agent_skills("resolve", "Use the PDF skill to extract this form")
        self.assertEqual(data["candidates"][0]["skill"], "pdf")
        self.assertTrue(data["candidates"][0]["firewall_required"])

    def test_invoke_dry_run_handoff_shape(self):
        data = run_agent_skills("invoke", "webapp-testing", "test", "--dry-run")
        self.assertEqual(data["schema"], "agent-skills.handoff.v1")
        self.assertEqual(data["source_skill"], "webapp-testing")
        self.assertEqual(data["result"]["status"], "success")
        self.assertIn("plugin.invoked", data["audit_events"])
        self.assertEqual(data["provenance"]["executed_scripts"], [])

    def test_restricted_skill_blocks_runtime_without_approval(self):
        data = run_agent_skills("invoke", "pdf", "extract")
        self.assertEqual(data["result"]["status"], "blocked")
        self.assertIn("Restricted/source-available", data["result"]["summary"])


class ReferenceConversionTests(unittest.TestCase):
    def test_mcp_builder_reference_conversion_writes_scaffold(self):
        out = REPO / ".pytest_cache" / "anthropic-agent-skills-mcp-scaffold"
        if out.exists():
            import shutil

            shutil.rmtree(out)
        data = run_agent_skills("invoke", "mcp-builder", "scaffold", "--artifact-dir", str(out))
        self.assertEqual(data["result"]["status"], "success")
        self.assertTrue((out / "package.json").is_file())
        self.assertTrue((out / "src" / "index.ts").is_file())
        self.assertEqual(data["provenance"]["executed_scripts"], [])

    def test_reference_conversion_refuses_to_overwrite_existing_artifacts(self):
        out = REPO / ".pytest_cache" / "anthropic-agent-skills-overwrite-refusal"
        if out.exists():
            import shutil

            shutil.rmtree(out)
        run_agent_skills("invoke", "mcp-builder", "scaffold", "--artifact-dir", str(out))
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "agent_skills",
                "invoke",
                "mcp-builder",
                "scaffold",
                "--artifact-dir",
                str(out),
            ],
            cwd=REPO,
            env=ENV,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("refusing to overwrite existing artifact", proc.stderr)


if __name__ == "__main__":
    unittest.main()
