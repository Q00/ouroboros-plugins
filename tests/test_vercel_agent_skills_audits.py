from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugins" / "vercel-agent-skills"))

from vercel_agent_skills.cli import main  # noqa: E402
from vercel_agent_skills.runtime import bounded_paths  # noqa: E402


def test_react_best_practices_writes_handoff(tmp_path, monkeypatch):
    monkeypatch.chdir(ROOT)
    out = tmp_path / "run"
    rc = main(["react-best-practices", "tests/fixtures/vercel-sample", "--format", "json", "--out", str(out)])
    assert rc == 0
    handoff = json.loads((out / "handoff.json").read_text())
    assert handoff["plugin"] == "vercel-agent-skills"
    assert handoff["upstream"]["skill"] == "react-best-practices"
    assert handoff["status"] == "success"
    assert handoff["artifacts"]
    assert any(f["path"].endswith("page.tsx") for f in handoff["findings"])


def test_bounded_paths_rejects_escape(monkeypatch):
    monkeypatch.chdir(ROOT)
    try:
        bounded_paths("../outside.ts")
    except (FileNotFoundError, ValueError):
        pass
    else:  # pragma: no cover
        raise AssertionError("path escape should not be accepted")


def test_view_transition_implement_is_blocked(tmp_path, monkeypatch):
    monkeypatch.chdir(ROOT)
    out = tmp_path / "run"
    rc = main(["react-view-transitions", "tests/fixtures/vercel-sample", "--mode", "implement", "--out", str(out)])
    assert rc == 2
    handoff = json.loads((out / "handoff.json").read_text())
    assert handoff["status"] == "blocked"


def test_web_design_guidelines_blocks_when_fetch_fails(tmp_path, monkeypatch):
    monkeypatch.chdir(ROOT)

    def fail_urlopen(*args, **kwargs):
        raise OSError("network disabled")

    import vercel_agent_skills.audits as audits

    monkeypatch.setattr(audits.urllib.request, "urlopen", fail_urlopen)
    out = tmp_path / "run"
    rc = main(["web-design-guidelines", "tests/fixtures/vercel-sample", "--format", "json", "--out", str(out)])
    assert rc == 2
    handoff = json.loads((out / "handoff.json").read_text())
    assert handoff["status"] == "blocked"
    assert any("Guideline fetch blocked" in item for item in handoff["limitations"])
