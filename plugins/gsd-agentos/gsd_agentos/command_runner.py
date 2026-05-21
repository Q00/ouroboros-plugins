"""Bounded shell-backed runner for trusted upstream GSD execution."""
from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path

MAX_CAPTURE = 12000
DEFAULT_TIMEOUT = 900


def run_upstream(
    command: dict,
    args: list[str],
    *,
    target_repo: Path,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict:
    runner = os.environ.get("GSD_AGENTOS_UPSTREAM_RUNNER", "")
    if not runner:
        return {
            "exit_code": 78,
            "mode": "blocked",
            "status": "blocked",
            "stdout_excerpt": "",
            "stderr_excerpt": (
                "--execute requires GSD_AGENTOS_UPSTREAM_RUNNER; "
                "use invoke without --execute for policy-checked explain mode"
            ),
        }
    argv = shlex.split(runner) + [command["canonical_name"], *args]
    proc = subprocess.run(
        argv,
        cwd=target_repo,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    return {
        "exit_code": proc.returncode,
        "mode": "shell",
        "argv": argv,
        "stdout_excerpt": proc.stdout[-MAX_CAPTURE:],
        "stderr_excerpt": proc.stderr[-MAX_CAPTURE:],
    }
