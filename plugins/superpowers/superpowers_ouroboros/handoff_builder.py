from __future__ import annotations

import hashlib
import json
import shlex
from datetime import datetime, timezone
from pathlib import Path

from .skill_index import PLUGIN_ROOT, SkillRecord
from .upstream import SOURCE_PLATFORM, UPSTREAM_COMMIT, UPSTREAM_LICENSE, UPSTREAM_REPO, UPSTREAM_VERSION


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _safe_run_id(skill: str, goal: str, user_input: str) -> str:
    digest = hashlib.sha256(f"{skill}\0{goal}\0{user_input}\0{_now()}".encode()).hexdigest()[:12]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}-{skill}-{digest}"


def build_handoff_markdown(skill: SkillRecord, *, goal: str, user_input: str, run_id: str) -> str:
    destructive_note = ""
    if skill.destructive_actions_excluded:
        destructive_note = "\n- Destructive upstream actions are report-only in v0: no merge, push, branch deletion, discard, or PR mutation may be performed by this command."
    capabilities = "\n".join(f"- `{c['name']}:{c['access']}` — {c.get('reason', '')}" for c in skill.capabilities)
    permissions = "\n".join(f"- `{p['scope']}` ({p['risk']}, required={p['required']}) — {p.get('reason', '')}" for p in skill.permissions)
    expected = _expected_artifacts(skill.name)
    verification = _verification_contract(skill.name)
    continuation = _continuation(skill.name)
    return f"""# Superpowers → Ouroboros handoff: `{skill.name}`

Run ID: `{run_id}`
Ouroboros command: `ooo superpowers {skill.name}`
Risk: `{skill.risk}`

## Purpose

{skill.description or 'Translate this upstream Superpowers skill into an Ouroboros-native handoff.'}

## User inputs

- Goal: {goal or '(not supplied)'}
- Input: {user_input or '(not supplied)'}

## Upstream provenance

- Repository: {UPSTREAM_REPO}
- Version: {UPSTREAM_VERSION}
- Commit: `{UPSTREAM_COMMIT}`
- License: {UPSTREAM_LICENSE}
- Vendored skill path: `{skill.skill_path}`

## Required Ouroboros capabilities

{capabilities}

## External permissions

{permissions}
{destructive_note}

## Expected artifacts

{expected}

## Seed-compatible execution handoff

This artifact is a Seed-preparation handoff. A downstream Ouroboros runner should:

1. Load the upstream skill intent from the vendored `SKILL.md` path above.
2. Preserve the v0 risk boundary and permission plan before any execution.
3. Convert the goal/input into the command-specific artifact listed above.
4. Record fresh evidence before claiming completion.
5. Attach this run's `invocation.json`, `provenance.json`, `evidence.json`, and `audit.jsonl` to the ledger or handoff bundle.

## Verification evidence contract

{verification}

## Continuation instructions

{continuation}

## Upstream skill excerpt

The full vendored skill remains the source of methodology truth at `{skill.skill_path}`. Do not inject it into core runtime without plugin manifest, trust, permission, and audit checks.
"""


def _expected_artifacts(skill_name: str) -> str:
    mapping = {
        "brainstorming": "- Design/spec handoff describing clarified intent, constraints, options, and approval gate.",
        "writing-plans": "- Implementation-plan or Seed-candidate handoff with file scopes, tests, and checkpoints.",
        "executing-plans": "- Resumable execution state with completed tasks, blockers, and verification checkpoints.",
        "subagent-driven-development": "- Bounded task fanout plan with ownership, review stages, and integration evidence.",
        "dispatching-parallel-agents": "- Parallel task dispatch plan with isolated contexts and audit of task fanout.",
        "test-driven-development": "- RED/GREEN/REFACTOR checklist, failing-test evidence, passing-test evidence, and refactor notes.",
        "systematic-debugging": "- Root-cause investigation log with hypotheses, observations, fix, and regression verification.",
        "requesting-code-review": "- Code review report with scope, findings, severity, and required follow-up.",
        "receiving-code-review": "- Review-response worklist distinguishing accepted, rejected, and clarified feedback.",
        "verification-before-completion": "- Completion gate report with commands run, raw outcomes, and residual risks.",
        "finishing-a-development-branch": "- Non-destructive branch completion report with merge/PR/cleanup options only.",
        "using-git-worktrees": "- Workspace isolation report and proposed safe worktree commands or verified existing isolation.",
        "writing-skills": "- Skill authoring plan, documentation-TDD checks, and validation evidence.",
        "using-superpowers": "- Inspectable methodology guidance and skill-loading discipline mapped to Ouroboros commands.",
    }
    return mapping.get(skill_name, "- Command-specific handoff, state, provenance, and evidence artifacts.")


