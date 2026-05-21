from __future__ import annotations

from typing import Any

from .catalog import load_catalog


def resolve(request: str, limit: int = 5) -> dict[str, Any]:
    needle = request.lower()
    candidates: list[dict[str, Any]] = []
    for skill in load_catalog().get("skills", []):
        score = 0
        name = skill["source_skill"]
        if name in needle:
            score += 10
        for alias in skill.get("trigger_aliases", []):
            if alias.lower() in needle:
                score += 5
        for command in skill.get("commands", []):
            if command["name"].replace("-", " ") in needle:
                score += 2
        if score:
            candidates.append({
                "skill": name,
                "score": score,
                "commands": [c["name"] for c in skill.get("commands", [])],
                "surfaces": [c["surface"] for c in skill.get("commands", [])],
                "license_classification": skill.get("license_classification"),
                "assimilation_mode": skill.get("assimilation_mode"),
                "firewall_required": True,
            })
    candidates.sort(key=lambda item: (-item["score"], item["skill"]))
    return {"format": "agent-skills.resolve.v1", "request": request, "candidates": candidates[:limit]}
