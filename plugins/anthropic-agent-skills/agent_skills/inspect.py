from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

RESOURCE_DIRS = ("scripts", "references", "assets")


def _frontmatter(text: str) -> dict[str, str]:
    match = re.match(r"---\n(.*?)\n---\n?", text, re.S)
    if not match:
        return {}
    result: dict[str, str] = {}
    for raw in match.group(1).splitlines():
        if ":" not in raw:
            continue
        key, value = raw.split(":", 1)
        result[key.strip()] = value.strip().strip('"').strip("'")
    return result


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def inspect_skill(skill_dir: Path) -> dict[str, Any]:
    skill_dir = skill_dir.resolve()
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        raise ValueError(f"{skill_dir} is not an Agent Skill directory: missing SKILL.md")
    text = skill_md.read_text(encoding="utf-8")
    fm = _frontmatter(text)
    resources: dict[str, list[dict[str, Any]]] = {}
    for dirname in RESOURCE_DIRS:
        base = skill_dir / dirname
        items: list[dict[str, Any]] = []
        if base.is_dir():
            for path in sorted(p for p in base.rglob("*") if p.is_file()):
                rel = path.relative_to(skill_dir).as_posix()
                items.append({"path": rel, "bytes": path.stat().st_size, "sha256": _sha256(path)})
        resources[dirname] = items
    return {
        "format": "agent-skill.inspect.v1",
        "path": str(skill_dir),
        "name": fm.get("name") or skill_dir.name,
        "description": fm.get("description", ""),
        "skill_md": {"path": "SKILL.md", "bytes": skill_md.stat().st_size, "sha256": _sha256(skill_md)},
        "resources": resources,
        "progressive_disclosure": {
            "metadata_loaded": True,
            "skill_md_loaded_for_inspection": True,
            "scripts_references_assets_loaded": False,
            "resource_inventory_only": True,
        },
    }


def catalog_path(repo_or_path: Path) -> dict[str, Any]:
    root = repo_or_path.resolve()
    candidates = []
    skills_root = root / "skills"
    if skills_root.is_dir():
        candidates.extend(sorted(p for p in skills_root.iterdir() if (p / "SKILL.md").is_file()))
    if (root / "SKILL.md").is_file():
        candidates.append(root)
    if not candidates:
        candidates.extend(sorted(p.parent for p in root.rglob("SKILL.md")))
    return {
        "format": "agent-skills.catalog-inspection.v1",
        "path": str(root),
        "skills": [inspect_skill(path) for path in candidates],
    }


def dumps(data: Any) -> str:
    return json.dumps(data, indent=2, sort_keys=True) + "\n"
