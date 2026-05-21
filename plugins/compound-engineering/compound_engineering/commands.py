from __future__ import annotations

import json
from pathlib import Path

UPSTREAM_VERSION = "3.8.3"
UPSTREAM_REPOSITORY = "EveryInc/compound-engineering-plugin"
PLUGIN_NAME = "compound-engineering"
PLUGIN_VERSION = "0.1.0"


def _load_commands() -> list[dict[str, object]]:
    metadata_path = Path(__file__).with_name("command_metadata.json")
    return json.loads(metadata_path.read_text(encoding="utf-8"))


COMMANDS = _load_commands()
COMMAND_BY_NAME = {command["command"]: command for command in COMMANDS}
UPSTREAM_BY_SKILL = {command["upstream_skill"]: command for command in COMMANDS}
