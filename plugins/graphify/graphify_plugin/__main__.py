"""Thin Ouroboros adapter for the upstream Graphify CLI."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
from typing import Any

PLUGIN_NAME = "graphify"
PLUGIN_VERSION = "0.1.0"
PYPI_PACKAGE = "graphifyy"


@dataclass(frozen=True)
class Resolution:
    argv: list[str] | None
    label: str | None
    version: str | None
    blocked_reason: str | None = None


def graphify_version() -> str | None:
    for package in (PYPI_PACKAGE, "graphify"):
        try:
            return metadata.version(package)
        except metadata.PackageNotFoundError:
            continue
    return None


def resolve_graphify() -> Resolution:
    executable = shutil.which("graphify")
    version = graphify_version()
    if executable:
        return Resolution([executable], executable, version)
    try:
        probe = subprocess.run(
            [sys.executable, "-m", "graphify", "--help"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=10,
        )
    except subprocess.TimeoutExpired:
        probe = None
    if probe is not None and probe.returncode == 0:
        return Resolution([sys.executable, "-m", "graphify"], "python -m graphify", version)
    return Resolution(
        None,
        None,
        version,
        "Graphify is not installed. Install it explicitly with `uv tool install graphifyy` or `pipx install graphifyy`; this adapter never auto-installs dependencies.",
    )


def command_family(args: list[str]) -> str:
    if args and args[0] in {"query", "path", "explain"}:
        return args[0]
    return "build"


def classify(args: list[str]) -> dict[str, Any]:
    family = command_family(args)
    if family in {"query", "path", "explain"}:
        return {"family": family, "risk": "read_only", "permissions_used": ["filesystem:read", "shell:execute"]}
    return {"family": family, "risk": "write", "permissions_used": ["filesystem:read", "filesystem:write", "shell:execute"]}


def payload(*, status: str, args: list[str], resolution: Resolution, classification: dict[str, Any], returncode: int | None, stdout: str = "", stderr: str = "", message: str = "") -> dict[str, Any]:
    return {
        "schema_version": "0.1",
        "kind": "graphify_result",
        "status": status,
        "message": message,
        "plugin": {"name": PLUGIN_NAME, "version": PLUGIN_VERSION},
        "upstream": {"package": PYPI_PACKAGE, "command": resolution.label, "version": resolution.version},
        "command": {"family": classification["family"], "argv": args, "returncode": returncode},
        "risk": classification["risk"],
        "permissions_used": classification["permissions_used"],
        "stdout_excerpt": stdout[-4000:] if stdout else "",
        "stderr_excerpt": stderr[-4000:] if stderr else "",
    }


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="graphify_plugin")
    parser.add_argument("args", nargs=argparse.REMAINDER, help="Arguments forwarded to upstream graphify.")
    ns = parser.parse_args(argv)
    upstream_args = ns.args or ["."]
    classification = classify(upstream_args)
    resolution = resolve_graphify()
    if resolution.argv is None:
        print(json.dumps(payload(status="blocked", args=upstream_args, resolution=resolution, classification=classification, returncode=None, message=resolution.blocked_reason or "Graphify executable could not be resolved."), indent=2, sort_keys=True))
        return 1
    proc = subprocess.run([*resolution.argv, *upstream_args], cwd=Path.cwd(), capture_output=True, text=True, check=False, env=os.environ.copy())
    status = "completed" if proc.returncode == 0 else "failed"
    print(json.dumps(payload(status=status, args=upstream_args, resolution=resolution, classification=classification, returncode=proc.returncode, stdout=proc.stdout, stderr=proc.stderr, message="Graphify command completed." if proc.returncode == 0 else "Graphify command failed."), indent=2, sort_keys=True))
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(run())
