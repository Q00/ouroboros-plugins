#!/usr/bin/env python3
"""Generate the Scientific Agent Skills AgentOS adapter registry and manifest.

The generator intentionally records metadata only. It does not vendor or execute
upstream skill scripts, preserving the plugin firewall boundary described in
Q00/ouroboros-plugins#35.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_DIR = ROOT / "plugins" / "scientific-agent-skills-adapter"
PACKAGE_DIR = PLUGIN_DIR / "scientific_agent_skills_adapter"
REGISTRY_PATH = PACKAGE_DIR / "registry.generated.json"
MANIFEST_PATH = PLUGIN_DIR / "ouroboros.plugin.json"
UPSTREAM_REPOSITORY = "https://github.com/K-Dense-AI/scientific-agent-skills"

READ_ONLY_KEYWORDS = {
    "lookup",
    "search",
    "read",
    "analyze",
    "analysis",
    "visualization",
    "plot",
    "inspect",
    "parse",
    "evaluate",
}
WRITE_KEYWORDS = {
    "write",
    "create",
    "generate",
    "edit",
    "draft",
    "report",
    "notebook",
    "image",
    "slides",
    "poster",
    "document",
    "protocol",
    "submit",
    "api",
}
DESTRUCTIVE_KEYWORDS = {
    "clinical",
    "treatment",
    "patient",
    "diagnostic",
    "lab automation",
    "robot",
    "opentrons",
    "pylabrobot",
    "cloud lab",
    "ginkgo",
    "benchling",
    "dnanexus",
    "modal",
    "adaptyv",
    "delete",
    "transfer",
    "inventory",
    "submission",
}
NETWORK_KEYWORDS = {
    "api",
    "database",
    "pubmed",
    "ncbi",
    "web",
    "search",
    "cloud",
    "server",
    "download",
    "upload",
    "zotero",
    "benchling",
    "dnanexus",
    "modal",
    "rowan",
    "exa",
    "parallel",
    "perplexity",
}
CREDENTIAL_KEYWORDS = {
    "api key",
    "token",
    "credential",
    "account",
    "secret",
    "oauth",
}
SERVICE_SCOPES = {
    "benchling": "benchling:write",
    "dnanexus": "dnanexus:write",
    "modal": "modal:execute",
    "opentrons": "opentrons:execute",
    "pylabrobot": "lab-robot:execute",
    "ginkgo": "cloud-lab:execute",
    "zotero": "zotero:write",
    "github": "github:read",
}


@dataclass(frozen=True)
class FrontMatter:
    fields: dict[str, object]
    body: str


def parse_frontmatter(text: str) -> FrontMatter:
    if not text.startswith("---\n"):
        return FrontMatter({}, text)
    end = text.find("\n---", 4)
    if end == -1:
        return FrontMatter({}, text)
    raw = text[4:end].splitlines()
    body = text[text.find("\n", end + 1) + 1 :]
    fields: dict[str, object] = {}
    current_parent: str | None = None
    for line in raw:
        if not line.strip():
            continue
        if line.startswith((" ", "\t")) and current_parent:
            key, sep, value = line.strip().partition(":")
            if sep:
                parent = fields.setdefault(current_parent, {})
                if isinstance(parent, dict):
                    parent[key.strip()] = value.strip()
            continue
        key, sep, value = line.partition(":")
        if not sep:
            continue
        key = key.strip()
        value = value.strip()
        current_parent = key
        if value == "":
            fields[key] = {}
        else:
            fields[key] = value
    return FrontMatter(fields, body)


def git_commit(path: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(path), "rev-parse", "HEAD"], text=True
        ).strip()
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        raise SystemExit(f"{path} must be a git checkout with a readable HEAD") from exc


def count_child_dir(skill_dir: Path, name: str) -> int:
    child = skill_dir / name
    if not child.is_dir():
        return 0
    return sum(1 for p in child.rglob("*") if p.is_file())


def sha256_tree(skill_dir: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(p for p in skill_dir.rglob("*") if p.is_file()):
        rel = path.relative_to(skill_dir).as_posix()
        digest.update(rel.encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def normalize_allowed_tools(value: object) -> list[str]:
    if isinstance(value, str):
        return [part.strip() for part in re.split(r"[, ]+", value) if part.strip()]
    if isinstance(value, list):
        return [str(part).strip() for part in value if str(part).strip()]
    return []


def infer_domain(slug: str, text: str) -> str:
    hay = f"{slug} {text}".lower()
    checks = [
        ("clinical", ["clinical", "patient", "treatment", "diagnostic", "healthcare"]),
        ("lab-automation", ["opentrons", "pylabrobot", "benchling", "cloud lab", "protocol"]),
        ("bioinformatics", ["genomic", "rna", "gene", "protein", "bio", "single-cell", "sequence"]),
        ("chemistry", ["molecule", "drug", "chem", "rdkit", "smiles", "docking"]),
        ("documents", ["pdf", "docx", "pptx", "xlsx", "latex", "slides", "writing"]),
        ("ml-ai", ["machine learning", "deep learning", "pytorch", "transformers", "model"]),
        ("data", ["dataframe", "statistics", "visualization", "analysis", "plot"]),
        ("cloud-web", ["api", "web", "database", "cloud", "search"]),
        ("physics", ["quantum", "astronomy", "astropy", "fluid", "simulation"]),
    ]
    for domain, words in checks:
        if any(word in hay for word in words):
            return domain
    return "scientific-general"


def infer_permissions(slug: str, text: str, allowed_tools: list[str], counts: dict[str, int]) -> list[dict[str, object]]:
    hay = f"{slug} {text}".lower()
    scopes: dict[str, tuple[str, bool, str]] = {
        "filesystem:read": ("read_only", True, "Read upstream SKILL.md metadata and local user inputs for inspection/preparation."),
        "filesystem:write": ("write", False, "Write Seed-compatible handoff, provenance, audit, and result artifacts."),
    }
    if counts.get("scripts", 0) or any(tool.lower() == "bash" for tool in allowed_tools):
        scopes["shell:execute"] = ("destructive", False, "Upstream skill includes scripts or Bash authority; execution is blocked until explicitly trusted.")
    if any(tool.lower() in {"write", "edit"} for tool in allowed_tools):
        scopes["filesystem:write"] = ("write", False, "Upstream instructions include file writing/editing authority; prepare writes handoff artifacts only.")
    if any(word in hay for word in NETWORK_KEYWORDS):
        scopes["network:read"] = ("read_only", False, "Skill may query public scientific databases, papers, documentation, or APIs.")
    if any(word in hay for word in ("submit", "upload", "mutate", "delete", "transfer", "write api")):
        scopes["network:write"] = ("destructive", False, "Skill may submit jobs, mutate remote platforms, or call paid/credentialed APIs.")
    for key, scope in SERVICE_SCOPES.items():
        if key in hay:
            scopes[scope] = ("destructive" if scope.endswith((":write", ":execute")) else "read_only", False, f"Service-specific authority inferred from {key} references.")
    return [
        {"scope": scope, "risk": risk, "required": required, "reason": reason}
        for scope, (risk, required, reason) in sorted(scopes.items())
    ]


def infer_risk(slug: str, text: str, allowed_tools: list[str], permissions: list[dict[str, object]], counts: dict[str, int]) -> str:
    hay = f"{slug} {text}".lower()
    if any(word in hay for word in DESTRUCTIVE_KEYWORDS):
        return "destructive"
    if any(p["risk"] == "destructive" for p in permissions):
        return "destructive"
    if counts.get("scripts", 0) or any(tool.lower() in {"bash", "edit", "write"} for tool in allowed_tools):
        return "write"
    if any(word in hay for word in WRITE_KEYWORDS):
        return "write"
    if any(word in hay for word in READ_ONLY_KEYWORDS):
        return "read_only"
    return "write"


def summarize_security(risk: str, allowed_tools: list[str], permissions: list[dict[str, object]], text: str) -> dict[str, object]:
    hay = text.lower()
    flags: list[str] = []
    if allowed_tools:
        flags.append("declares_allowed_tools")
    if any(tool.lower() == "bash" for tool in allowed_tools):
        flags.append("allows_bash")
    if "api key" in hay or "token" in hay or "credential" in hay:
        flags.append("mentions_credentials")
    if any(p["risk"] == "destructive" for p in permissions):
        flags.append("destructive_permission_candidate")
    execution_default = "blocked" if risk in {"write", "destructive"} or flags else "dry_run_only"
    if risk == "read_only" and not flags:
        execution_default = "prepare_only"
    return {
        "risk": risk,
        "flags": flags,
        "execution_default": execution_default,
        "requires_manual_review": risk == "destructive" or bool(flags),
    }


def build_registry(upstream: Path) -> dict[str, object]:
    skills_root = upstream / "scientific-skills"
    if not skills_root.is_dir():
        raise SystemExit(f"{skills_root} not found")
    commit = git_commit(upstream)
    skills: list[dict[str, object]] = []
    for skill_dir in sorted(p for p in skills_root.iterdir() if (p / "SKILL.md").is_file()):
        skill_md = skill_dir / "SKILL.md"
        text = skill_md.read_text(encoding="utf-8", errors="replace")
        fm = parse_frontmatter(text)
        slug = str(fm.fields.get("name") or skill_dir.name).strip()
        description = str(fm.fields.get("description") or "").strip()
        license_value = str(fm.fields.get("license") or "Unknown").strip()
        allowed_tools = normalize_allowed_tools(fm.fields.get("allowed-tools"))
        counts = {
            "references": count_child_dir(skill_dir, "references"),
            "scripts": count_child_dir(skill_dir, "scripts"),
            "assets": count_child_dir(skill_dir, "assets"),
        }
        permissions = infer_permissions(slug, text, allowed_tools, counts)
        risk = infer_risk(slug, text, allowed_tools, permissions, counts)
        security = summarize_security(risk, allowed_tools, permissions, text)
        skills.append(
            {
                "slug": slug,
                "name": slug,
                "description": description,
                "domain": infer_domain(slug, f"{description}\n{fm.body[:4000]}"),
                "license": license_value,
                "allowed_tools": allowed_tools,
                "package": counts,
                "permissions": permissions,
                "risk": risk,
                "security": security,
                "provenance": {
                    "repository": UPSTREAM_REPOSITORY,
                    "commit": commit,
                    "skill_path": f"scientific-skills/{skill_dir.name}/SKILL.md",
                    "source_hash": sha256_tree(skill_dir),
                },
            }
        )
    return {
        "schema_version": "scientific-agent-skills-registry/0.1",
        "generated_from": {
            "repository": UPSTREAM_REPOSITORY,
            "commit": commit,
            "skill_count": len(skills),
        },
        "skills": skills,
    }


def command(name: str, summary: str, usage: str, risk: str, args: list[dict[str, object]] | None = None, confirm: bool = False) -> dict[str, object]:
    out = {
        "namespace": "scientific",
        "name": name,
        "summary": summary,
        "usage": usage,
        "risk": risk,
        "requires_confirmation": confirm,
    }
    if args:
        out["arguments"] = args
    return out


def build_manifest(registry: dict[str, object]) -> dict[str, object]:
    skill_arg = {"name": "skill", "type": "string", "required": True, "description": "Scientific Agent Skill slug."}
    task_arg = {"name": "task", "type": "string", "required": True, "description": "Scientific task or user goal."}
    optional_task_arg = {"name": "task", "type": "string", "required": False, "description": "Optional task context."}
    commands = [
        command("list", "List assimilated Scientific Agent Skills with optional domain/risk filters.", "ooo scientific list [--domain <domain>] [--risk <risk>]", "read_only"),
        command("inspect", "Inspect a scientific skill's metadata, permissions, provenance, and risk.", "ooo scientific inspect <skill>", "read_only", [skill_arg]),
        command("explain", "Explain how a scientific skill maps into AgentOS handoff semantics.", "ooo scientific explain <skill> [--task <goal>]", "read_only", [skill_arg, optional_task_arg]),
        command("prepare", "Write a Seed-compatible handoff plan for a scientific skill without executing upstream code.", "ooo scientific prepare <skill> --task <goal> [--output <path>]", "write", [skill_arg, task_arg, {"name": "output", "type": "path", "required": False, "description": "Output directory for handoff artifacts."}]),
        command("run", "Run a skill only through dry-run or approved low-risk boundaries; otherwise block with an audit artifact.", "ooo scientific run <skill> --task <goal> [--dry-run]", "destructive", [skill_arg, task_arg, {"name": "dry_run", "type": "boolean", "required": False, "description": "Generate handoff and audit artifacts without executing upstream scripts."}], True),
        command("trust-report", "Emit the generated trust report for a scientific skill.", "ooo scientific trust-report <skill>", "read_only", [skill_arg]),
        command("doctor", "Check adapter registry integrity and safety defaults.", "ooo scientific doctor", "read_only"),
    ]
    for skill in registry["skills"]:  # type: ignore[index]
        slug = skill["slug"]  # type: ignore[index]
        risk = skill["risk"]  # type: ignore[index]
        commands.append(command(str(slug), f"Prepare or dry-run the {slug} scientific capability via AgentOS boundaries.", f"ooo scientific {slug} --task <goal> [--dry-run]", "write" if risk == "read_only" else str(risk), [task_arg], risk == "destructive"))
    return {
        "schema_version": "0.1",
        "name": "scientific-agent-skills-adapter",
        "version": "0.1.0",
        "description": "Reference adapter proving safe AgentOS assimilation of K-Dense Scientific Agent Skills.",
        "source": {"type": "local_path", "path": "plugins/scientific-agent-skills-adapter", "repository": UPSTREAM_REPOSITORY},
        "commands": commands,
        "capabilities": [
            {"name": "seed", "access": "write", "reason": "Generate Seed-compatible handoff plans from scientific skill metadata."},
            {"name": "ledger", "access": "write", "reason": "Record risk classifications, decisions, audit events, and outcomes."},
            {"name": "state", "access": "write", "reason": "Persist selected skill, task, input/output paths, and resume state."},
            {"name": "provenance", "access": "write", "reason": "Record upstream repository, commit, skill path, and source hash."},
            {"name": "handoff", "access": "attach", "reason": "Attach generated plans, dry-run reports, and blocked-execution artifacts."},
            {"name": "progress", "access": "write", "reason": "Report long-running workflow plan states without hiding state in terminal output."},
            {"name": "runtime", "access": "execute", "reason": "Reserved for future manually trusted low-risk execution paths; default runner blocks unsafe execution."},
            {"name": "mcp", "access": "execute", "reason": "Reserved for skills that explicitly require MCP-backed scientific services; v0.1 uses execute as the closest supported access value."},
        ],
        "permissions": [
            {"scope": "filesystem:read", "risk": "read_only", "required": True, "reason": "Read vendored/generated skill metadata, references, and user input paths."},
            {"scope": "filesystem:write", "risk": "write", "required": True, "reason": "Write generated handoff, provenance, audit, and dry-run artifacts."},
            {"scope": "network:read", "risk": "read_only", "required": False, "reason": "Optional public scientific database/paper/API lookup after per-skill trust."},
            {"scope": "network:write", "risk": "destructive", "required": False, "reason": "Optional remote job submission or mutation only after explicit trust and confirmation."},
            {"scope": "shell:execute", "risk": "destructive", "required": False, "reason": "Optional upstream script execution; blocked by default until explicitly reviewed."},
            {"scope": "benchling:write", "risk": "destructive", "required": False, "reason": "Service-specific lab data mutations require explicit trust."},
            {"scope": "dnanexus:write", "risk": "destructive", "required": False, "reason": "Cloud genomics platform mutations require explicit trust."},
            {"scope": "modal:execute", "risk": "destructive", "required": False, "reason": "Cloud compute execution requires explicit trust."},
            {"scope": "opentrons:execute", "risk": "destructive", "required": False, "reason": "Physical lab automation execution requires explicit trust."},
            {"scope": "zotero:write", "risk": "destructive", "required": False, "reason": "Reference library mutations require explicit trust."},
        ],
        "entrypoint": {"type": "command", "command": "python -m scientific_agent_skills_adapter"},
        "audit": {"events": ["plugin.invoked", "plugin.permission_used", "plugin.completed", "plugin.failed"]},
    }


def dump_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("upstream", type=Path, help="Path to K-Dense-AI/scientific-agent-skills checkout")
    parser.add_argument("--check", action="store_true", help="Fail if generated files differ")
    args = parser.parse_args(argv)
    registry = build_registry(args.upstream.resolve())
    manifest = build_manifest(registry)
    if args.check:
        expected_registry = json.dumps(registry, indent=2, sort_keys=True) + "\n"
        expected_manifest = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
        mismatches = []
        if REGISTRY_PATH.read_text(encoding="utf-8") != expected_registry:
            mismatches.append(str(REGISTRY_PATH.relative_to(ROOT)))
        if MANIFEST_PATH.read_text(encoding="utf-8") != expected_manifest:
            mismatches.append(str(MANIFEST_PATH.relative_to(ROOT)))
        if mismatches:
            raise SystemExit("generated files drifted: " + ", ".join(mismatches))
        return 0
    dump_json(REGISTRY_PATH, registry)
    dump_json(MANIFEST_PATH, manifest)
    print(f"generated {len(registry['skills'])} scientific skill entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
