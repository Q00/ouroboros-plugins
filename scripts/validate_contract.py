"""Validate repository contract JSON files against their JSON Schemas.

Validates:
  - plugins/<name>/ouroboros.plugin.json against schemas/<major>/plugin.schema.json
    (routed by the manifest's schema_version field)
  - catalog/index.json basic shape
  - schemas themselves are valid JSON Schema Draft 2020-12

Exits non-zero on any violation. Used by tests/CI as the gate that catches
contract drift before merge. Requires `jsonschema>=4.21` (see
requirements-dev.txt).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    from jsonschema import Draft202012Validator
    from jsonschema.exceptions import SchemaError
except ImportError as exc:  # pragma: no cover - import-time guard only
    sys.stderr.write(
        "error: jsonschema is required. Install it with:\n"
        "    pip install -r requirements-dev.txt\n"
    )
    raise SystemExit(2) from exc


ROOT = Path(__file__).resolve().parents[1]

# Per docs/contract.md "Versioning": current MAJOR + previous MAJOR. Until
# 1.0 ships, the only supported MAJOR is 0.1. When 1.0 lands, this set
# becomes {"0.1", "1.0"}; when 2.0 lands, {"1.0", "2.0"} (0.1 deprecated).
SUPPORTED_SCHEMA_VERSIONS = {"0.1"}


def load_json(path: Path) -> object:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def validate_schema_self(schema: dict, label: str) -> None:
    """Confirm the schema document itself is a valid Draft 2020-12 schema."""
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        raise SystemExit(f"{label}: schema is invalid Draft 2020-12 ({exc.message})")


def validate_against(instance: object, schema: dict, label: str) -> None:
    """Validate one JSON document against its schema; raise SystemExit with the
    JSON Pointer to the failing field on first violation."""
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.absolute_path))
    if not errors:
        return
    err = errors[0]
    pointer = "/" + "/".join(str(p) for p in err.absolute_path) if err.absolute_path else ""
    raise SystemExit(
        f"{label}: validation failed at {pointer or '(root)'}: {err.message}"
    )


def schema_dir_for(version: str) -> Path:
    return ROOT / "schemas" / version


def main() -> int:
    # v0 ships archived per-major schemas under schemas/<major>/.
    # See docs/contract.md "Versioning" section.

    index_path = ROOT / "catalog" / "index.json"
    if not index_path.exists():
        raise SystemExit("error: catalog/index.json not found")
    index = load_json(index_path)
    if not isinstance(index, dict):
        raise SystemExit(f"{index_path.relative_to(ROOT)}: must be an object")

    plugins_root = ROOT / "plugins"
    if not plugins_root.is_dir():
        raise SystemExit("plugins/ directory missing")

    schema_cache: dict[str, dict] = {}
    plugin_count = 0
    for plugin_dir in sorted(plugins_root.iterdir()):
        manifest_path = plugin_dir / "ouroboros.plugin.json"
        if not manifest_path.is_file():
            continue
        manifest = load_json(manifest_path)
        if not isinstance(manifest, dict):
            raise SystemExit(f"{manifest_path.relative_to(ROOT)}: must be an object")

        declared_version = manifest.get("schema_version")
        if not isinstance(declared_version, str):
            raise SystemExit(
                f"{manifest_path.relative_to(ROOT)}: schema_version must be a string"
            )
        if declared_version not in SUPPORTED_SCHEMA_VERSIONS:
            supported = sorted(SUPPORTED_SCHEMA_VERSIONS)
            raise SystemExit(
                f"error: schema_version {declared_version!r} is not supported. "
                f"Current support window: {supported}. "
                "Upgrade plugin or pin to a supported core version."
            )

        if declared_version not in schema_cache:
            schemas = schema_dir_for(declared_version)
            plugin_schema = load_json(schemas / "plugin.schema.json")
            audit_schema = load_json(schemas / "audit-event.schema.json")
            if not isinstance(plugin_schema, dict):
                raise SystemExit(f"schemas/{declared_version}/plugin.schema.json: must be an object")
            if not isinstance(audit_schema, dict):
                raise SystemExit(f"schemas/{declared_version}/audit-event.schema.json: must be an object")
            validate_schema_self(plugin_schema, f"schemas/{declared_version}/plugin.schema.json")
            validate_schema_self(audit_schema, f"schemas/{declared_version}/audit-event.schema.json")
            schema_cache[declared_version] = plugin_schema

        validate_against(manifest, schema_cache[declared_version], str(manifest_path.relative_to(ROOT)))
        plugin_count += 1

    if plugin_count == 0:
        raise SystemExit("no plugin manifests found under plugins/")

    print(f"contract validation passed ({plugin_count} plugin manifest(s) validated)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
