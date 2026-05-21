from __future__ import annotations

from pathlib import Path
from typing import Any

from .artifacts import timestamp, write_json
from .commands import PLUGIN_NAME, PLUGIN_VERSION


def audit_event(
    *,
    event_type: str,
    command_name: str,
    argv: list[str],
    capabilities_used: list[str],
    permissions_used: list[str],
    provenance: dict[str, str],
    status: str,
    message: str,
) -> dict[str, Any]:
    return {
        "schema_version": "0.1",
        "event_type": event_type,
        "occurred_at": timestamp(),
        "plugin": {
            "name": PLUGIN_NAME,
            "version": PLUGIN_VERSION,
            "source_type": "local_path",
        },
        "command": {
            "namespace": "compound",
            "name": command_name,
            "argv": argv,
        },
        "trust_state": "trusted",
        "capabilities_used": capabilities_used,
        "permissions_used": permissions_used,
        "provenance": provenance,
        "result": {
            "status": status,
            "message": message,
        },
    }


def write_audit(path: Path, payload: dict[str, Any]) -> None:
    write_json(path, payload)
