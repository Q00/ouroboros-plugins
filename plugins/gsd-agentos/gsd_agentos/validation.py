"""Catalog consistency checks used by tests and the CLI."""
from __future__ import annotations

from collections import Counter

REQUIRED_KEYS = {
    "upstream_file",
    "canonical_name",
    "description",
    "argument_hint",
    "namespace",
    "usage",
    "risk",
    "required_permissions",
    "expected_output_artifacts",
    "mutates",
}
VALID_RISKS = {"read_only", "write", "destructive"}


def validate_catalog(catalog: dict) -> list[str]:
    errors: list[str] = []
    commands = catalog.get("commands", [])
    if not commands:
        errors.append("catalog has no commands")
    names = Counter(c.get("canonical_name") for c in commands)
    for name, count in names.items():
        if count > 1:
            errors.append(f"duplicate command {name}")
    for command in commands:
        missing = REQUIRED_KEYS - set(command)
        if missing:
            errors.append(f"{command.get('canonical_name','<unknown>')} missing {sorted(missing)}")
        if command.get("namespace") != "gsd":
            errors.append(f"{command.get('canonical_name')} namespace must be gsd")
        if command.get("risk") not in VALID_RISKS:
            errors.append(f"{command.get('canonical_name')} has invalid risk")
        if command.get("risk") == "read_only" and any(
            command.get("mutates", {}).values()
        ):
            errors.append(
                f"{command.get('canonical_name')} read_only command declares mutation"
            )
        if (
            command.get("risk") == "destructive"
            and "shell:execute" not in command.get("required_permissions", [])
        ):
            errors.append(f"{command.get('canonical_name')} destructive command must require shell:execute")
    return errors
