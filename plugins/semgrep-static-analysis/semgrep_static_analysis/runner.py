from __future__ import annotations

import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from .paths import BoundaryError, BoundedPath, is_remote_config, resolve_bounded_path


@dataclass(frozen=True)
class ScanRequest:
    root: Path
    target_path: str
    config: str
    output_dir: Path
    semgrep_bin: str = "semgrep"
    allow_remote_config: bool = False
    sarif: bool = False
    error_on_findings: bool = False
    includes: tuple[str, ...] = ()
    excludes: tuple[str, ...] = ()


@dataclass(frozen=True)
class PreparedScan:
    argv: list[str]
    target: BoundedPath
    config_display: str
    config_kind: str
    sarif_path: Path | None
    permissions_used: list[str]


@dataclass(frozen=True)
class SemgrepRun:
    argv: list[str]
    version: str
    returncode: int
    stdout: str
    stderr: str
    duration_seconds: float


class SemgrepBlocked(RuntimeError):
    """Raised when the plugin refuses to invoke Semgrep."""


class SemgrepExecutionError(RuntimeError):
    """Raised for Semgrep process execution errors."""


def _require_semgrep(binary: str) -> str:
    resolved = shutil.which(binary)
    if not resolved:
        raise SemgrepBlocked(
            f"Semgrep executable not found: {binary}. Install Semgrep and retry; this plugin does not vendor Semgrep."
        )
    return resolved


def _validate_glob(value: str, label: str) -> str:
    if not value or "\x00" in value:
        raise BoundaryError(f"{label} must be a non-empty glob")
    if value.startswith("/") or ".." in Path(value).parts:
        raise BoundaryError(f"{label} must be a bounded relative glob")
    return value


def prepare_scan(request: ScanRequest) -> PreparedScan:
    semgrep = _require_semgrep(request.semgrep_bin)
    root = request.root.resolve(strict=False)
    target = resolve_bounded_path(request.target_path, root=root, label="target_path", must_exist=True)

    permissions = ["filesystem:read", "shell:execute"]
    config_kind = "local"
    config_display = request.config
    config_arg = request.config
    if is_remote_config(request.config):
        if not request.allow_remote_config:
            raise SemgrepBlocked(
                "Remote or registry Semgrep configs require explicit network permission; pass --allow-remote-config after granting network:read."
            )
        config_kind = "remote"
        permissions.append("network:read")
    else:
        config_path = resolve_bounded_path(request.config, root=root, label="config", must_exist=True)
        config_display = config_path.relative
        config_arg = config_path.relative

    output_bound = resolve_bounded_path(
        str(request.output_dir), root=root, label="output_dir", must_exist=False
    )
    output_dir = output_bound.absolute
    output_dir.mkdir(parents=True, exist_ok=True)
    sarif_path = output_dir / "semgrep.raw.sarif" if request.sarif else None

    argv = [
        semgrep,
        "scan",
        "--json",
        "--metrics=off",
        "--disable-version-check",
        "--config",
        config_arg,
    ]
    if request.error_on_findings:
        argv.append("--error")
    for include in request.includes:
        argv.extend(["--include", _validate_glob(include, "include")])
    for exclude in request.excludes:
        argv.extend(["--exclude", _validate_glob(exclude, "exclude")])
    if sarif_path is not None:
        argv.extend(["--sarif-output", str(sarif_path)])
    argv.append(target.relative)
    return PreparedScan(
        argv=argv,
        target=target,
        config_display=config_display,
        config_kind=config_kind,
        sarif_path=sarif_path,
        permissions_used=permissions,
    )


def run_semgrep(prepared: PreparedScan, *, cwd: Path, timeout_seconds: int = 1800) -> SemgrepRun:
    start = time.monotonic()
    version = "unknown"
    try:
        version_proc = subprocess.run(
            [prepared.argv[0], "--version"],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        version = (version_proc.stdout or version_proc.stderr).strip().splitlines()[0] if (version_proc.stdout or version_proc.stderr).strip() else "unknown"
        proc = subprocess.run(
            prepared.argv,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise SemgrepExecutionError(f"Semgrep timed out after {timeout_seconds}s") from exc
    except OSError as exc:
        raise SemgrepExecutionError(f"Failed to execute Semgrep: {exc}") from exc
    return SemgrepRun(
        argv=prepared.argv,
        version=version,
        returncode=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
        duration_seconds=round(time.monotonic() - start, 3),
    )
