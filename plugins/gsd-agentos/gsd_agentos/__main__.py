"""CLI entrypoint for the gsd-agentos plugin."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .command_catalog import all_commands, get_command, load_catalog
from .command_runner import run_upstream
from .handoff import write_handoff
from .provenance import append_audit, build_record
from .risk_policy import check_policy, trusted_scopes
from .validation import validate_catalog


def _attach_catalog(command: dict) -> dict:
    catalog = load_catalog()
    out = dict(command)
    out["catalog"] = {"upstream_commit": catalog.get("upstream", {}).get("commit")}
    return out


def cmd_list(args: argparse.Namespace) -> int:
    rows = all_commands()
    if args.risk:
        rows = [c for c in rows if c["risk"] == args.risk]
    if args.json:
        print(json.dumps(rows, indent=2, sort_keys=True))
    else:
        for c in rows:
            print(f"gsd {c['canonical_name']:<24} {c['risk']:<12} {c['description']}")
    return 0


def cmd_explain(args: argparse.Namespace) -> int:
    command = get_command(args.command)
    if args.json:
        print(json.dumps(command, indent=2, sort_keys=True))
    else:
        print(f"gsd {command['canonical_name']}")
        print(f"  summary: {command['description']}")
        print(f"  usage: {command['usage']}")
        print(f"  risk: {command['risk']}")
        print(f"  required_permissions: {', '.join(command['required_permissions'])}")
        print(f"  upstream: {command['upstream_file']}")
    return 0


def cmd_validate(_: argparse.Namespace) -> int:
    errors = validate_catalog(load_catalog())
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print(f"catalog validation passed ({len(all_commands())} gsd command(s))")
    return 0


def cmd_invoke(args: argparse.Namespace) -> int:
    root = Path(args.target_repo).expanduser().resolve()
    if not root.is_dir():
        print(f"target repo does not exist: {root}", file=sys.stderr)
        return 2
    command = _attach_catalog(get_command(args.command))
    policy = check_policy(command, execute=args.execute, confirm=args.confirm)
    audit_events = [
        build_record(
            command,
            argv=args.args,
            target_repo=root,
            status="policy_checked",
            event_type="plugin.invoked",
        )
    ]
    trust = trusted_scopes()
    can_write_audit = "filesystem:read" in trust and "filesystem:write" in trust
    if can_write_audit:
        append_audit(root, audit_events[-1])
    if not policy.allowed:
        blocked = build_record(
            command,
            argv=args.args,
            target_repo=root,
            status="blocked",
            event_type="plugin.failed",
            trust_state="blocked",
        )
        audit_events.append(blocked)
        if can_write_audit:
            append_audit(root, blocked)
        print(policy.message, file=sys.stderr)
        return 3
    runner_result = None
    if args.execute:
        runner_result = run_upstream(
            command, args.args, target_repo=root, timeout=args.timeout
        )
    if runner_result and runner_result.get("status") == "blocked":
        status = "blocked"
    else:
        status = (
            "completed"
            if not runner_result or runner_result.get("exit_code") == 0
            else "failed"
        )
    markdown_path = json_path = None
    if args.handoff or command.get("risk") != "read_only":
        markdown_path, json_path, _ = write_handoff(
            root, command, args.args, status=status, runner_result=runner_result
        )
    outputs = [p for p in [markdown_path, json_path] if p]
    completed = build_record(
        command,
        argv=args.args,
        target_repo=root,
        status=status,
        output_paths=outputs,
        exit_code=(runner_result or {}).get("exit_code"),
        event_type="plugin.completed" if status == "completed" else "plugin.failed",
        trust_state="blocked" if status == "blocked" else "trusted",
    )
    audit_events.append(completed)
    if can_write_audit:
        append_audit(root, completed)
    result = {
        "status": status,
        "command": command["canonical_name"],
        "risk": command["risk"],
        "handoff": str(json_path) if json_path else None,
        "runner": runner_result,
        "audit_events": audit_events,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    if status == "completed":
        return 0
    if status == "blocked":
        return 3
    return 4


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gsd-agentos", description="AgentOS adapter for GSD commands"
    )
    sub = parser.add_subparsers(dest="subcommand", required=True)
    p_list = sub.add_parser("list", help="List exposed GSD commands")
    p_list.add_argument("--risk", choices=["read_only", "write", "destructive"])
    p_list.add_argument("--json", action="store_true")
    p_list.set_defaults(func=cmd_list)
    p_explain = sub.add_parser("explain", help="Explain one GSD command contract")
    p_explain.add_argument("command")
    p_explain.add_argument("--json", action="store_true")
    p_explain.set_defaults(func=cmd_explain)
    p_validate = sub.add_parser(
        "validate-catalog", help="Validate reviewed command catalog"
    )
    p_validate.set_defaults(func=cmd_validate)
    p_invoke = sub.add_parser(
        "invoke", help="Policy-check and optionally run a GSD command"
    )
    p_invoke.add_argument("command")
    p_invoke.add_argument("args", nargs="*")
    p_invoke.add_argument("--target-repo", default=".")
    p_invoke.add_argument("--execute", action="store_true")
    p_invoke.add_argument("--handoff", action="store_true")
    p_invoke.add_argument("--confirm")
    p_invoke.add_argument("--timeout", type=int, default=900)
    p_invoke.set_defaults(func=cmd_invoke)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args, unknown = parser.parse_known_args(argv)
    if getattr(args, "subcommand", None) == "invoke" and unknown:
        args.args.extend(unknown)
    elif unknown:
        parser.error("unrecognized arguments: " + " ".join(unknown))
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
