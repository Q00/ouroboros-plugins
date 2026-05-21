from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class RunResult:
    argv: list[str]
    returncode: int
    stdout: str
    stderr: str


def aider_bin() -> str:
    configured = os.environ.get("AIDER_ASSIST_AIDER_BIN")
    if configured:
        return configured
    found = shutil.which("aider")
    if found:
        return found
    return "aider"


def version(repo_root: Path) -> str:
    try:
        completed = subprocess.run([aider_bin(), "--version"], cwd=repo_root, text=True, capture_output=True, check=False, timeout=20)
    except OSError:
        return "unavailable"
    return (completed.stdout or completed.stderr).strip() or "unknown"


def run_aider(argv: list[str], repo_root: Path, timeout: int = 3600) -> RunResult:
    try:
        completed = subprocess.run(argv, cwd=repo_root, text=True, capture_output=True, check=False, timeout=timeout)
    except FileNotFoundError as exc:
        return RunResult(argv=argv, returncode=127, stdout="", stderr=f"Aider executable not found: {exc.filename}\n")
    except OSError as exc:
        return RunResult(argv=argv, returncode=126, stdout="", stderr=f"Aider execution failed: {exc}\n")
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        return RunResult(argv=argv, returncode=124, stdout=stdout, stderr=f"{stderr}Aider timed out after {timeout} seconds.\n")
    return RunResult(argv=argv, returncode=completed.returncode, stdout=completed.stdout, stderr=completed.stderr)


def ask_args(message: str, read_only_paths: list[str]) -> list[str]:
    args = [aider_bin(), "--chat-mode", "ask", "--message", message]
    for path in read_only_paths:
        args.extend(["--read", path])
    return args