def _verification_contract(skill_name: str) -> str:
    if skill_name == "test-driven-development":
        return "- Include failing-test output captured before implementation and passing-test output after implementation."
    if skill_name == "systematic-debugging":
        return "- Include root-cause evidence, the minimal fix, and regression test output."
    if skill_name == "finishing-a-development-branch":
        return "- Include fresh test/status evidence and prove destructive actions were not executed by v0."
    if skill_name == "verification-before-completion":
        return "- Include exact verification commands, exit codes, and a claim-to-evidence matrix."
    return "- Include command-specific completion evidence and any downstream verification commands before success claims."


def _continuation(skill_name: str) -> str:
    if skill_name in {"subagent-driven-development", "dispatching-parallel-agents"}:
        return "Use Ouroboros team/native subagent surfaces only after task ownership, shared-file conflict rules, and review gates are declared."
    if skill_name == "finishing-a-development-branch":
        return "Present merge/PR/cleanup choices to a trusted harness; require a future destructive command declaration before executing destructive paths."
    if skill_name in {"brainstorming", "writing-plans"}:
        return "Feed the produced spec/plan into `ooo auto`, `$ralph`, or `$team` only after explicit approval and scope locking."
    return "Continue through the normal Ouroboros Seed, ledger, state, provenance, and verification surfaces."


def prepare_handoff(skill: SkillRecord, *, goal: str, user_input: str, output_root: Path, invoked_by: str = "direct") -> dict[str, object]:
    run_id = _safe_run_id(skill.name, goal, user_input)
    run_dir = output_root / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    argument_summary = {
        "goal_supplied": bool(goal),
        "goal_sha256": hashlib.sha256(goal.encode()).hexdigest() if goal else None,
        "goal_length": len(goal),
        "input_supplied": bool(user_input),
        "input_sha256": hashlib.sha256(user_input.encode()).hexdigest() if user_input else None,
        "input_length": len(user_input),
    }
    used_permissions = [
        p for p in skill.permissions
        if p["scope"] in {"filesystem:read", "filesystem:write"}
    ]
    invocation = {
        "run_id": run_id,
        "status": "prepared",
        "invoked_at": _now(),
        "invoked_by": invoked_by,
        "upstream_skill": skill.name,
        "ouroboros_command": f"superpowers {skill.name}",
        "risk": skill.risk,
        "arguments": argument_summary,
        "capabilities": skill.capabilities,
        "planned_permissions": skill.permissions,
        "used_permissions": used_permissions,
    }
    provenance = {
        "upstream_repo": UPSTREAM_REPO,
        "upstream_version": UPSTREAM_VERSION,
        "upstream_commit": UPSTREAM_COMMIT,
        "upstream_license": UPSTREAM_LICENSE,
        "upstream_skill": skill.name,
        "ouroboros_command": f"superpowers {skill.name}",
        "artifact_path": str((run_dir / "handoff.md").as_posix()),
        "invoked_by": invoked_by,
        "source_platform": SOURCE_PLATFORM,
    }
    evidence = {
        "run_id": run_id,
        "status": "prepared",
        "completion_state": "blocked_until_downstream_execution",
        "evidence": [
            "validated skill exists in pinned upstream snapshot",
            "prepared invocation/provenance/handoff/seed-preparation artifacts",
            "destructive actions excluded from v0 command execution",
        ],
        "next_step": _continuation(skill.name),
    }
    audit_events = [
        {
            "event": "plugin.invoked",
            "at": invocation["invoked_at"],
            "run_id": run_id,
            "skill": skill.name,
            "arguments": argument_summary,
        },
        {
            "event": "plugin.permission_used",
            "at": invocation["invoked_at"],
            "run_id": run_id,
            "permissions": used_permissions,
        },
        {"event": "plugin.completed", "at": _now(), "run_id": run_id, "artifact": str((run_dir / "handoff.md").as_posix())},
    ]
    handoff = build_handoff_markdown(skill, goal=goal, user_input=user_input, run_id=run_id)
    seed = f"""# Seed preparation: Superpowers `{skill.name}`

Goal: {goal or '(not supplied)'}

Use `{run_dir / 'handoff.md'}` as the bounded handoff. This is not raw prompt injection; it is a plugin-governed, permissioned, auditable translation of upstream Superpowers `{skill.name}`.
"""

    files = {
        "invocation_path": run_dir / "invocation.json",
        "provenance_path": run_dir / "provenance.json",
        "handoff_path": run_dir / "handoff.md",
        "seed_path": run_dir / "seed.md",
        "evidence_path": run_dir / "evidence.json",
        "audit_path": run_dir / "audit.jsonl",
    }
    files["invocation_path"].write_text(json.dumps(invocation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    files["provenance_path"].write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    files["handoff_path"].write_text(handoff, encoding="utf-8")
    files["seed_path"].write_text(seed, encoding="utf-8")
    files["evidence_path"].write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    files["audit_path"].write_text("".join(json.dumps(event, sort_keys=True) + "\n" for event in audit_events), encoding="utf-8")

    return {
        **invocation,
        **{key: str(path) for key, path in files.items()},
        "run_dir": str(run_dir),
        "provenance": provenance,
        "recommended_command": f"ooo run {shlex.quote(str(files['seed_path']))}",
    }
