from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from .upstream import UPSTREAM_COMMIT, UPSTREAM_LICENSE, UPSTREAM_REPO, UPSTREAM_VERSION

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
VENDOR_ROOT = PLUGIN_ROOT / "vendor" / "superpowers"
SKILLS_ROOT = VENDOR_ROOT / "skills"

READ_ONLY_SKILLS: set[str] = set()
DESTRUCTIVE_DESCRIBED_SKILLS = {"finishing-a-development-branch"}

CAPABILITIES_BY_SKILL: dict[str, list[dict[str, str]]] = {
    "using-superpowers": [
        {"name": "provenance", "access": "write", "reason": "Record inspected upstream skill guidance."},
        {"name": "progress", "access": "write", "reason": "Report methodology guidance readiness."},
    ],
    "requesting-code-review": [
        {"name": "ledger", "access": "write", "reason": "Record review scope, findings, and evidence."},
        {"name": "provenance", "access": "write", "reason": "Record upstream review-skill source."},
        {"name": "handoff", "access": "attach", "reason": "Attach review report for downstream remediation."},
    ],
    "verification-before-completion": [
        {"name": "ledger", "access": "write", "reason": "Record verification commands and outcomes."},
        {"name": "provenance", "access": "write", "reason": "Record upstream verification-skill source."},
        {"name": "handoff", "access": "attach", "reason": "Attach completion-gate evidence."},
    ],
}
DEFAULT_CAPABILITIES = [
    {"name": "seed", "access": "write", "reason": "Prepare Seed-compatible handoff artifacts."},
    {"name": "ledger", "access": "write", "reason": "Record workflow decisions, constraints, and evidence."},
    {"name": "state", "access": "write", "reason": "Persist resumable command state under .omx/superpowers/."},
    {"name": "provenance", "access": "write", "reason": "Record upstream Superpowers source and command mapping."},
    {"name": "runtime", "access": "execute", "reason": "Describe safe Ouroboros runtime continuation stages."},
    {"name": "handoff", "access": "attach", "reason": "Attach prepared handoffs to Ouroboros execution."},
    {"name": "progress", "access": "write", "reason": "Report resumable command progress."},
]


def _permissions_for(skill: str) -> list[dict[str, object]]:
    perms: list[dict[str, object]] = [
        {
            "scope": "filesystem:read",
            "risk": "read_only",
            "required": True,
            "reason": "Read vendored upstream Superpowers skill files and local user-supplied inputs.",
        }
    ]
    if skill not in READ_ONLY_SKILLS:
        perms.append(
            {
                "scope": "filesystem:write",
                "risk": "write",
                "required": True,
                "reason": "Write .omx/superpowers handoff, state, provenance, and evidence artifacts.",
            }
        )
    if skill in {"dispatching-parallel-agents", "subagent-driven-development", "executing-plans"}:
        perms.append(
            {
                "scope": "shell:execute",
                "risk": "write",
                "required": False,
                "reason": "Future controlled execution may launch bounded Ouroboros runtime or team stages; v0 handoff generation does not execute them.",
            }
        )
    if skill in DESTRUCTIVE_DESCRIBED_SKILLS:
        perms.append(
            {
                "scope": "shell:execute",
                "risk": "destructive",
                "required": False,
                "reason": "The upstream workflow describes merge/push/discard choices, but v0 only reports options and does not perform destructive actions.",
            }
        )
    return perms


def _risk_for(skill: str) -> str:
    # All skill commands prepare auditable .omx artifacts in v0, so the
    # command risk is write even when the underlying methodology is review or
    # guidance oriented. Pure inspection remains available through `inspect`.
    return "write"


def _capabilities_for(skill: str) -> list[dict[str, str]]:
    return CAPABILITIES_BY_SKILL.get(skill, DEFAULT_CAPABILITIES)


def parse_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---", 4)
    if end == -1:
        return {}
    data: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip().strip('"').strip("'")
    return data


@dataclass(frozen=True)
class SkillRecord:
    name: str
    description: str
    command: str
    risk: str
    destructive_actions_excluded: bool
    capabilities: list[dict[str, str]]
    permissions: list[dict[str, object]]
    upstream_repo: str
    upstream_version: str
    upstream_commit: str
    upstream_license: str
    skill_path: str

    def to_json(self) -> dict[str, object]:
        return asdict(self)


def discover_skills() -> list[SkillRecord]:
    records: list[SkillRecord] = []
    for skill_md in sorted(SKILLS_ROOT.glob("*/SKILL.md")):
        text = skill_md.read_text(encoding="utf-8")
        fm = parse_frontmatter(text)
        name = fm.get("name", skill_md.parent.name)
        records.append(
            SkillRecord(
                name=name,
                description=fm.get("description", ""),
                command=f"superpowers {name}",
                risk=_risk_for(name),
                destructive_actions_excluded=name in DESTRUCTIVE_DESCRIBED_SKILLS,
                capabilities=_capabilities_for(name),
                permissions=_permissions_for(name),
                upstream_repo=UPSTREAM_REPO,
                upstream_version=UPSTREAM_VERSION,
                upstream_commit=UPSTREAM_COMMIT,
                upstream_license=UPSTREAM_LICENSE,
                skill_path=str(skill_md.relative_to(PLUGIN_ROOT)),
            )
        )
    return records


def get_skill(name: str) -> SkillRecord:
    for skill in discover_skills():
        if skill.name == name:
            return skill
    available = ", ".join(s.name for s in discover_skills())
    raise KeyError(f"unknown Superpowers skill {name!r}; available: {available}")


def write_index(path: Path) -> Path:
    skills = [skill.to_json() for skill in discover_skills()]
    payload = {
        "upstream": {
            "repo": UPSTREAM_REPO,
            "version": UPSTREAM_VERSION,
            "commit": UPSTREAM_COMMIT,
            "license": UPSTREAM_LICENSE,
        },
        "skills": skills,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
