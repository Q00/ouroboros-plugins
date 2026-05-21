from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugins" / "vercel-agent-skills"))
from vercel_agent_skills.cli import main  # noqa: E402


def test_optimize_blocks_without_auth_or_project(tmp_path, monkeypatch):
    monkeypatch.chdir(ROOT)
    monkeypatch.delenv("VERCEL_TOKEN", raising=False)
    out = tmp_path / "run"
    rc = main(["optimize", "tests/fixtures/vercel-sample", "--out", str(out)])
    assert rc == 2
    handoff = json.loads((out / "handoff.json").read_text())
    assert handoff["status"] == "blocked"
    assert "vercel:metrics:read" in handoff["permissions_used"]
    assert (out / "signals.json").exists()
    assert (out / "gate.json").exists()


def test_optimize_limited_writes_report(tmp_path, monkeypatch):
    monkeypatch.chdir(ROOT)
    monkeypatch.delenv("VERCEL_TOKEN", raising=False)
    out = tmp_path / "run"
    rc = main(["optimize", "tests/fixtures/vercel-sample", "--limited", "--out", str(out)])
    assert rc == 0
    signals = json.loads((out / "signals.json").read_text())
    assert signals["framework"]["name"] == "nextjs"
    handoff = json.loads((out / "handoff.json").read_text())
    assert handoff["status"] == "success"
    assert handoff["limitations"]
