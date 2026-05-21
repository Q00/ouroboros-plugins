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


def audit_event(event_type: str, command_name: str, argv: list[str], status: str, message: str, capabilities: list[str], permissions: list[str], provenance: dict[str, str]) -> dict[str, Any]:
    return {"schema_version": "0.1", "event_type": event_type, "occurred_at": utc_now(), "plugin": {"name": PLUGIN_NAME, "version": PLUGIN_VERSION, "source_type": "local_path"}, "command": {"namespace": "openhands", "name": command_name, "argv": redact_argv(argv)}, "trust_state": "trusted" if permissions else "blocked", "capabilities_used": capabilities, "permissions_used": permissions, "provenance": provenance, "result": {"status": status, "message": message}}


def build_openhands_command(args: argparse.Namespace, openhands_bin: str) -> list[str]:
    cmd = [openhands_bin, "--headless", "--json"]
    cmd.extend(["--task", args.task] if args.task is not None else ["--file", str(args.task_file_path)])
    if args.resume:
        cmd.extend(["--resume", args.resume])
    if args.last:
        cmd.append("--last")
    if args.override_with_envs:
        cmd.append("--override-with-envs")
    return cmd


def split_jsonl(stdout: str) -> tuple[str, str, int]:
    json_lines: list[str] = []
    log_lines: list[str] = []
    for line in stdout.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            json.loads(stripped)
        except json.JSONDecodeError:
            log_lines.append(line)
        else:
            json_lines.append(stripped)
    return "\n".join(json_lines) + ("\n" if json_lines else ""), "\n".join(log_lines) + ("\n" if log_lines else ""), len(json_lines)


def run_openhands(args: argparse.Namespace) -> CommandResult:
    if not args.trusted_shell_execute:
        return CommandResult("blocked", 1, "refusing to run without --trusted-shell-execute for shell:execute")
    if args.task is None and args.task_file is None:
        return CommandResult("blocked", 2, "one of --task or --task-file is required")
    if args.task is not None and args.task_file is not None:
        return CommandResult("blocked", 2, "--task and --task-file are mutually exclusive")
    workspace = resolve_existing_dir(args.workspace, "--workspace")
    run_id = args.run_id or f"oh-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    run_dir = resolve_inside(workspace, str(DEFAULT_STATE_ROOT / run_id), "run directory")
    events_path = resolve_inside(workspace, args.out, "--out")
    if events_path.suffix not in {".jsonl", ".json"}:
        raise ValueError("--out should be a JSONL path inside the workspace")
    run_dir.mkdir(parents=True, exist_ok=True)
    metadata_path = resolve_inside(workspace, args.metadata_out, "--metadata-out") if args.metadata_out else events_path.parent / "metadata.json"
    stderr_path = events_path.parent / "stderr.log"
    stdout_log_path = events_path.parent / "stdout.log"
    audit_path = resolve_inside(workspace, args.audit_out, "--audit-out") if args.audit_out else events_path.parent / "audit.jsonl"
    args.task_file_path = resolve_inside(workspace, args.task_file, "--task-file", must_exist=True) if args.task_file is not None else None
    openhands_bin = resolve_openhands_binary(args.openhands_bin)
    if not openhands_bin:
        return CommandResult("blocked", 1, f"OpenHands binary is not executable or was not found: {args.openhands_bin}")
    cmd = build_openhands_command(args, openhands_bin)
    env = safe_base_env(args.config_mode, run_dir, args.sandbox, args.pass_llm_env)
    metadata: dict[str, Any] = {"schema_version": "0.1", "plugin": {"name": PLUGIN_NAME, "version": PLUGIN_VERSION}, "run_id": run_id, "status": "running", "created_at": utc_now(), "workspace": str(workspace), "task": {"kind": "inline" if args.task is not None else "file", "value": args.task if args.task is not None else display_path(args.task_file_path, workspace)}, "openhands": {"binary": args.openhands_bin, "resolved_path": openhands_bin, "command": redact_argv(cmd)}, "config_mode": args.config_mode, "sandbox": args.sandbox, "environment": redacted_env(env), "artifacts": {"events": display_path(events_path, workspace), "metadata": display_path(metadata_path, workspace), "stderr": display_path(stderr_path, workspace), "audit": display_path(audit_path, workspace)}, "permissions": ["shell:execute", "filesystem:read", "filesystem:write"], "capabilities": ["ledger:write", "provenance:write", "state:write", "progress:write"]}
    capabilities = ["ledger:write", "provenance:write", "state:write", "progress:write"]
    permissions = ["shell:execute", "filesystem:read", "filesystem:write"]
    provenance = {
        "run_id": run_id,
        "workspace": str(workspace),
        "config_mode": args.config_mode,
    }
    invoked = audit_event(
        "plugin.invoked",
        "run",
        sys.argv[1:],
        "running",
        "OpenHands headless JSONL invocation accepted by plugin boundary.",
        capabilities,
        permissions,
        provenance,
    )
    permission_used = audit_event(
        "plugin.permission_used",
        "run",
        sys.argv[1:],
        "running",
        "Granted shell and filesystem permissions are being used for this bounded run.",
        capabilities,
        permissions,
        provenance,
    )
    write_text_atomic(
        audit_path,
        json.dumps(invoked, sort_keys=True)
        + "\n"
        + json.dumps(permission_used, sort_keys=True)
        + "\n",
    )
    write_json_atomic(metadata_path, metadata)
    proc = subprocess.run(cmd, cwd=workspace, env=env, capture_output=True, text=True, check=False)
    jsonl, stdout_log, event_count = split_jsonl(proc.stdout)
    write_text_atomic(events_path, jsonl)
    write_text_atomic(stdout_log_path, stdout_log)
    write_text_atomic(stderr_path, proc.stderr)
    status = "completed" if proc.returncode == 0 else "failed"
    metadata.update({"status": status, "completed_at": utc_now(), "exit_code": proc.returncode, "event_count": event_count, "artifacts": {**metadata["artifacts"], "stdout_log": display_path(stdout_log_path, workspace)}})
    write_json_atomic(metadata_path, metadata)
    done = audit_event(
        "plugin.completed" if proc.returncode == 0 else "plugin.failed",
        "run",
        sys.argv[1:],
        status,
        f"OpenHands exited with code {proc.returncode}; captured {event_count} JSONL event(s).",
        capabilities,
        permissions,
        {"run_id": run_id, "events": display_path(events_path, workspace)},
    )
    with audit_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(done, sort_keys=True) + "\n")
    return CommandResult(status, proc.returncode, done["result"]["message"], run_dir, events_path, metadata_path, stderr_path, audit_path)



