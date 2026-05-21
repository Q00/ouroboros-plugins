# Issue #39 Superpowers PR Plan

Issue #39 should land as **six PRs**. The sequence keeps the AgentOS contract reviewable while ensuring that merging all six resolves the epic.

## PR 1 — Contract, docs, and plugin skeleton

Scope:
- Add `plugins/openai-skills-superpowers/` as the reference plugin name.
- Add a schema-valid `ouroboros.plugin.json` with `superpower` command projections.
- Document that this is capability assimilation, not a marketplace or bulk import.
- Record relation to issue #27 and the `ooo auto` boundary.

Out of scope:
- Catalog fetching, skill execution, script execution, direct aliases.

## PR 2 — Catalog ingestion, list, and inspect

Scope:
- Ingest a pinned `openai/skills` tree from a GitHub ref or local source path.
- Parse every `SKILL.md` frontmatter.
- Detect `scripts/`, `references/`, `assets/`, and `agents/openai.yaml`.
- Record repository/ref/path/license provenance.
- Infer permission and risk profiles.
- Implement `catalog refresh`, `catalog list`, and `inspect`.
- Handle duplicate skill names: unqualified lookup prefers `.curated`; use `system/<name>` for `.system` duplicates.

Out of scope:
- Executing workflows or scripts.

## PR 3 — Handoff and audit/provenance

Scope:
- Implement `superpower handoff <skill-name> --task <task> --out <path>`.
- Produce `kind: superpower_handoff` JSON that preserves skill instructions and resource references.
- Emit standard plugin audit events and provenance evidence.
- Document how `ooo auto` consumes handoffs without becoming a skill-specific router.

Out of scope:
- Runtime execution beyond handoff creation.

## PR 4 — Read-only run

Scope:
- Implement `superpower run` for read-only skills by projecting the skill into the active agent context.
- Support at least `openai-docs`, `security-best-practices`, `security-threat-model`, and `pdf` in read-only mode.
- Preserve progressive disclosure: include `SKILL.md` and selected references, not every asset eagerly.
- Emit invoked, permission-used, completed, blocked, and failed audit events.

Out of scope:
- Shell execution and external writes.

## PR 5 — Trusted scripts and local writes

Scope:
- Add `trust-plan` for exact permission decisions.
- Gate script-backed skills on plugin-manager-provided trust plus shell permission.
- In the standalone reference adapter, block script execution and expose required scopes via `trust-plan`.
- Keep local artifact writes cwd-relative/bounded until wider filesystem grants are manager-mediated.

Out of scope:
- External SaaS writes or deployments.

## PR 6 — External service/deployment policy and polish

Scope:
- Add explicit GitHub/Figma/Linear/Notion/Sentry/deploy scope inference.
- Block external-write/destructive skills until trusted.
- Add `doctor`, README linkage, and final acceptance validation.
- Defer direct aliases until namespace collision/ownership policy is stronger.

Out of scope:
- Adding new manifest fields; v0 uses runtime risk overlays inside the adapter.


## Issue #27 conformance checklist

Each PR scope must preserve the plugin-authoring consensus from issue #27:

| #27 requirement | Superpowers PR alignment |
| --- | --- |
| Contract/reference repository, not marketplace | `plugins/openai-skills-superpowers` is one reference adapter; skills remain catalog projections. |
| Core stays small | Skill-specific behavior stays in the plugin entrypoint and handoff artifacts, not `ooo auto` or core. |
| Not just a command wrapper | The adapter records permissions, capabilities, risk, provenance, audit outcomes, and continuation handoffs. |
| Manifest is minimum executable boundary | `ouroboros.plugin.json` declares command projections, capabilities, permissions, entrypoint, and audit vocabulary. |
| Capabilities and permissions stay distinct | Capabilities cover Ouroboros primitives; permissions cover filesystem/network/shell/GitHub/external authority. |
| Shared risk taxonomy | Read-only, write, and destructive risks are inferred per skill and enforced at runtime. |
| Lifecycle/trust/firewall behavior | Script, write, external-write, and destructive workflows return blocked outcomes unless a future plugin-manager trust context can prove exact scopes. |
| Audit/provenance/handoff | `handoff` and `run` emit standard plugin events and preserve skill source/ref/path/loaded resources. |
| Preserve `ooo auto` boundary | `ooo auto` may consume generated handoffs, but direct skill routing remains inside `superpower`. |

This checklist is the merge guard for the PR stack: if a later PR weakens one
of these rows, it must be fixed before merge.

## Final merge condition

The epic is complete when the six PRs together provide a schema-valid `openai-skills-superpowers` plugin that can represent all 43 observed OpenAI skills from pinned `openai/skills` main (`590b49edc158611a2b2ed715ae73f27eb70d251a` as verified on 2026-05-21), inspect each skill, create handoff artifacts, run read-only skills, produce exact trust plans for script-backed workflows, and block script/write/external-write/destructive workflows until plugin-manager-mediated trust is available.
