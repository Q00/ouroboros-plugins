from __future__ import annotations

from pathlib import Path
from typing import Any

RESTRICTED_SKILLS = {"docx", "pdf", "pptx", "xlsx"}


def classify(skill_name: str, source_path: Path | None = None) -> dict[str, Any]:
    if skill_name in RESTRICTED_SKILLS:
        return {
            "license_classification": "source-available",
            "assimilation_mode": "adapter-only",
            "can_vendor": False,
            "requires_maintainer_approval": True,
            "message": "Restricted/source-available upstream materials must not be vendored without explicit maintainer approval.",
        }
    return {
        "license_classification": "apache-2.0",
        "assimilation_mode": "reference-adapter",
        "can_vendor": True,
        "requires_maintainer_approval": False,
        "message": "Open-source reference adapter may catalog metadata; runtime execution still requires bounded trust checks.",
    }
