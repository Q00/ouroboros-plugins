# Issue #35 PR decomposition: Scientific Agent Skills assimilation

Issue: <https://github.com/Q00/ouroboros-plugins/issues/35>
Target upstream: <https://github.com/K-Dense-AI/scientific-agent-skills>

## Decision

Implement the epic as **7 PRs**, matching the issue milestones and keeping each
merge independently reviewable. PRs should be stacked in this order; each PR
preserves `ouroboros-plugins` as a curated contract/reference repository, not a
marketplace or vendored upstream mirror.

### PR 1 — Inventory/generator/read-only discovery

Scope:

- Add `plugins/scientific-agent-skills-adapter/` as a reference adapter.
- Add `scripts/generate_scientific_adapter.py` to parse upstream
  `scientific-skills/*/SKILL.md` frontmatter and package shape.
- Check in generated registry metadata for all 138 upstream skills: slug,
  description, domain, license, allowed tools, references/scripts/assets counts,
  upstream repository, commit, skill path, and source hash.
- Expose `ooo scientific list`, `inspect`, `explain`, `trust-report`, and
  `doctor` read-only command behavior.
- Add snapshot-style tests for all 138 slugs and the generated registry shape.

Out of scope: execution, trust grants, upstream vendoring, remote calls.

### PR 2 — Permission and risk classifier

Scope:

- Map `allowed-tools`, scripts, package contents, service keywords, credentials,
  and clinical/lab/cloud indicators into permission candidates.
- Classify each skill as `read_only`, `write`, or `destructive`.
- Emit per-skill trust reports and require manual-review flags for ambiguous or
  elevated-risk skills.
- Add blocked-execution tests for high-risk skills.

Out of scope: actual execution of upstream scripts or service calls.

### PR 3 — Manifest generation and contract validation

Scope:

- Generate/maintain `ouroboros.plugin.json` with generic commands plus all
  per-skill aliases (`ooo scientific <skill-slug>`).
- Preserve upstream slugs as command names.
- Validate against `schemas/0.1/plugin.schema.json`.
- Add catalog registration and drift tests for manifest/registry consistency.

Out of scope: schema expansion beyond v0.1 unless a future PR explicitly needs
service-specific permission schema changes.

### PR 4 — Handoff-first prepare model

Scope:

- Implement `prepare` for every skill.
- Write durable Seed-compatible handoff JSON, seed Markdown, provenance, resume
  instructions, permission plan, verification plan, and audit artifact.
- Ensure generated handoffs can be passed to `ooo auto` without making `ooo auto`
  a scientific router.

Out of scope: running scientific workflows.

### PR 5 — Safe runner boundary

Scope:

- Implement `run --dry-run` for all skills as handoff generation.
- Block actual `run` for write/destructive/manual-review skills by default.
- Emit audit artifacts for completed dry-runs and blocked runs.
- Reserve actual low-risk execution for future explicitly trusted paths.

Out of scope: executing high-risk upstream scripts, shell, network, clinical,
cloud, or lab automation behavior.

### PR 6 — Smooth AgentOS UX

Scope:

- Make per-skill aliases behave like built-in `ooo scientific <skill>` commands.
- Add fuzzy unknown-skill suggestions.
- Support `list --domain` and `list --risk` filters.
- Document examples and recommended follow-up commands.

Out of scope: changing AgentOS core dispatch semantics.

### PR 7 — Reference policy/docs and epic closure

Scope:

- Document why this reference adapter belongs in `ouroboros-plugins` while the
  long-tail pack remains an external author/repo-level pack.
- Link the implementation to the capability-assimilation thesis from #27.
- Record final validation evidence: manifest validation, tests, no high-risk
  execution bypass, and all 138 skills discoverable/preparable.

Out of scope: turning this repository into a marketplace or adding all skills to
Ouroboros core.

## Current implementation bundle

This branch implements the full 7-PR stack as a reviewable reference bundle. It
can be opened as one integration PR or split along the boundaries above. The
commits/files are organized to preserve those scopes.

## Issue #27 alignment review

Each proposed PR boundary was reviewed against #27's plugin-authoring and
capability-assimilation thesis:

| PR | #27 alignment | Guardrail |
|---|---|---|
| PR 1 — Inventory/generator/read-only discovery | Treats upstream as an external capability repository and records provenance instead of vendoring a marketplace mirror. | Read-only discovery only; no upstream scripts run. |
| PR 2 — Permission and risk classifier | Keeps capabilities and permissions explicit and separate; risk metadata is executable safety input, not cosmetic. | Classifier output defaults elevated or ambiguous skills to manual review / blocked execution. |
| PR 3 — Manifest generation and contract validation | Uses `ouroboros.plugin.json` as the executable boundary and preserves all command aliases through schema-valid manifest generation. | Manifest declares only core capabilities used by this reference adapter; `runtime`/`mcp` are not predeclared as future authority. |
| PR 4 — Handoff-first prepare model | Converts raw skills into Seed-compatible, auditable, resumable handoffs rather than command wrappers. | `prepare` writes durable artifacts and records `filesystem:write` as required/used authority. |
| PR 5 — Safe runner boundary | Invocation semantics include blocked/failed outcomes and never pretend high-risk upstream behavior ran. | `run --dry-run` is handoff-only; non-dry-run high-risk paths block with audit evidence. |
| PR 6 — Smooth AgentOS UX | Makes the capability feel native while keeping `ooo auto` domain-agnostic. | Per-skill aliases preserve upstream names but route through the same plugin boundary. |
| PR 7 — Reference policy/docs | Preserves `Q00/ouroboros-plugins` as a curated contract/reference repo, not a marketplace. | The long-tail scientific pack remains an external author/repo-level capability pack. |

This review found two P1 alignment fixes and both are implemented in this PR:

1. `filesystem:write` is required and emitted in audit `permissions_used` because
   every `prepare`/dry-run invocation writes handoff, Seed, provenance, and audit
   artifacts.
2. Unused future `runtime`/`mcp` capabilities were removed from the manifest so
   the adapter does not predeclare authority it does not exercise.
