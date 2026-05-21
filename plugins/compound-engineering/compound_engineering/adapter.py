from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .artifacts import relative_to_repo, repo_root_from, slugify, timestamp, write_json, write_markdown
from .audit import audit_event, write_audit
from .commands import COMMANDS, COMMAND_BY_NAME, PLUGIN_NAME, PLUGIN_VERSION, UPSTREAM_REPOSITORY, UPSTREAM_VERSION
from .upstream import list_agents, read_skill_excerpt, skill_path

NEXT_COMMAND = {
    "brainstorm": "compound plan",
    "plan": "compound work",
    "work": "compound code-review",
    "work-beta": "compound code-review",
    "code-review": "compound compound",
    "debug": "compound plan or compound work",
    "compound": "compound brainstorm for the next improvement",
    "compound-refresh": "compound brainstorm for the next improvement",
}


def _artifact_dir(command: str) -> str:
    return {
        "brainstorm": "brainstorms",
        "plan": "plans",
        "code-review": "reviews",
        "debug": "debug",
        "compound": "learnings",
        "compound-refresh": "learnings",
    }.get(command, command)


def _artifact_extension(command: str) -> str:
    return ".json" if command == "code-review" else ".md"


def _primary_artifact_path(repo_root: Path, command: str, input_text: str, run_id: str) -> Path:
    slug = slugify(input_text or command, fallback=command)
    suffix = _artifact_extension(command)
    return repo_root / ".omx" / "compound" / _artifact_dir(command) / f"{run_id}-{slug}{suffix}"


def actual_permissions_used(status: str) -> list[str]:
    # The adapter itself only reads vendored CE assets and writes bounded local
    # handoff/audit artifacts. Command-specific elevated permissions remain
    # declared as required_permissions until a trusted runtime executes them.
    return ["filesystem:read", "filesystem:write"]


def build_payload(command: dict[str, Any], input_text: str, confirm: bool, argv: list[str]) -> tuple[dict[str, Any], str]:
    status = "success"
    message = "handoff artifact generated"
    if command["risk"] == "destructive" and not confirm:
        status = "blocked"
        message = "destructive command requires --confirm before a handoff can be generated"
    provenance = {
        "upstream_repository": UPSTREAM_REPOSITORY,
        "upstream_version": UPSTREAM_VERSION,
        "upstream_skill": command["upstream_skill"],
        "adapter_command": f"compound {command['command']}",
        "invoked_by": "direct",
    }
    payload = {
        "schema_version": "0.1",
        "plugin": {"name": PLUGIN_NAME, "version": PLUGIN_VERSION},
        "command": {"namespace": "compound", "name": command["command"], "argv": argv},
        "input": {"text": input_text},
        "source": {
            "repository": UPSTREAM_REPOSITORY,
            "version": UPSTREAM_VERSION,
            "skill": command["upstream_skill"],
            "skill_asset": str(skill_path(command["upstream_skill"]).relative_to(Path(__file__).resolve().parents[1])),
        },
        "risk": command["risk"],
        "status": status,
        "message": message,
        "capabilities_used": command["capabilities"],
        "permissions_used": actual_permissions_used(status),
        "required_permissions": command["permissions"],
        "artifacts": [],
        "handoff": {
            "summary": command["handoff"],
            "next_recommended_command": NEXT_COMMAND.get(command["command"], "compound code-review or compound compound when appropriate"),
            "downstream_target": "Ouroboros runtime / AgentOS command dispatcher",
            "resumability": "Re-run this adapter command with the same input; use the run result JSON to recover provenance and artifact paths.",
        },
        "audit": {"provenance": provenance},
        "verification": {
            "behavior": "Adapter validates the command name, risk gate, vendored skill asset, and writes bounded .omx/compound artifacts without generic shell passthrough.",
            "read_only_boundary": "read_only commands may write adapter audit/handoff artifacts under .omx/compound but do not mutate project source files or external services.",
        },
        "upstream_skill_excerpt": read_skill_excerpt(command["upstream_skill"]),
        "available_agent_assets": list_agents() if command["command"] in {"code-review", "doc-review", "debug", "slack-research", "plan"} else [],
    }
    return payload, status


