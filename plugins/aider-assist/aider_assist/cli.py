from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .artifacts import root as artifact_root
from .artifacts import run_id, write_handoff, write_json, write_text
from .git_state import diff, snapshot, touched_files
from .policy import PolicyError, normalize_paths
from .runner import ask_args, edit_args, run_aider, version


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aider_assist")
    parser.add_argument("--repo", default=".", help="Repository root; defaults to current directory.")
    parser.add_argument("--version", action="version", version=f"aider-assist {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    ask = sub.add_parser("ask", help="Ask Aider about selected context without edits.")
    ask.add_argument("--message", required=True)
    ask.add_argument("--file", action="append", default=[], help="Context file; treated as read-only in ask mode.")
    ask.add_argument("--read", action="append", default=[], help="Additional read-only context file.")
    ask.add_argument("--timeout", type=int, default=3600)

    edit = sub.add_parser("edit", help="Run a bounded Aider edit over explicit files.")
    edit.add_argument("--message", required=True)
    edit.add_argument("--file", action="append", default=[], help="Editable repository file; required.")
    edit.add_argument("--read", action="append", default=[], help="Additional read-only context file.")
    edit.add_argument("--timeout", type=int, default=7200)

    for name in ("fix", "architect"):
        cmd = sub.add_parser(name, help=f"{name} is declared in the manifest and implemented by later stacked PRs.")
        cmd.set_defaults(not_implemented=name)
    return parser


def ask(ns: argparse.Namespace) -> int:
    repo_root = Path(ns.repo).resolve()
    try:
        read_only = normalize_paths([*ns.file, *ns.read], repo_root)
    except PolicyError as exc:
        print(f"blocked: {exc}", file=sys.stderr)
        return 2

    rid = run_id("ask")
    out = artifact_root(repo_root, rid)
    out.mkdir(parents=True, exist_ok=True)
    argv = ask_args(ns.message, read_only)
    before = snapshot(repo_root)
    aider_version = version(repo_root)
    result = run_aider(argv, repo_root, timeout=ns.timeout)
    status = "completed" if result.returncode == 0 else "failed"

    write_json(out / "invocation.json", {
        "schema_version": "0.1",
        "plugin": {"name": "aider-assist", "version": __version__},
        "command": "ask",
        "argv": argv,
        "message": ns.message,
        "selected_context": read_only,
        "repo_state_before": before,
        "aider_version": aider_version,
        "result": {"status": status, "exit_code": result.returncode},
    })
    write_text(out / "stdout.txt", result.stdout)
    write_text(out / "stderr.txt", result.stderr)
    write_text(out / "answer.md", result.stdout)
    summary = result.stdout.strip() or result.stderr.strip() or f"Aider exited with code {result.returncode}."
    write_handoff(out / "handoff.md", command="ask", message=ns.message, selected_context=read_only, status=status, aider_version=aider_version, summary=summary)
    print(str(out))
    return result.returncode


def edit(ns: argparse.Namespace) -> int:
    repo_root = Path(ns.repo).resolve()
    try:
        editable = normalize_paths(ns.file, repo_root)
        read_only = normalize_paths(ns.read, repo_root)
    except PolicyError as exc:
        print(f"blocked: {exc}", file=sys.stderr)
        return 2
    if not editable:
        print("blocked: edit requires at least one --file editable path", file=sys.stderr)
        return 2

    rid = run_id("edit")
    out = artifact_root(repo_root, rid)
    out.mkdir(parents=True, exist_ok=True)
    argv = edit_args(ns.message, editable, read_only)
    before = snapshot(repo_root)
    aider_version = version(repo_root)
    result = run_aider(argv, repo_root, timeout=ns.timeout)
    after = snapshot(repo_root)
    patch = diff(repo_root)
    touched = touched_files(repo_root)
    status = "completed" if result.returncode == 0 else "failed"

    write_json(out / "invocation.json", {
        "schema_version": "0.1",
        "plugin": {"name": "aider-assist", "version": __version__},
        "command": "edit",
        "argv": argv,
        "message": ns.message,
        "editable_files": editable,
        "read_only_context": read_only,
        "repo_state_before": before,
        "repo_state_after": after,
        "aider_version": aider_version,
        "result": {"status": status, "exit_code": result.returncode},
    })
    write_text(out / "stdout.txt", result.stdout)
    write_text(out / "stderr.txt", result.stderr)
    write_text(out / "diff.patch", patch)
    write_text(out / "touched-files.txt", "\n".join(touched) + ("\n" if touched else ""))
    summary = result.stdout.strip() or result.stderr.strip() or f"Aider exited with code {result.returncode}."
    write_handoff(out / "handoff.md", command="edit", message=ns.message, selected_context=[*editable, *read_only], status=status, aider_version=aider_version, summary=summary)
    print(str(out))
    return result.returncode


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    ns = parser.parse_args(argv)
    if getattr(ns, "not_implemented", None):
        print(f"{ns.not_implemented} is declared for the issue #44 stack but implemented in a later PR", file=sys.stderr)
        return 2
    if ns.command == "ask":
        return ask(ns)
    if ns.command == "edit":
        return edit(ns)
    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
