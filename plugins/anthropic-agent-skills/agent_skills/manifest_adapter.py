from __future__ import annotations

from pathlib import Path
from typing import Any

from .inspect import inspect_skill
from .license_policy import classify


def validate_path(path: Path) -> dict[str, Any]:
    path = path.resolve()
    if (path / "ouroboros.plugin.json").is_file():
        return {"format": "agent-skills.validation.v1", "path": str(path), "kind": "ouroboros-plugin", "valid": True, "warnings": []}
    inspected = inspect_skill(path)
    policy = classify(inspected["name"], path)
    warnings = []
    if not policy["can_vendor"]:
        warnings.append(policy["message"])
    if inspected["resources"].get("scripts"):
        warnings.append("scripts/ present: execution requires bounded adapter and shell:execute trust checks.")
    return {"format": "agent-skills.validation.v1", "path": str(path), "kind": "agent-skill", "valid": True, "inspection": inspected, "license_policy": policy, "warnings": warnings}