def command_inspect(args: argparse.Namespace) -> int:
    print_json(inspect_payload(args)); return 0


def command_run(args: argparse.Namespace) -> int:
    try:
        result = run_openhands(args)
    except ValueError as exc:
        return die(str(exc), 2)
    print_json({"status": result.status, "exit_code": result.exit_code, "message": result.message, "events_path": str(result.events_path) if result.events_path else None, "metadata_path": str(result.metadata_path) if result.metadata_path else None, "stderr_path": str(result.stderr_path) if result.stderr_path else None, "audit_path": str(result.audit_path) if result.audit_path else None})
    return result.exit_code


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="openhands-agentos", description="Run OpenHands as an audited Ouroboros AgentOS plugin.")
    parser.add_argument("--openhands-bin", default="openhands", help="OpenHands CLI binary to inspect or invoke.")
    sub = parser.add_subparsers(dest="command", required=True)
    inspect = sub.add_parser("inspect", help="Inspect OpenHands availability without running an agent."); inspect.add_argument("--config-mode", choices=["isolated", "native"], default="isolated"); inspect.set_defaults(func=command_inspect)
    run = sub.add_parser("run", help="Run OpenHands headless JSONL inside a bounded workspace.")
    for name in ("task", "task-file", "workspace", "out", "resume", "run-id", "metadata-out", "audit-out"):
        run.add_argument(f"--{name}", required=name in {"workspace", "out"})
    run.add_argument("--trusted-shell-execute", action="store_true"); run.add_argument("--config-mode", choices=["isolated", "native"], default="isolated"); run.add_argument("--sandbox", choices=["docker", "process", "remote"], default="docker"); run.add_argument("--pass-llm-env", action="store_true"); run.add_argument("--override-with-envs", action="store_true"); run.add_argument("--last", action="store_true"); run.set_defaults(func=command_run)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)

if __name__ == "__main__":
    raise SystemExit(main())
