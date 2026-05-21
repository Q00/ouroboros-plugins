"""Command entrypoint for the Hermes skill assimilation plugin."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PLUGIN_NAME = "hermes-skill-assimilator"
PLUGIN_VERSION = "0.1.0"


@dataclass(frozen=True)
class SkillInspection:
    path: Path
    name: str
    description: str
    frontmatter: dict[str, Any]
    risk: str
    risk_categories: list[str]
    risk_reasons: list[str]
    permissions: list[str]
    referenced_files: list[str]
    setup_requirements: list[str]
    shell_snippets: list[str]
    environment_variables: list[str]
    external_urls: list[str]

    def to_dict(self, root: Path | None = None) -> dict[str, Any]:
        source_path = display_path(self.path, root) if root else str(self.path)
        return {
            "source_path": source_path,
            "name": self.name,
            "description": self.description,
            "frontmatter": self.frontmatter,
            "risk": self.risk,
            "risk_categories": self.risk_categories,
            "risk_reasons": self.risk_reasons,
            "permissions": self.permissions,
            "referenced_files": self.referenced_files,
            "setup_requirements": self.setup_requirements,
            "shell_snippets": self.shell_snippets,
            "environment_variables": self.environment_variables,
            "external_urls": self.external_urls,
        }


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def display_path(path: Path, root: Path | None) -> str:
    if root is None:
        return str(path)
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


def write_json_atomic(path: Path, payload: Any) -> None:
    write_text_atomic(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    if end == -1:
        return {}, text
    raw = text[4:end].strip()
    body = text[end + len("\n---") :].lstrip("\n")
    return parse_simple_yaml(raw), body


def parse_simple_yaml(raw: str) -> dict[str, Any]:
    data: dict[str, Any] = {}
    current_key: str | None = None
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("-") and current_key:
            data.setdefault(current_key, []).append(stripped[1:].strip().strip('"\''))
            continue
        if ":" in stripped:
            key, value = stripped.split(":", 1)
            key = key.strip()
            value = value.strip()
            current_key = key
            if not value:
                data[key] = []
            elif value.lower() in {"true", "false"}:
                data[key] = value.lower() == "true"
            else:
                data[key] = value.strip('"\'')
    return data


def find_skill_files(path: Path) -> list[Path]:
    resolved = path.expanduser().resolve()
    if resolved.is_file():
        return [resolved]
    if (resolved / "SKILL.md").is_file():
        return [resolved / "SKILL.md"]
    return sorted(p for p in resolved.rglob("SKILL.md") if p.is_file())


def find_plugin_yaml(path: Path) -> list[Path]:
    resolved = path.expanduser().resolve()
    if resolved.is_file() and resolved.name in {"plugin.yaml", "plugin.yml"}:
        return [resolved]
    if resolved.is_file():
        return []
    return sorted([*resolved.rglob("plugin.yaml"), *resolved.rglob("plugin.yml")])


def extract_shell_snippets(text: str) -> list[str]:
    snippets: list[str] = []
    for match in re.finditer(r"```(?:bash|sh|shell|zsh)\s*\n(.*?)```", text, re.DOTALL | re.IGNORECASE):
        snippets.append(match.group(1).strip())
    return snippets


def classify_skill(text: str, frontmatter: dict[str, Any]) -> tuple[str, list[str], list[str], list[str]]:
    haystack = "\n".join([text, json.dumps(frontmatter, sort_keys=True)]).lower()
    reasons: list[str] = []
    categories: set[str] = set()
    permissions: set[str] = {"filesystem:read"}
    risk_rank = 0

    def bump(rank: int, category: str, reason: str, *scopes: str) -> None:
        nonlocal risk_rank
        risk_rank = max(risk_rank, rank)
        categories.add(category)
        if reason not in reasons:
            reasons.append(reason)
        permissions.update(scopes)

    if re.search(r"```(?:bash|sh|shell|zsh)", text, re.IGNORECASE) or any(word in haystack for word in ["shell", "subprocess", "execute"]):
        bump(2, "shell_execution", "contains shell execution guidance", "shell:execute")
    if re.search(r"\b(write|create|modify|edit|save|output|--out)\b", haystack):
        bump(1, "filesystem_write", "may write filesystem artifacts", "filesystem:write")
    if re.search(r"https?://", text) or any(word in haystack for word in ["web", "http", "api", "curl"]):
        bump(1, "network_read", "contacts external network resources", "network:read")
    if re.search(r"\b(api[_-]?key|token|secret|credential|slack|discord|telegram|email)\b", haystack):
        bump(1, "credential_or_external_delivery", "may require credentials or external delivery trust", "network:write")
    if re.search(r"\b(delete|destroy|drop|production|prod)\b", haystack):
        bump(2, "destructive_or_production", "mentions destructive or production-affecting behavior", "shell:execute")

    risk = ["read_only", "write", "destructive"][risk_rank]
    return risk, sorted(categories) or ["read_only_guidance"], reasons or ["read-only guidance only"], sorted(permissions)


def inspect_skill(path: Path) -> SkillInspection:
    text = path.read_text(encoding="utf-8", errors="replace")
    frontmatter, body = parse_frontmatter(text)
    name = str(frontmatter.get("name") or path.parent.name)
    description = str(frontmatter.get("description") or "")
    shell_snippets = extract_shell_snippets(text)
    env = sorted(set(re.findall(r"\b[A-Z][A-Z0-9_]{2,}\b", text)))
    urls = sorted(set(re.findall(r"https?://[^\s)>'\"]+", text)))
    refs = sorted(set(re.findall(r"`([^`]+\.(?:md|py|json|yaml|yml|txt))`", text)))
    setup = []
    for line in body.splitlines():
        if re.search(r"\b(install|set |export |requires?|setup)\b", line, re.IGNORECASE):
            setup.append(line.strip().lstrip("- "))
    risk, categories, reasons, permissions = classify_skill(text, frontmatter)
    return SkillInspection(path, name, description, frontmatter, risk, categories, reasons, permissions, refs, setup, shell_snippets, env, urls)


def inspect_plugin_yaml(path: Path, root: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8", errors="replace")
    data = parse_simple_yaml(raw)
    return {
        "source_path": display_path(path, root),
        "metadata": data,
        "permissions": data.get("permissions", []),
        "risk": "write" if data.get("permissions") else "read_only",
        "risk_categories": ["external_plugin_entrypoint"] if "entrypoint" in data else [],
    }


def inspect_path(raw_path: str) -> dict[str, Any]:
    root = Path(raw_path).expanduser().resolve()
    skill_files = find_skill_files(root)
    plugin_files = find_plugin_yaml(root)
    skills = [inspect_skill(path) for path in skill_files]
    plugins = [inspect_plugin_yaml(path, root) for path in plugin_files]
    return {
        "plugin": PLUGIN_NAME,
        "version": PLUGIN_VERSION,
        "status": "ready" if skills or plugins else "no_hermes_artifacts_found",
        "source": {"path": str(root), "inspected_at": utc_now()},
        "summary": {"skill_count": len(skills), "plugin_manifest_count": len(plugins)},
        "skills": [skill.to_dict(root) for skill in skills],
        "plugin_manifests": plugins,
        "safety": {"executed_instructions": False, "notes": ["Inspection is static and never runs Hermes skill or plugin code."]},
    }


def render_report(payload: dict[str, Any]) -> str:
    lines = ["# Hermes skill assimilation report", "", f"Source: `{payload['source']['path']}`", "", "## Summary", ""]
    lines.append(f"- Skills inspected: {payload['summary']['skill_count']}")
    lines.append(f"- Plugin manifests inspected: {payload['summary']['plugin_manifest_count']}")
    lines.append("- Executed instructions: no")
    lines.append("")
    for skill in payload["skills"]:
        lines.extend([
            f"## Skill: {skill['name']}",
            "",
            f"- Path: `{skill['source_path']}`",
            f"- Risk: `{skill['risk']}`",
            f"- Permissions: {', '.join(skill['permissions']) or 'none'}",
            f"- Reasons: {'; '.join(skill['risk_reasons'])}",
            f"- Referenced files: {', '.join(skill['referenced_files']) or 'none'}",
            f"- Environment variables: {', '.join(skill['environment_variables']) or 'none'}",
            f"- External URLs: {', '.join(skill['external_urls']) or 'none'}",
            "",
        ])
    if payload["plugin_manifests"]:
        lines.extend(["## Hermes plugin metadata", ""])
        for item in payload["plugin_manifests"]:
            lines.append(f"- `{item['source_path']}` risk `{item['risk']}` permissions `{item['permissions']}`")
    return "\n".join(lines).rstrip() + "\n"


def capability_map(payload: dict[str, Any]) -> dict[str, Any]:
    permissions = sorted({perm for skill in payload["skills"] for perm in skill["permissions"]})
    return {
        "schema": "ouroboros.hermes_skill_capability_map.v1",
        "source": payload["source"],
        "executed_instructions": False,
        "permissions_detected": permissions,
        "skills": payload["skills"],
        "plugin_manifests": payload["plugin_manifests"],
    }


def command_catalog(args: argparse.Namespace) -> int:
    payload = inspect_path(args.path)
    report_path = Path(args.out).expanduser().resolve()
    map_path = report_path.with_name("hermes-skill-capability-map.json")
    write_text_atomic(report_path, render_report(payload))
    write_json_atomic(map_path, capability_map(payload))
    sys.stdout.write(json.dumps({"status": "written", "report_path": str(report_path), "capability_map_path": str(map_path)}, indent=2) + "\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hermes-skill-assimilator")
    sub = parser.add_subparsers(dest="command", required=True)
    inspect_parser = sub.add_parser("inspect")
    inspect_parser.add_argument("path")
    catalog_parser = sub.add_parser("catalog")
    catalog_parser.add_argument("path")
    catalog_parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    if args.command == "inspect":
        sys.stdout.write(json.dumps(inspect_path(args.path), indent=2, sort_keys=True) + "\n")
        return 0
    if args.command == "catalog":
        return command_catalog(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
