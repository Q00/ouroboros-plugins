from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugins" / "vercel-agent-skills"))
from vercel_agent_skills.cli import main  # noqa: E402
from vercel_agent_skills.runtime import redact  # noqa: E402


def test_redact_masks_tokens():
    text = "VERCEL_TOKEN=vercel_1234567890abcdefghijklmnopqrstuvwxyz authorization Bearer abcdef1234567890abcdef1234567890"
    redacted = redact(text)
    assert "vercel_123456" not in redacted
    assert "abcdef1234567890abcdef" not in redacted
    assert "[REDACTED]" in redacted


def test_cli_token_preflight_never_persists_raw_token(tmp_path, monkeypatch):
    monkeypatch.chdir(ROOT)
    monkeypatch.setenv("VERCEL_TOKEN", "vercel_1234567890abcdefghijklmnopqrstuvwxyz")
    out = tmp_path / "run"
    rc = main(["cli-with-tokens", "preflight", "tests/fixtures/vercel-sample", "--out", str(out)])
    assert rc == 0
    combined = (out / "token-preflight.json").read_text() + (out / "handoff.json").read_text()
    assert "vercel_123456" not in combined
    assert "[REDACTED]" in combined


def test_preview_deploy_requires_confirmation_and_token(tmp_path, monkeypatch):
    monkeypatch.chdir(ROOT)
    monkeypatch.delenv("VERCEL_TOKEN", raising=False)
    out = tmp_path / "run"
    rc = main(["deploy-preview", "tests/fixtures/vercel-sample", "--out", str(out)])
    assert rc == 2
    handoff = json.loads((out / "handoff.json").read_text())
    assert handoff["status"] == "blocked"
    assert any("--confirm" in item for item in handoff["limitations"])


def test_production_deploy_is_disabled(tmp_path, monkeypatch):
    monkeypatch.chdir(ROOT)
    out = tmp_path / "run"
    rc = main(["deploy-production", "tests/fixtures/vercel-sample", "--out", str(out)])
    assert rc == 2
    handoff = json.loads((out / "handoff.json").read_text())
    assert handoff["status"] == "blocked"
    assert handoff["risk"] == "destructive"
