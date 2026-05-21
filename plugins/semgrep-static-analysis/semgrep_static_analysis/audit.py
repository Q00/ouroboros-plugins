from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from . import PLUGIN_NAME, PLUGIN_VERSION

STANDARD_CAPABILITIES = ["ledger:write", "provenance:write", "handoff:attach", "progress:write"]
STANDARD_PERMISSIONS = ["filesystem:read", "shell:execute"]
NETWORK_PERMISSION = "network:read"


def audit_event(
    event_type: str,
    *,
    command_name: str,
    argv: list[str],
    status: str,
    message: str,
    permissions_used: list[str] | None = None,
    provenance: dict[str, str] | None = None,
    trust_state: str = "trusted",
) -> dict[str, Any]:
    return {
        "schema_version": "0.1",
        "event_type": event_type,
        "occurred_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "plugin": {
            "name": PLUGIN_NAME,
            "version": PLUGIN_VERSION,
            "source_type": "local_path",
        },
        "command": {
            "namespace": "semgrep",
            "name": command_name,
            "argv": argv,
        },
        "trust_state": trust_state,
        "capabilities_used": STANDARD_CAPABILITIES,
        "permissions_used": permissions_used or STANDARD_PERMISSIONS,
        "provenance": provenance or {},
        "result": {
            "status": status,
            "message": message,
        },
    }
