"""Ouroboros-native SuperClaude adapter.

The MVP is intentionally a prompt/asset adapter, not an unrestricted shell
wrapper around SuperClaude. It exposes the pinned SuperClaude command mental
model through structured output, trust-gated artifact writes, and auditable
handoff payloads.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = PLUGIN_ROOT / "command_catalog.json"
ASSETS = PLUGIN_ROOT / "assets"
UPSTREAM = {
    "repository": "https://github.com/SuperClaude-Org/SuperClaude_Framework",
    "commit": "226c45cc93b865108843a669c6545d421784b68c",
    "commit_date": "2026-04-27T08:38:57+05:30",
    "version": "4.3.0",
    "license": "MIT",
}
WRITE_COMMANDS = {
    "brainstorm",
    "build",
    "cleanup",
    "design",
    "document",
    "implement",
    "improve",
    "index",
    "index-repo",
    "pm",
    "reflect",
    "save",
    "spawn",
    "task",
    "test",
    "workflow",
}
SHELL_COMMANDS = {"build", "git", "test"}
NETWORK_COMMANDS = {"research", "deep-research"}
DESTRUCTIVE_GIT_TERMS = {"push", "reset", "merge", "rebase", "clean", "tag", "release"}
SKILL_ALIASES = {"research": "deep-research"}

HANDOFF_COMMANDS = {
    "brainstorm",
    "confidence-check",
    "deep-research",
    "design",
    "document",
    "estimate",
    "pm",
    "reflect",
    "research",
    "spawn",
    "spec-panel",
    "task",
    "token-efficiency",
    "troubleshoot",
    "workflow",
}


@dataclass(frozen=True)
class Selection:
    command: str
    display_command: str
    args: list[str]
    command_asset: Path | None
    skill_asset: Path | None
    agent_asset: Path | None
    mode_asset: Path | None


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _catalog_items(kind: str | None = None) -> list[dict]:
    items = _load_json(CATALOG_PATH)["items"]
    if kind is None:
        return items
    return [item for item in items if item.get("kind") == kind]


def _valid_names(kind: str) -> list[str]:
    return sorted(item["name"] for item in _catalog_items(kind))


def _mode_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _mode_asset(mode: str | None) -> Path | None:
    if not mode:
        return None
    wanted = _mode_key(mode)
    for item in _catalog_items("mode"):
        if wanted in {item.get("key"), _mode_key(item["name"]), _mode_key(Path(item["source"]).stem.removeprefix("MODE_"))}:
            return PLUGIN_ROOT / item["source"]
    raise SystemExit(f"unsupported mode {mode!r}; valid modes: {', '.join(item['name'] for item in _catalog_items('mode'))}")


def _agent_asset(agent: str | None) -> Path | None:
    if not agent:
        return None
    path = ASSETS / "agents" / f"{agent}.md"
    if path.exists():
        return path
    raise SystemExit(f"unsupported agent {agent!r}; valid agents: {', '.join(_valid_names('agent'))}")


def _split_options(argv: list[str]) -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(prog="superclaude_ouroboros", add_help=True)
    parser.add_argument("--json", action="store_true", help="Emit JSON only; this is the default shape.")
    parser.add_argument("--list", choices=["commands", "skills", "agents", "modes", "all"], help="List packaged surfaces.")
    parser.add_argument("--agent", help="Optional packaged SuperClaude agent to include.")
    parser.add_argument("--mode", help="Optional packaged SuperClaude mode to include.")
    parser.add_argument("--artifact-dir", type=Path, help="Directory for explicit handoff/audit artifacts.")
    parser.add_argument("--audit-dir", type=Path, help="Directory for audit-event JSONL output.")
    parser.add_argument("--confirm-destructive", action="store_true", help="Required for destructive Git-style paths.")
    parser.add_argument("command", nargs="?")
    ns, rest = parser.parse_known_args(argv)
    return ns, rest


def _trust_scopes() -> set[str]:
    raw = os.environ.get("OUROBOROS_TRUSTED_SCOPES") or os.environ.get("SUPERCLAUDE_OUROBOROS_TRUSTED_SCOPES") or ""
    return {part.strip() for part in re.split(r"[,\s]+", raw) if part.strip()}


def _has_scope(scope: str) -> bool:
    return scope in _trust_scopes()


def _required_scopes(command: str, args: Iterable[str], *, writes_artifacts: bool = False) -> list[str]:
    scopes: list[str] = []
    if writes_artifacts:
        scopes.append("filesystem:write")
    if command in WRITE_COMMANDS and "filesystem:write" not in scopes:
        scopes.append("filesystem:write")
    if command in SHELL_COMMANDS:
        scopes.append("shell:execute")
    if command in NETWORK_COMMANDS and any(a in {"--web", "--network", "--mcp"} for a in args):
        scopes.append("network:read")
    if command == "git" and any(a in DESTRUCTIVE_GIT_TERMS for a in args):
        scopes.append("git:write")
    return scopes


def _event(event_type: str, command: str, argv: list[str], status: str, message: str, permissions: list[str]) -> dict:
    return {
        "schema_version": "0.1",
        "event_type": event_type,
        "occurred_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "plugin": {"name": "superclaude", "version": "4.3.0", "source_type": "local_path"},
        "command": {"namespace": "superclaude", "name": command, "argv": argv},
        "trust_state": "trusted" if all(_has_scope(scope) for scope in permissions) else ("blocked" if permissions else "installed"),
        "capabilities_used": ["state:read", "provenance:write", "progress:write"],
        "permissions_used": permissions,
        "provenance": {
            "upstream_commit": UPSTREAM["commit"][:12],
            "adapter": "superclaude_ouroboros",
        },
        "result": {"status": status, "message": message},
    }


def _write_jsonl(path: Path, events: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event, sort_keys=True) + "\n")


def _read_excerpt(path: Path | None, limit: int = 1800) -> str | None:
    if path is None:
        return None
    text = path.read_text(encoding="utf-8")
    return text[:limit]


def _asset_summary(path: Path | None) -> dict | None:
    if path is None:
        return None
    return {"path": str(path.relative_to(PLUGIN_ROOT)), "excerpt": _read_excerpt(path)}


def _select(command: str | None, rest: list[str], agent: str | None, mode: str | None) -> Selection:
    if not command:
        command = "help"
    command_names = set(_valid_names("command"))
    skill_names = set(_valid_names("skill"))
    display = command
    skill_asset: Path | None = None
    command_asset: Path | None = None
    args = list(rest)
    selected_agent = agent
    if command == "sc" and args:
        nested = args.pop(0)
        if nested in command_names or nested in skill_names:
            command = nested
            display = f"sc {nested}"
    if command == "skill":
        if not args:
            raise SystemExit("usage: ooo superclaude skill <skill-name> [args...]")
        skill = args.pop(0)
        if skill not in skill_names:
            raise SystemExit(f"unsupported skill {skill!r}; valid skills: {', '.join(sorted(skill_names))}")
        display = f"skill {skill}"
        command = skill
        skill_asset = ASSETS / "skills" / skill / "SKILL.md"
        command_asset = ASSETS / "commands" / f"{skill}.md"
        if not command_asset.exists():
            command_asset = None
    elif command in skill_names and command not in command_names:
        skill_asset = ASSETS / "skills" / command / "SKILL.md"
    else:
        if command not in command_names:
            raise SystemExit(f"unsupported command {command!r}; valid commands: {', '.join(sorted(command_names))}")
        command_asset = ASSETS / "commands" / f"{command}.md"
        overlap_name = SKILL_ALIASES.get(command, command)
        overlap = ASSETS / "skills" / overlap_name / "SKILL.md"
        if overlap.exists():
            skill_asset = overlap
        if command == "agent" and args and selected_agent is None:
            candidate = args[0]
            if candidate in set(_valid_names("agent")):
                selected_agent = candidate
                display = f"agent {candidate}"
    return Selection(command=command, display_command=display, args=args, command_asset=command_asset, skill_asset=skill_asset, agent_asset=_agent_asset(selected_agent), mode_asset=_mode_asset(mode))


def _list_payload(kind: str) -> dict:
    kinds = ["command", "skill", "agent", "mode"] if kind == "all" else [{"commands":"command","skills":"skill","agents":"agent","modes":"mode"}[kind]]
    return {"plugin": "superclaude", "upstream": UPSTREAM, "items": {k: _catalog_items(k) for k in kinds}}


def _write_handoff(artifact_dir: Path, selection: Selection, permissions: list[str]) -> Path:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^a-z0-9-]+", "-", selection.display_command.lower()).strip("-") or "command"
    path = artifact_dir / f"superclaude-{safe}-handoff.md"
    sections = [
        f"# SuperClaude Handoff: `{selection.display_command}`",
        "",
        f"Upstream: {UPSTREAM['repository']} @ `{UPSTREAM['commit']}` (`{UPSTREAM['version']}`)",
        f"Arguments: `{ ' '.join(selection.args) }`",
        f"Required scopes: {', '.join(permissions) if permissions else 'none'}",
        "",
        "## Command instructions",
        _read_excerpt(selection.command_asset, 5000) or "No separate command asset.",
    ]
    if selection.skill_asset:
        sections += ["", "## Skill instructions", _read_excerpt(selection.skill_asset, 5000) or ""]
    if selection.agent_asset:
        sections += ["", "## Agent instructions", _read_excerpt(selection.agent_asset, 5000) or ""]
    if selection.mode_asset:
        sections += ["", "## Mode instructions", _read_excerpt(selection.mode_asset, 5000) or ""]
    path.write_text("\n".join(sections).rstrip() + "\n", encoding="utf-8")
    return path


def _events(selection: Selection, status: str, message: str, permissions: list[str]) -> list[dict]:
    result_event = "plugin.completed" if status == "success" else "plugin.failed"
    events = [_event("plugin.invoked", selection.command, selection.args, "success", "invocation accepted by adapter", [])]
    if permissions:
        gate_status = "success" if status == "success" else "blocked"
        events.append(_event("plugin.permission_used", selection.command, selection.args, gate_status, "permission gate evaluated", permissions))
    events.append(_event(result_event, selection.command, selection.args, status, message, permissions))
    return events


def _risk(command: str, destructive: bool) -> str:
    if destructive:
        return "destructive"
    return "write" if command in WRITE_COMMANDS else "read_only"


def _payload(selection: Selection, status: str, message: str, permissions: list[str], missing: list[str], handoff_path: Path | None, events: list[dict]) -> dict:
    return {
        "plugin": "superclaude",
        "status": status,
        "message": message,
        "command": {"namespace": "superclaude", "name": selection.command, "display": selection.display_command, "argv": selection.args},
        "risk": _risk(selection.command, "git:write" in permissions),
        "required_scopes": permissions,
        "missing": missing,
        "assets": {
            "command": _asset_summary(selection.command_asset),
            "skill": _asset_summary(selection.skill_asset),
            "agent": _asset_summary(selection.agent_asset),
            "mode": _asset_summary(selection.mode_asset),
        },
        "handoff_artifact": str(handoff_path) if handoff_path else None,
        "audit_events": events,
        "upstream": UPSTREAM,
        "notes": [
            "MVP prepares SuperClaude instructions and handoff artifacts; it does not auto-install MCP servers.",
            "Compatibility alias `sc` is documented but cannot be a namespace under schema 0.1.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    ns, rest = _split_options(list(sys.argv[1:] if argv is None else argv))
    if ns.list:
        sys.stdout.write(json.dumps(_list_payload(ns.list), indent=2) + "\n")
        return 0

    try:
        selection = _select(ns.command, rest, ns.agent, ns.mode)
    except SystemExit as exc:
        sys.stderr.write(str(exc) + "\n")
        return 2

    writes_artifacts = bool(ns.audit_dir or (ns.artifact_dir and (selection.command in HANDOFF_COMMANDS or selection.skill_asset)))
    permissions = _required_scopes(selection.command, selection.args, writes_artifacts=writes_artifacts)
    missing = [scope for scope in permissions if not _has_scope(scope)]
    destructive = "git:write" in permissions
    if destructive and not ns.confirm_destructive:
        missing.append("confirmation:destructive")

    status = "blocked" if missing else "success"
    message = "command prepared" if status == "success" else f"blocked; missing {', '.join(missing)}"
    events = _events(selection, status, message, permissions)

    handoff_path = None
    should_handoff = selection.command in HANDOFF_COMMANDS or selection.skill_asset
    if status == "success" and ns.artifact_dir and should_handoff:
        handoff_path = _write_handoff(ns.artifact_dir, selection, permissions)
        for event in events:
            event["capabilities_used"] = sorted(set(event["capabilities_used"] + ["handoff:attach"]))

    if ns.audit_dir:
        _write_jsonl(ns.audit_dir / "superclaude-audit.jsonl", events)

    sys.stdout.write(json.dumps(_payload(selection, status, message, permissions, missing, handoff_path, events), indent=2) + "\n")
    return 0 if status == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
