from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .catalog import command_entry, skill_entry
from .license_policy import classify

VALID_STATUSES = {"success", "failed", "blocked", "cancelled"}


def make_handoff(
    skill: str,
    command: str,
    *,
    status: str,
    summary: str = "",
    inputs: list[Any] | None = None,
    outputs: list[Any] | None = None,
    evidence: list[Any] | None = None,
    permissions_used: list[Any] | None = None,
    loaded_files: list[str] | None = None,
    executed_scripts: list[str] | None = None,
    next_actions: list[str] | None = None,
) -> dict[str, Any]:
    if status not in VALID_STATUSES:
        raise ValueError(f"status must be one of {sorted(VALID_STATUSES)}")
    skill_meta = skill_entry(skill) or {}
    cmd_meta = command_entry(skill, command) or {}
    license_state = classify(skill)
    return {
        "schema": "agent-skills.handoff.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_skill": skill,
        "source_repository": skill_meta.get("source_repository", "https://github.com/anthropics/skills"),
        "source_revision": skill_meta.get("source_revision"),
        "license": license_state,
        "ouroboros_command": cmd_meta.get("surface", f"ooo skill {skill} {command}"),
        "goal": cmd_meta.get("summary", summary),
        "inputs": inputs or [],
        "outputs": outputs or [],
        "evidence": evidence or [],
        "permissions_used": permissions_used or [],
        "provenance": {
            "loaded_files": loaded_files or [],
            "executed_scripts": executed_scripts or [],
            "adapter": "agent-skills 0.1.0",
        },
        "audit_events": ["plugin.invoked", "plugin.permission_used", "plugin.completed" if status == "success" else "plugin.failed"],
        "result": {"status": status, "summary": summary or status},
        "next_actions": next_actions or [],
    }


def write_handoff(handoff: dict[str, Any], out: Path | None) -> str:
    payload = json.dumps(handoff, indent=2, sort_keys=True) + "\n"
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(payload, encoding="utf-8")
    return payload
