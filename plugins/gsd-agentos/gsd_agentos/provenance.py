"""Bounded audit and provenance records for GSD AgentOS."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PLUGIN_NAME = "gsd-agentos"
PLUGIN_VERSION = "0.1.0"
SOURCE_TYPE = "local_path"


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def file_metadata(path: Path, root: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"path": str(path), "exists": False}
    data = path.read_bytes()
    return {
        "path": str(path.relative_to(root)),
        "exists": True,
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def _result_status(status: str) -> str:
    if status in {"completed", "success", "policy_checked"}:
        return "success"
    if status == "blocked":
        return "blocked"
    return "failed"


def build_record(
    command: dict,
    *,
    argv: list[str],
    target_repo: Path,
    status: str,
    output_paths: list[Path] | None = None,
    exit_code: int | None = None,
    next_action: str | None = None,
    event_type: str | None = None,
    trust_state: str = "trusted",
) -> dict[str, Any]:
    catalog = command.get("catalog", {})
    permissions = command.get("required_permissions", [])
    artifact_meta = [file_metadata(p, target_repo) for p in (output_paths or [])]
    provenance = {
        "upstream_repository": "https://github.com/gsd-build/get-shit-done",
        "upstream_commit": str(catalog.get("upstream_commit") or ""),
        "upstream_command_source_file": str(command.get("upstream_file") or ""),
        "upstream_command_source_sha256": str(command.get("upstream_sha256") or ""),
        "target_repo": str(target_repo),
        "working_directory": str(Path.cwd()),
        "risk": str(command.get("risk", "")),
    }
    if exit_code is not None:
        provenance["exit_code"] = str(exit_code)
    if next_action:
        provenance["next_suggested_action"] = next_action
    if artifact_meta:
        provenance["artifacts"] = json.dumps(artifact_meta, sort_keys=True)
    result_status = _result_status(status)
    return {
        "schema_version": "0.1",
        "event_type": event_type
        or ("plugin.failed" if result_status in {"blocked", "failed"} else "plugin.completed"),
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "plugin": {
            "name": PLUGIN_NAME,
            "version": PLUGIN_VERSION,
            "source_type": SOURCE_TYPE,
        },
        "command": {
            "namespace": command.get("namespace", "gsd"),
            "name": command["canonical_name"],
            "argv": argv,
        },
        "trust_state": trust_state,
        "capabilities_used": command.get("capabilities_used", []),
        "permissions_used": permissions,
        "provenance": provenance,
        "result": {
            "status": result_status,
            "message": status,
        },
    }


def append_audit(root: Path, event: dict[str, Any]) -> Path:
    audit_dir = root / ".ouroboros" / "handoffs" / "gsd"
    audit_dir.mkdir(parents=True, exist_ok=True)
    audit_path = audit_dir / "audit.jsonl"
    with audit_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True) + "\n")
    return audit_path