def run_command(command_name: str, input_text: str, *, confirm: bool = False, repo_root: Path | None = None, argv: list[str] | None = None) -> dict[str, Any]:
    if command_name not in COMMAND_BY_NAME:
        raise KeyError(command_name)
    command = COMMAND_BY_NAME[command_name]
    argv = argv or [command_name] + ([input_text] if input_text else [])
    root = repo_root or repo_root_from()
    run_id = timestamp()
    payload, status = build_payload(command, input_text, confirm, argv)
    artifact_path = _primary_artifact_path(root, command_name, input_text, run_id)
    run_path = root / ".omx" / "compound" / "runs" / run_id / "result.json"
    audit_path = root / ".omx" / "compound" / "runs" / run_id / "audit-event.json"

    if artifact_path.suffix == ".json":
        artifact_payload = {
            "status": status,
            "command": payload["command"],
            "source": payload["source"],
            "risk": payload["risk"],
            "findings": [],
            "handoff": payload["handoff"],
        }
        write_json(artifact_path, artifact_payload)
    else:
        write_markdown(
            artifact_path,
            f"Compound Engineering {command_name} handoff",
            {
                "Status": status,
                "Input": input_text or "(none)",
                "Source": f"{UPSTREAM_REPOSITORY} {UPSTREAM_VERSION} / `{command['upstream_skill']}`",
                "Risk and permissions": json.dumps({"risk": command["risk"], "permissions": command["permissions"]}, indent=2),
                "Next step": payload["handoff"]["next_recommended_command"],
                "Upstream skill excerpt": payload["upstream_skill_excerpt"],
            },
        )

    payload["artifacts"] = [relative_to_repo(artifact_path, root), relative_to_repo(run_path, root), relative_to_repo(audit_path, root)]
    payload["audit"]["provenance"]["artifact_path"] = relative_to_repo(artifact_path, root)
    write_json(run_path, payload)
    event = audit_event(
        event_type="plugin.completed" if status == "success" else "plugin.failed",
        command_name=command_name,
        argv=argv,
        capabilities_used=payload["capabilities_used"],
        permissions_used=payload["permissions_used"],
        provenance=payload["audit"]["provenance"],
        status=status,
        message=payload["message"],
    )
    write_audit(audit_path, event)
    return payload


def command_table() -> list[dict[str, Any]]:
    return [
        {
            "command": f"compound {c['command']}",
            "upstream_skill": c["upstream_skill"],
            "risk": c["risk"],
            "permissions": c["permissions"],
            "summary": c["summary"],
        }
        for c in COMMANDS
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m compound_engineering", description="Bounded AgentOS adapter for Compound Engineering skills.")
    parser.add_argument("command", nargs="?", help="Compound command name, e.g. brainstorm, plan, work, code-review")
    parser.add_argument("input", nargs="*", help="Original CE command input text")
    parser.add_argument("--confirm", action="store_true", help="Allow destructive workflow handoff generation")
    parser.add_argument("--list-commands", action="store_true", help="Print command metadata as JSON")
    parser.add_argument("--repo-root", type=Path, default=None, help="Repository root for .omx/compound artifacts")
    ns = parser.parse_args(argv)
    if ns.list_commands:
        print(json.dumps(command_table(), indent=2, sort_keys=True))
        return 0
    if not ns.command:
        parser.print_help(sys.stderr)
        return 2
    if ns.command not in COMMAND_BY_NAME:
        print(f"unknown compound command: {ns.command}", file=sys.stderr)
        return 2
    input_text = " ".join(ns.input).strip()
    payload = run_command(ns.command, input_text, confirm=ns.confirm, repo_root=ns.repo_root, argv=[ns.command, *ns.input])
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["status"] == "success" else 1
