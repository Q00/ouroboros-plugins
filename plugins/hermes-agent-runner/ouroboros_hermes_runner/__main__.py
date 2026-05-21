"""Command entrypoint for the bounded Hermes Agent runtime bridge."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PLUGIN_NAME = "hermes-agent-runner"
PLUGIN_VERSION = "0.1.0"
DEFAULT_STATE_ROOT = Path(".ouroboros") / "hermes-agent-runner" / "sessions"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


def write_json_atomic(path: Path, payload: Any) -> None:
    write_text_atomic(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def session_root(raw: str | None) -> Path:
    return Path(raw).expanduser().resolve() if raw else (Path.cwd() / DEFAULT_STATE_ROOT).resolve()


def session_dir(root: Path, session_id: str) -> Path:
    return root / session_id


def session_state_path(root: Path, session_id: str) -> Path:
    return session_dir(root, session_id) / "session.json"


def new_session_id() -> str:
    return f"hermes-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"


def load_session(root: Path, session_id: str) -> dict[str, Any]:
    path = session_state_path(root, session_id)
    if not path.is_file():
        raise FileNotFoundError(f"session not found: {session_id}")
    return read_json(path)


def base_state(session_id: str, command: str, cwd: Path, prompt: str | None) -> dict[str, Any]:
    return {
        "schema": "ouroboros.hermes_session.v1",
        "plugin": PLUGIN_NAME,
        "version": PLUGIN_VERSION,
        "session_id": session_id,
        "command": command,
        "status": "created",
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "cwd": str(cwd),
        "prompt": prompt,
        "permissions_declared": ["shell:execute", "filesystem:read", "filesystem:write"],
        "audit_events": ["plugin.invoked", "plugin.permission_used"],
        "artifacts": {},
    }


def command_run(args: argparse.Namespace) -> int:
    root = session_root(args.session_root)
    sid = args.session_id or new_session_id()
    sdir = session_dir(root, sid)
    sdir.mkdir(parents=True, exist_ok=True)
    cwd = Path(args.cwd).expanduser().resolve() if args.cwd else Path.cwd().resolve()
    state = base_state(sid, "run", cwd, args.prompt)
    stdout_path = sdir / "stdout.txt"
    stderr_path = sdir / "stderr.txt"
    handoff_path = sdir / "handoff.md"
    argv = shlex.split(args.hermes_command) + ["run", args.prompt]
    state.update({"hermes_command": argv, "timeout_seconds": args.timeout, "started_at": utc_now(), "status": "running"})
    write_json_atomic(sdir / "session.json", state)

    if args.dry_run:
        stdout = f"DRY RUN: would execute {shlex.join(argv)}\n"
        stderr = ""
        returncode = 0
        status = "dry_run_completed"
    else:
        executable = shutil.which(argv[0])
        if executable is None:
            stderr = f"Hermes executable not found: {argv[0]}\n"
            stdout = ""
            returncode = 127
            status = "failed"
        else:
            argv[0] = executable
            try:
                proc = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=args.timeout, check=False)
                stdout, stderr, returncode = proc.stdout, proc.stderr, proc.returncode
                status = "completed" if returncode == 0 else "failed"
            except subprocess.TimeoutExpired as exc:
                stdout = exc.stdout or ""
                stderr = (exc.stderr or "") + f"\nTimed out after {args.timeout} seconds.\n"
                returncode = 124
                status = "failed"
    write_text_atomic(stdout_path, stdout)
    write_text_atomic(stderr_path, stderr)
    handoff = f"# Hermes run handoff\n\n- Session: `{sid}`\n- Status: `{status}`\n- Return code: `{returncode}`\n- Prompt: {args.prompt!r}\n- Stdout: `{stdout_path}`\n- Stderr: `{stderr_path}`\n\nNo implicit trust is granted to external providers or messaging gateways.\n"
    write_text_atomic(handoff_path, handoff)
    state.update({
        "status": status,
        "returncode": returncode,
        "completed_at": utc_now(),
        "updated_at": utc_now(),
        "audit_events": state["audit_events"] + (["plugin.completed"] if returncode == 0 else ["plugin.failed"]),
        "artifacts": {"stdout": str(stdout_path), "stderr": str(stderr_path), "handoff": str(handoff_path)},
    })
    write_json_atomic(sdir / "session.json", state)
    sys.stdout.write(json.dumps(state, indent=2, sort_keys=True) + "\n")
    return 0 if returncode == 0 else 1


def command_chat(args: argparse.Namespace) -> int:
    root = session_root(args.session_root)
    sid = args.session_id or new_session_id()
    sdir = session_dir(root, sid)
    sdir.mkdir(parents=True, exist_ok=True)
    cwd = Path(args.cwd).expanduser().resolve() if args.cwd else Path.cwd().resolve()
    state = base_state(sid, "chat", cwd, None)
    argv = shlex.split(args.hermes_command)
    state.update({
        "status": "attach_ready",
        "hermes_command": argv,
        "attach_contract": "Launch the recorded Hermes command in a managed terminal only after shell/network/provider scopes are explicitly trusted.",
        "updated_at": utc_now(),
        "audit_events": state["audit_events"] + ["plugin.completed"],
    })
    write_json_atomic(sdir / "session.json", state)
    write_text_atomic(sdir / "handoff.md", f"# Hermes chat attach handoff\n\nSession `{sid}` is prepared for an auditable interactive attach. Command: `{shlex.join(argv)}`.\n")
    sys.stdout.write(json.dumps(state, indent=2, sort_keys=True) + "\n")
    return 0


def command_status(args: argparse.Namespace) -> int:
    try:
        state = load_session(session_root(args.session_root), args.session_id)
    except FileNotFoundError as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 1
    sys.stdout.write(json.dumps(state, indent=2, sort_keys=True) + "\n")
    return 0


def command_resume(args: argparse.Namespace) -> int:
    try:
        state = load_session(session_root(args.session_root), args.session_id)
    except FileNotFoundError as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 1
    payload = {"status": "resume_ready", "session": state, "resume_guidance": "Use the recorded artifacts and command metadata; do not re-run external Hermes work without renewed trust."}
    sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return 0


def command_stop(args: argparse.Namespace) -> int:
    root = session_root(args.session_root)
    try:
        state = load_session(root, args.session_id)
    except FileNotFoundError as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 1
    state.update({"status": "stopped", "updated_at": utc_now(), "stop_note": "Synchronous v0 sessions are marked stopped/cancelled in state; no background process handle is retained."})
    events = list(state.get("audit_events", []))
    if "plugin.completed" not in events:
        events.append("plugin.completed")
    state["audit_events"] = events
    write_json_atomic(session_state_path(root, args.session_id), state)
    sys.stdout.write(json.dumps(state, indent=2, sort_keys=True) + "\n")
    return 0


def command_export(args: argparse.Namespace) -> int:
    root = session_root(args.session_root)
    try:
        state = load_session(root, args.session_id)
    except FileNotFoundError as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 1
    out = Path(args.out).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    write_json_atomic(out / "session.json", state)
    lines = ["# Hermes session export", "", f"- Session: `{args.session_id}`", f"- Status: `{state.get('status')}`", f"- Source state: `{session_state_path(root, args.session_id)}`", ""]
    for label, raw_path in state.get("artifacts", {}).items():
        source = Path(raw_path)
        if source.is_file():
            target = out / source.name
            write_text_atomic(target, source.read_text(encoding="utf-8", errors="replace"))
            lines.append(f"- {label}: `{target}`")
    write_text_atomic(out / "handoff.md", "\n".join(lines) + "\n")
    sys.stdout.write(json.dumps({"status": "exported", "session_id": args.session_id, "output_dir": str(out)}, indent=2) + "\n")
    return 0


def add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--session-root")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hermes-agent-runner")
    sub = parser.add_subparsers(dest="command", required=True)
    p_run = sub.add_parser("run")
    p_run.add_argument("prompt")
    p_run.add_argument("--hermes-command", default=os.environ.get("HERMES_COMMAND", "hermes"))
    p_run.add_argument("--timeout", type=int, default=300)
    p_run.add_argument("--cwd")
    p_run.add_argument("--session-id")
    p_run.add_argument("--dry-run", action="store_true")
    add_common(p_run)
    p_chat = sub.add_parser("chat")
    p_chat.add_argument("--hermes-command", default=os.environ.get("HERMES_COMMAND", "hermes"))
    p_chat.add_argument("--cwd")
    p_chat.add_argument("--session-id")
    add_common(p_chat)
    for name in ["status", "resume", "stop"]:
        p = sub.add_parser(name)
        p.add_argument("session_id")
        add_common(p)
    p_export = sub.add_parser("export")
    p_export.add_argument("session_id")
    p_export.add_argument("--out", required=True)
    add_common(p_export)
    args = parser.parse_args(argv)
    if args.command == "run":
        return command_run(args)
    if args.command == "chat":
        return command_chat(args)
    if args.command == "status":
        return command_status(args)
    if args.command == "resume":
        return command_resume(args)
    if args.command == "stop":
        return command_stop(args)
    if args.command == "export":
        return command_export(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
