"""Validate repository contract JSON files.

This intentionally uses only the Python standard library so the contract repo
has no bootstrap dependency.
"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> object:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> int:
    plugin_schema = load_json(ROOT / "schemas" / "plugin.schema.json")
    audit_schema = load_json(ROOT / "schemas" / "audit-event.schema.json")
    index = load_json(ROOT / "registry" / "index.json")
    manifest = load_json(ROOT / "plugins" / "github-pr-ops" / "ouroboros.plugin.json")

    require(isinstance(plugin_schema, dict), "plugin schema must be an object")
    require(isinstance(audit_schema, dict), "audit schema must be an object")
    require(isinstance(index, dict), "registry index must be an object")
    require(isinstance(manifest, dict), "plugin manifest must be an object")

    required_manifest_keys = {
        "schema_version",
        "name",
        "version",
        "description",
        "source",
        "commands",
        "capabilities",
        "permissions",
        "entrypoint",
        "audit",
    }
    missing = required_manifest_keys - set(manifest)
    require(not missing, f"manifest missing required keys: {sorted(missing)}")

    commands = manifest["commands"]
    require(isinstance(commands, list) and commands, "manifest commands must be non-empty")
    namespaces = {command["namespace"] for command in commands}
    require(len(namespaces) == 1, "reference plugin should own exactly one namespace")

    permissions = manifest["permissions"]
    require(isinstance(permissions, list), "permissions must be a list")
    for permission in permissions:
        require("scope" in permission, "permission missing scope")
        require("risk" in permission, "permission missing risk")
        require("required" in permission, "permission missing required flag")

    print("contract validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
