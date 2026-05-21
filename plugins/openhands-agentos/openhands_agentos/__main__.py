"""Command entrypoint for the OpenHands AgentOS Ouroboros plugin."""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

PLUGIN_NAME = "openhands-agentos"
PLUGIN_VERSION = "0.1.0"
DEFAULT_STATE_ROOT = Path(".omx") / "artifacts" / "openhands"
DEFAULT_HANDOFF_ROOT = Path(".omx") / "handoffs" / "openhands"
SECRET_KEY_RE = re.compile(r"(api[_-]?key|token|secret|password|authorization|bearer)", re.I)
SAFE_ENV_ALLOWLIST = {"PATH", "LANG", "LC_ALL", "LC_CTYPE", "TERM", "TMPDIR", "PYTHONPATH", "VIRTUAL_ENV"}
OPENHANDS_ENV_ALLOWLIST = {"OPENHANDS_VERSION"}
LLM_ENV_NAMES = {"LLM_API_KEY", "LLM_MODEL", "LLM_BASE_URL"}


@dataclass(frozen=True)
class CommandResult:
    status: str
    exit_code: int
    message: str
    run_dir: Path | None = None
    events_path: Path | None = None
    metadata_path: Path | None = None
    stderr_path: Path | None = None
    audit_path: Path | None = None


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def print_json(payload: Any) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def die(message: str, code: int = 2) -> int:
    print(message, file=sys.stderr)
    return code


def resolve_existing_dir(raw_path: str, label: str) -> Path:
    if not raw_path or raw_path.strip() in {"", ".", "..", "~", "/"}:
        raise ValueError(f"{label} must be an explicit bounded directory, not {raw_path!r}")
    path = Path(raw_path).expanduser().resolve()
    if not path.is_dir():
        raise ValueError(f"{label} must exist and be a directory: {raw_path}")
    if str(path) == "/":
        raise ValueError(f"{label} cannot be the filesystem root")
    return path


def resolve_inside(root: Path, raw_path: str, label: str, *, must_exist: bool = False) -> Path:
    candidate = Path(raw_path).expanduser()
    resolved = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"{label} must stay inside the bounded workspace") from exc
    if must_exist and not resolved.exists():
        raise ValueError(f"{label} does not exist: {raw_path}")
    return resolved


