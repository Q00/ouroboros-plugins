"""Reviewed GSD command catalog accessors."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

CATALOG_PATH = Path(__file__).with_name("command_catalog.json")


@lru_cache(maxsize=1)
def load_catalog() -> dict[str, Any]:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def all_commands() -> list[dict[str, Any]]:
    return list(load_catalog()["commands"])


def get_command(name: str) -> dict[str, Any]:
    normalized = name.removeprefix("gsd:").replace("_", "-")
    for command in all_commands():
        if command["canonical_name"] == normalized or normalized in command.get("aliases", []):
            return command
    available = ", ".join(c["canonical_name"] for c in all_commands())
    raise KeyError(f"unknown gsd command {name!r}; available commands: {available}")
