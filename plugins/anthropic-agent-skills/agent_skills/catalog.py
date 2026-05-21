from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG = PACKAGE_ROOT / "catalog" / "anthropic-skills.json"


def load_catalog(path: Path | None = None) -> dict[str, Any]:
    catalog_path = path or DEFAULT_CATALOG
    return json.loads(catalog_path.read_text(encoding="utf-8"))


def skill_entry(skill_name: str, catalog: dict[str, Any] | None = None) -> dict[str, Any] | None:
    data = catalog or load_catalog()
    for entry in data.get("skills", []):
        if entry.get("source_skill") == skill_name:
            return entry
    return None


def command_entry(skill_name: str, command_name: str, catalog: dict[str, Any] | None = None) -> dict[str, Any] | None:
    entry = skill_entry(skill_name, catalog)
    if not entry:
        return None
    for command in entry.get("commands", []):
        if command.get("name") == command_name:
            return command
    return None
