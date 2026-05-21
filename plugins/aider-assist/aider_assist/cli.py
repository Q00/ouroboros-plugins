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
from .verification import all_passed, failure_context, run_verifications, serialize


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
    edit.add_argument("--test-cmd")
    edit.add_argument("--lint-cmd")
    edit.add_argument("--timeout", type=int, default=7200)

    fix = sub.add_parser("fix", help="Run failing verification context through a bounded Aider repair.")
    fix.add_argument("--message", default="Repair the failing verification command without changing the requested behavior.")
    fix.add_argument("--file", action="append", default=[], help="Editable repository file; required.")
    fix.add_argument("--read", action="append", default=[], help="Additional read-only context file.")
    fix.add_argument("--test-cmd")
    fix.add_argument("--lint-cmd")
    fix.add_argument("--timeout", type=int, default=7200)

    architect = sub.add_parser("architect", help="architect is declared in the manifest and implemented by the final stacked PR.")
    architect.set_defaults(not_implemented="architect")
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


def write_mode(ns: argparse.Namespace, command_name: str) -> int:
    repo_root = Path(ns.repo).resolve()
    try:
        editable = normalize_paths(ns.file, repo_root)
        read_only = normalize_paths(ns.read, repo_root)
    except PolicyError as exc:
        print(f"blocked: {exc}", file=sys.stderr)
        return 2
    if not editable:
        print(f"blocked: {command_name} requires at least one --file editable path", file=sys.stderr)
        return 2
    if command_name == "fix" and not (ns.test_cmd or ns.lint_cmd):
        print("blocked: fix requires --test-cmd or --lint-cmd", file=sys.stderr)
        return 2

    rid = run_id(command_name)
    out = artifact_root(repo_root, rid)
    out.mkdir(parents=True, exist_ok=True)
    editable_set = set(editable)
    preexisting_outside_bounds = sorted(path for path in touched_files(repo_root) if path not in editable_set)
    if preexisting_outside_bounds:
        write_json(out / "invocation.json", {
            "schema_version": "0.1",
            "plugin": {"name": "aider-assist", "version": __version__},
            "command": command_name,
            "message": ns.message,
            "editable_files": editable,
            "read_only_context": read_only,
            "result": {"status": "blocked", "message": "repository has dirty files outside the editable allowlist", "files": preexisting_outside_bounds},
        })
        summary = f"Dirty files outside edit bounds: {', '.join(preexisting_outside_bounds)}"
        write_handoff(out / "handoff.md", command=command_name, message=ns.message, selected_context=[*editable, *read_only], status="blocked", aider_version=version(repo_root), summary=summary)
        print(str(out))
        return 2

    before = snapshot(repo_root)
    pre_verification = run_verifications(ns.test_cmd, ns.lint_cmd, repo_root, timeout=ns.timeout)
    message = ns.message
    if command_name == "fix":
        context = failure_context(pre_verification)
        if context:
            message = f"{ns.message}\n\nVerification failure context:\n{context}"
    argv = edit_args(message, editable, read_only)
    aider_version = version(repo_root)
    result = run_aider(argv, repo_root, timeout=ns.timeout)
    post_verification = run_verifications(ns.test_cmd, ns.lint_cmd, repo_root, timeout=ns.timeout)
    after = snapshot(repo_root)
    patch = diff(repo_root)
    touched = touched_files(repo_root)
    unauthorized_touched = sorted(path for path in touched if path not in editable_set)
    status = "completed" if result.returncode == 0 and all_passed(post_verification) and not unauthorized_touched else "failed"

    write_json(out / "invocation.json", {
        "schema_version": "0.1",
        "plugin": {"name": "aider-assist", "version": __version__},
        "command": command_name,
        "argv": argv,
        "message": ns.message,
        "editable_files": editable,
        "read_only_context": read_only,
        "repo_state_before": before,
        "repo_state_after": after,
        "aider_version": aider_version,
        "unauthorized_touched_files": unauthorized_touched,
        "verification_before": serialize(pre_verification),
        "verification_after": serialize(post_verification),
        "result": {"status": status, "exit_code": result.returncode},
    })
    write_json(out / "verification.json", {
        "before": serialize(pre_verification),
        "after": serialize(post_verification),
        "status": "passed" if all_passed(post_verification) else "failed",
    })
    write_text(out / "stdout.txt", result.stdout)
    write_text(out / "stderr.txt", result.stderr)
    write_text(out / "diff.patch", patch)
    write_text(out / "touched-files.txt", "\n".join(touched) + ("\n" if touched else ""))
    summary = result.stdout.strip() or result.stderr.strip() or f"Aider exited with code {result.returncode}."
    if unauthorized_touched:
        summary = f"Aider touched files outside the editable allowlist: {', '.join(unauthorized_touched)}"
    write_handoff(out / "handoff.md", command=command_name, message=ns.message, selected_context=[*editable, *read_only], status=status, aider_version=aider_version, summary=summary)
    print(str(out))
    return 0 if status == "completed" else (result.returncode or 1)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    ns = parser.parse_args(argv)
    if getattr(ns, "not_implemented", None):
        print(f"{ns.not_implemented} is declared for the issue #44 stack but implemented in a later PR", file=sys.stderr)
        return 2
    if ns.command == "ask":
        return ask(ns)
    if ns.command == "edit":
        return write_mode(ns, "edit")
    if ns.command == "fix":
        return write_mode(ns, "fix")
    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
