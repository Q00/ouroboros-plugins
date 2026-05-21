from __future__ import annotations

import subprocess
from pathlib import Path


def git(args: list[str], repo_root: Path) -> str:
    completed = subprocess.run(["git", *args], cwd=repo_root, text=True, capture_output=True, check=False)
    return completed.stdout.strip()


def snapshot(repo_root: Path) -> dict[str, str]:
    return {
        "head": git(["rev-parse", "HEAD"], repo_root),
        "branch": git(["rev-parse", "--abbrev-ref", "HEAD"], repo_root),
        "status_short": git(["status", "--short"], repo_root),
    }