def display_path(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


def write_json_atomic(path: Path, payload: Any) -> None:
    write_text_atomic(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def redact_value(key: str, value: str) -> str:
    return "<redacted>" if SECRET_KEY_RE.search(key) or SECRET_KEY_RE.search(value) else value


def redact_argv(argv: Iterable[str]) -> list[str]:
    out: list[str] = []
    previous_sensitive = False
    for part in argv:
        if previous_sensitive:
            out.append("<redacted>")
            previous_sensitive = False
            continue
        if SECRET_KEY_RE.search(part):
            if "=" in part:
                key, _sep, _value = part.partition("=")
                out.append(f"{key}=<redacted>")
            else:
                out.append(part)
                previous_sensitive = True
        else:
            out.append(part)
    return out


def safe_base_env(config_mode: str, run_dir: Path, sandbox: str, pass_llm_env: bool) -> dict[str, str]:
    env: dict[str, str] = {}
    for key in sorted(SAFE_ENV_ALLOWLIST | OPENHANDS_ENV_ALLOWLIST):
        if key in os.environ:
            env[key] = os.environ[key]
    if pass_llm_env:
        for key in sorted(LLM_ENV_NAMES):
            if key in os.environ:
                env[key] = os.environ[key]
        env["OPENHANDS_AGENTOS_LLM_ENV"] = "passed-through"
    env.setdefault("PATH", os.environ.get("PATH", ""))
    if config_mode == "isolated":
        env["HOME"] = str(run_dir / "isolated-home")
        env["XDG_CONFIG_HOME"] = str(run_dir / "xdg-config")
        env["XDG_CACHE_HOME"] = str(run_dir / "xdg-cache")
        env["OPENHANDS_AGENTOS_CONFIG_MODE"] = "isolated"
    else:
        if "HOME" in os.environ:
            env["HOME"] = os.environ["HOME"]
        env["OPENHANDS_AGENTOS_CONFIG_MODE"] = "native"
    env["RUNTIME"] = sandbox
    return env


def redacted_env(env: dict[str, str]) -> dict[str, str]:
    return {key: redact_value(key, value) for key, value in sorted(env.items())}


def resolve_openhands_binary(openhands_bin: str) -> str | None:
    if os.path.basename(openhands_bin) == openhands_bin:
        return shutil.which(openhands_bin)
    path = Path(openhands_bin).expanduser().resolve()
    if path.is_file() and os.access(path, os.X_OK):
        return str(path)
    return None


def detect_cli(openhands_bin: str) -> dict[str, Any]:
    path = resolve_openhands_binary(openhands_bin)
    info: dict[str, Any] = {"binary": openhands_bin, "path": path, "installed": bool(path), "version": None, "version_status": "not_run", "help_supports": {"headless": False, "json": False, "task": False, "file": False, "resume": False}}
    if not path:
        return info
    try:
        proc = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=10, check=False)
        info["version_status"] = "ok" if proc.returncode == 0 else "error"
        info["version"] = (proc.stdout or proc.stderr).strip().splitlines()[0] if (proc.stdout or proc.stderr).strip() else None
    except Exception as exc:
        info["version_status"] = "error"
        info["version_error"] = str(exc)
    try:
        proc = subprocess.run([path, "--help"], capture_output=True, text=True, timeout=10, check=False)
        text = f"{proc.stdout}\n{proc.stderr}"
        info["help_supports"] = {"headless": "--headless" in text, "json": "--json" in text, "task": "--task" in text or "-t," in text or "-t " in text, "file": "--file" in text or "-f," in text or "-f " in text, "resume": "--resume" in text}
    except Exception as exc:
        info["help_error"] = str(exc)
    return info


def inspect_payload(args: argparse.Namespace) -> dict[str, Any]:
    config_home = Path.home() / ".openhands"
    config_files = ["agent_settings.json", "cli_config.json", "mcp.json"]
    cli = detect_cli(args.openhands_bin)
    return {"plugin": {"name": PLUGIN_NAME, "version": PLUGIN_VERSION}, "generated_at": utc_now(), "status": "installed" if cli["installed"] else "missing_openhands_cli", "openhands": cli, "config": {"mode": args.config_mode, "isolated_default": True, "native_config": {"home": str(config_home), "files_present": [name for name in config_files if (config_home / name).is_file()], "conversations_dir_present": (config_home / "conversations").is_dir(), "note": "Only file presence is reported; config contents and credentials are not read."}}, "sandbox": {"recommended_default": "docker", "supported_by_openhands_docs": ["docker", "process", "remote"], "detected_runtime_env": os.environ.get("RUNTIME"), "warnings": ["Headless OpenHands runs with auto-approval; invoke through Ouroboros trust and audit gates.", "process/local sandbox has no container isolation and should require explicit opt-in."]}, "json_headless_supported": bool(cli["help_supports"].get("headless") and cli["help_supports"].get("json")), "risk": "read_only", "mutated_external_systems": False}



def command_inspect(args: argparse.Namespace) -> int:
    print_json(inspect_payload(args))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="openhands-agentos",
        description="Inspect OpenHands as an audited Ouroboros AgentOS plugin.",
    )
    parser.add_argument(
        "--openhands-bin",
        default="openhands",
        help="OpenHands CLI binary to inspect.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    inspect = sub.add_parser(
        "inspect",
        help="Inspect OpenHands availability without running an agent.",
    )
    inspect.add_argument(
        "--config-mode",
        choices=["isolated", "native"],
        default="isolated",
    )
    inspect.set_defaults(func=command_inspect)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
