from __future__ import annotations

from pathlib import Path


def package_root() -> Path:
    return Path(__file__).resolve().parents[1]


def skill_path(upstream_skill: str) -> Path:
    return package_root() / "assets" / "skills" / upstream_skill / "SKILL.md"


def agent_dir() -> Path:
    return package_root() / "assets" / "agents"


def list_agents() -> list[str]:
    root = agent_dir()
    if not root.is_dir():
        return []
    return sorted(path.name for path in root.glob("*.agent.md"))


def read_skill_excerpt(upstream_skill: str, max_lines: int = 80) -> str:
    path = skill_path(upstream_skill)
    if not path.is_file():
        return ""
    lines = path.read_text(encoding="utf-8").splitlines()
    return "\n".join(lines[:max_lines])
