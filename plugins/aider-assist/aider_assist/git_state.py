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


def diff(repo_root: Path) -> str:
    return git(["diff", "--binary"], repo_root)


def touched_files(repo_root: Path) -> list[str]:
    status = git(["status", "--short"], repo_root)
    files: list[str] = []
    for line in status.splitlines():
        if not line.strip():
            continue
        path = line[2:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        files.append(path)
    return files
