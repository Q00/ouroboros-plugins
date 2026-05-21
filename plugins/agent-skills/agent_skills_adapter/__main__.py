"""Bounded AgentOS/Ouroboros adapter for addyosmani/agent-skills.

The adapter does not paste or execute upstream prompt files. It maps the
upstream command/skill surface into Ouroboros-native metadata and durable
handoff artifacts that downstream runners can inspect, attach, or execute
under their own permission gates.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

METADATA_PATH = Path(__file__).with_name("metadata.json")
DEFAULT_OUTPUT_DIR = Path(".omx") / "handoffs" / "agent-skills"


@dataclass(frozen=True)
class Capability:
    name: str
    summary: str
    risk: str
    mode: str
    upstream_path: str
    alias: str | None = None


def load_metadata() -> dict[str, Any]:
    with METADATA_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def command_map(metadata: dict[str, Any]) -> dict[str, Capability]:
    direct = {
        skill["name"]: Capability(
            name=skill["name"],
            summary=skill["summary"],
            risk=skill["risk"],
            mode=skill["mode"],
            upstream_path=skill["path"],
        )
        for skill in metadata["skills"]
    }
    for alias in metadata["lifecycle_aliases"]:
        target = direct[alias["target_skill"]]
        direct[alias["name"]] = Capability(
            name=target.name,
            summary=alias["summary"],
            risk=alias["risk"],
            mode=target.mode if alias["name"] != "ship" else "fanout",
            upstream_path=target.upstream_path,
            alias=alias["name"],
        )
    return direct


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def run_id(command: str, scope: str, argv: list[str]) -> str:
    digest = hashlib.sha256("\0".join([command, scope, *argv]).encode("utf-8")).hexdigest()[:10]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}-{digest}"


def write_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


def permissions_for(
    capability: Capability,
    *,
    allow_shell: bool,
    allow_network: bool,
    allow_browser: bool,
) -> tuple[list[str], list[str]]:
    used = ["filesystem:read", "filesystem:write"]
    blocked: list[str] = []
    if allow_shell:
        used.append("shell:execute")
    if allow_network:
        used.append("network:read")
    if allow_browser:
        used.append("browser:devtools")

    if capability.mode == "guarded_edit" and not allow_shell:
        blocked.append(
            "shell:execute not granted; adapter produced an execution handoff "
            "instead of running commands or mutating code"
        )
    if capability.alias == "ship" or capability.name == "shipping-and-launch":
        if not allow_shell:
            blocked.append("shell:execute not granted; launch readiness checks are represented as requested verification commands")
    if capability.name == "browser-testing-with-devtools" and not allow_browser:
        blocked.append("browser:devtools not granted; browser automation is blocked and recorded as a handoff task")
    return used, blocked


def audit_event(
    metadata: dict[str, Any],
    capability: Capability,
    argv: list[str],
    permissions: list[str],
    status: str,
    message: str,
) -> dict[str, Any]:
    return {
        "schema_version": "0.1",
        "event_type": "plugin.completed" if status == "success" else "plugin.failed",
        "occurred_at": utc_now(),
        "plugin": {
            "name": metadata["plugin_name"],
            "version": metadata["plugin_version"],
            "source_type": "local_path",
        },
        "command": {"namespace": "agent-skills", "name": capability.alias or capability.name, "argv": argv},
        "trust_state": "trusted",
        "capabilities_used": [
            "seed:write",
            "ledger:write",
            "state:write",
            "provenance:write",
            "handoff:attach",
            "progress:write",
        ],
        "permissions_used": permissions,
        "provenance": {
            "upstream_repository": metadata["upstream_repository"],
            "upstream_commit": metadata["upstream_commit"],
            "upstream_skill_path": capability.upstream_path,
            "upstream_license": metadata["upstream_license"],
        },
        "result": {"status": status, "message": message},
    }


def markdown_handoff(payload: dict[str, Any]) -> str:
    lines = [
        f"# Agent Skills Handoff: {payload['command']['invoked']}",
        "",
        "## Summary",
        "",
        payload["result"]["summary"],
        "",
        "## Command",
        "",
        f"- Plugin: `{payload['plugin']['name']}` `{payload['plugin']['version']}`",
        f"- Namespace: `agent-skills`",
        f"- Invoked: `{payload['command']['invoked']}`",
        f"- Upstream skill: `{payload['command']['upstream_skill']}`",
        f"- Scope: `{payload['command']['scope'] or 'not supplied'}`",
        f"- Risk: `{payload['risk']['classification']}`",
        f"- Mode: `{payload['risk']['mode']}`",
        "",
        "## Provenance",
        "",
        f"- Repository: {payload['provenance']['repository']}",
        f"- Commit: `{payload['provenance']['commit']}`",
        f"- Skill path: `{payload['provenance']['skill_path']}`",
        f"- License: `{payload['provenance']['license']}`",
        "",
        "## Permissions Used",
        "",
        *[f"- `{p}`" for p in payload["permissions_used"]],
        "",
        "## Capabilities Used",
        "",
        *[f"- `{c}`" for c in payload["capabilities_used"]],
        "",
        "## Evidence",
        "",
        *([f"- {item}" for item in payload["evidence"]] or ["- No external evidence supplied; this adapter recorded a structured capability handoff only."]),
        "",
        "## Verification Commands",
        "",
        *([f"- `{cmd}`" for cmd in payload["verification_commands"]] or ["- None run by adapter; downstream execution must record verification before merge or release."]),
        "",
        "## Blocked / Guarded Conditions",
        "",
        *([f"- {item}" for item in payload["blocked_conditions"]] or ["- None."]),
        "",
        "## Recommended Next Action",
        "",
        payload["result"]["recommended_next_action"],
        "",
        "## Machine Payload",
        "",
        "```json",
        json.dumps(payload, indent=2, ensure_ascii=False),
        "```",
        "",
    ]
    return "\n".join(lines)


def build_payload(
    args: argparse.Namespace,
    metadata: dict[str, Any],
    capability: Capability,
    argv: list[str],
) -> tuple[dict[str, Any], str]:
    permissions, blocked = permissions_for(
        capability,
        allow_shell=args.allow_shell,
        allow_network=args.allow_network,
        allow_browser=args.allow_browser,
    )
    status = "success"
    summary = args.summary or capability.summary
    if capability.mode in {"guarded_edit", "fanout"} and blocked:
        summary = f"{summary} Guarded execution was not performed; a handoff was generated."
    if capability.name == "browser-testing-with-devtools" and any("browser:devtools" in b for b in blocked):
        status = "blocked"
    recommended = "Attach this handoff to `ooo auto` or a future Workflow IR run-step so execution occurs under explicit trust grants."
    if capability.mode == "report":
        recommended = "Use this report artifact as review evidence; run any listed verification commands before acting on findings."
    elif capability.mode == "artifact_write":
        recommended = "Review the generated spec/plan/document handoff, then pass the bounded scope to `ooo auto` if implementation is needed."
    elif capability.mode == "fanout":
        recommended = "Synthesize code-reviewer, security-auditor, and test-engineer readiness outputs into a go/no-go decision before release."

    invoked = capability.alias or capability.name
    rid = run_id(invoked, args.scope or "", argv)
    artifact_base = Path(args.output_dir) / invoked / rid
    payload: dict[str, Any] = {
        "schema_version": "0.1",
        "run_id": rid,
        "created_at": utc_now(),
        "plugin": {"name": metadata["plugin_name"], "version": metadata["plugin_version"]},
        "upstream": {"name": "addyosmani/agent-skills", "version": metadata["upstream_plugin_version"]},
        "command": {
            "namespace": "agent-skills",
            "invoked": invoked,
            "upstream_skill": capability.name,
            "lifecycle_alias": capability.alias,
            "scope": args.scope or "",
            "argv": argv,
        },
        "risk": {"classification": capability.risk, "mode": capability.mode, "requires_confirmation": False},
        "permissions_used": permissions,
        "capabilities_used": [
            "seed:write",
            "ledger:write",
            "state:write",
            "provenance:write",
            "handoff:attach",
            "progress:write",
        ],
        "provenance": {
            "repository": metadata["upstream_repository"],
            "commit": metadata["upstream_commit"],
            "skill_path": capability.upstream_path,
            "license": metadata["upstream_license"],
            "copied_prompt_pack": "false",
        },
        "evidence": args.evidence or [],
        "verification_commands": args.verification_command or [],
        "blocked_conditions": blocked,
        "ship_fanout": metadata["personas"] if capability.mode == "fanout" else [],
        "result": {
            "status": status,
            "summary": summary,
            "recommended_next_action": recommended,
            "suitable_for_ooo_auto_handoff": True,
        },
        "artifacts": {
            "markdown": str(artifact_base.with_suffix(".md")),
            "json": str(artifact_base.with_suffix(".json")),
            "audit_event": str(artifact_base.with_suffix(".audit.json")),
        },
    }
    message = "handoff artifact generated" if status == "success" else "handoff generated with blocked authority"
    return payload, message


def emit_list(metadata: dict[str, Any]) -> None:
    data = {
        "plugin": metadata["plugin_name"],
        "version": metadata["plugin_version"],
        "upstream_repository": metadata["upstream_repository"],
        "upstream_commit": metadata["upstream_commit"],
        "lifecycle_aliases": metadata["lifecycle_aliases"],
        "skills": metadata["skills"],
    }
    sys.stdout.write(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def main(argv: list[str] | None = None) -> int:
    metadata = load_metadata()
    commands = command_map(metadata)
    parser = argparse.ArgumentParser(prog="agent-skills")
    parser.add_argument("command", nargs="?", help="Lifecycle alias or upstream skill command.")
    parser.add_argument("--list-skills", action="store_true", help="List lifecycle aliases and direct upstream skills.")
    parser.add_argument("--scope", default="", help="Bounded goal, file path, diff, issue, or work scope.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Artifact output directory.")
    parser.add_argument("--summary", default="", help="Result summary to include in the handoff.")
    parser.add_argument("--evidence", action="append", default=[], help="Evidence line to include in the handoff.")
    parser.add_argument(
        "--verification-command",
        action="append",
        default=[],
        help="Verification command to record; the adapter does not execute it.",
    )
    parser.add_argument("--allow-shell", action="store_true", help="Record that shell:execute authority was explicitly granted.")
    parser.add_argument("--allow-network", action="store_true", help="Record that network:read authority was explicitly granted.")
    parser.add_argument("--allow-browser", action="store_true", help="Record that browser:devtools authority was explicitly granted.")
    args, extra = parser.parse_known_args(argv)
    args.extra = extra

    if args.list_skills:
        emit_list(metadata)
        return 0
    if not args.command:
        parser.error("command is required unless --list-skills is used")
    if args.command not in commands:
        known = ", ".join(sorted(commands))
        parser.error(f"unknown command {args.command!r}; known commands: {known}")

    capability = commands[args.command]
    raw_argv = [args.command, *args.extra]
    payload, message = build_payload(args, metadata, capability, raw_argv)
    json_path = Path(payload["artifacts"]["json"])
    md_path = Path(payload["artifacts"]["markdown"])
    audit_path = Path(payload["artifacts"]["audit_event"])
    write_atomic(json_path, json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    write_atomic(md_path, markdown_handoff(payload))
    write_atomic(audit_path, json.dumps(audit_event(metadata, capability, raw_argv, payload["permissions_used"], payload["result"]["status"], message), indent=2, ensure_ascii=False) + "\n")
    sys.stdout.write(
        json.dumps(
            {
                "status": payload["result"]["status"],
                "handoff_path": str(md_path),
                "handoff_json": str(json_path),
                "audit_event_path": str(audit_path),
                "ooo_auto_ready": True,
                "blocked_conditions": payload["blocked_conditions"],
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n"
    )
    return 0 if payload["result"]["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
