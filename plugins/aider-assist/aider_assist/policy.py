from __future__ import annotations

from pathlib import Path


class PolicyError(ValueError):
    """Raised when a requested Aider operation violates the plugin boundary."""


def repo_relative(path: str, repo_root: Path) -> str:
    candidate = (repo_root / path).resolve() if not Path(path).is_absolute() else Path(path).resolve()
    root = repo_root.resolve()
    try:
        rel = candidate.relative_to(root)
    except ValueError as exc:
        raise PolicyError(f"path escapes repository: {path}") from exc
    if any(part == ".." for part in rel.parts):
        raise PolicyError(f"path escapes repository: {path}")
    return rel.as_posix()


def normalize_paths(paths: list[str] | None, repo_root: Path) -> list[str]:
    if not paths:
        return []
    seen: list[str] = []
    for item in paths:
        rel = repo_relative(item, repo_root)
        if rel not in seen:
            seen.append(rel)
    return seen
