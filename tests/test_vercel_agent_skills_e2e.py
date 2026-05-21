from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_PATH = ROOT / "plugins" / "vercel-agent-skills"


def test_entrypoint_smoke_and_audit_event_schema(tmp_path):
    out = tmp_path / "run"
    proc = subprocess.run(
        [sys.executable, "-m", "vercel_agent_skills", "composition-patterns", str(ROOT / "tests/fixtures/vercel-sample"), "--format", "json", "--out", str(out)],
        cwd=PLUGIN_PATH,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    handoff = json.loads((out / "handoff.json").read_text())
    assert handoff["command"]["namespace"] == "vercel"
    audit = json.loads((out / "audit-event.json").read_text())
    schema = json.loads((ROOT / "schemas/0.1/audit-event.schema.json").read_text())
    jsonschema.validate(audit, schema)
    assert audit["result"]["status"] == "success"


def test_all_upstream_skills_have_explicit_manifest_command():
    manifest = json.loads((PLUGIN_PATH / "ouroboros.plugin.json").read_text())
    names = {c["name"] for c in manifest["commands"] if c["namespace"] == "vercel"}
    assert {
        "optimize",
        "react-best-practices",
        "web-design-guidelines",
        "react-native-skills",
        "react-view-transitions",
        "composition-patterns",
        "deploy-preview",
        "deploy-production",
        "cli-with-tokens",
    } <= names
