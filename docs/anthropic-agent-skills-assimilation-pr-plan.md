# Anthropic Agent Skills assimilation PR plan for issue #33

Issue #33 is an epic for assimilating `anthropics/skills` into AgentOS through the `ouroboros-plugins` contract. The target repository is `anthropics/skills`; this repository remains the adapter/contract layer.

## PR count and merge order

Implement the epic as **5 stacked PRs**. They are intentionally ordered so each PR is independently reviewable and mergeable, while the final merge satisfies the epic acceptance criteria.

### PR 1 — Contract/design + reference plugin shell

**Scope**
- Add the `anthropic-agent-skills` reference plugin manifest using existing schema `0.1` only.
- Add docs that state the assimilation boundary, non-goals, license policy, progressive disclosure contract, and audit/handoff semantics.
- Add a checked-in PR breakdown so review can track the epic without expanding the manifest schema speculatively.

**Out of scope**
- No vendoring of restricted/source-available upstream materials.
- No runtime execution of upstream scripts.
- No manifest schema expansion.

### PR 2 — Local Agent Skill inspection and validation CLI

**Scope**
- Implement `ooo anthropic-skills inspect <skill-dir>` for local Agent Skill directories.
- Implement `ooo anthropic-skills validate <skill-dir-or-plugin-dir>` with license/provenance warnings.
- Inventory `SKILL.md`, `scripts/`, `references/`, and `assets/` without loading bulky resources into memory.
- Emit structured JSON suitable for provenance and handoff.

**Out of scope**
- Multi-skill repository catalog generation.
- Script execution.

### PR 3 — Anthropic skills catalog + command taxonomy/resolver

**Scope**
- Add `plugins/anthropic-agent-skills/catalog/anthropic-skills.json` pinned to upstream revision `690f15cac7f7b4c055c5ab109c79ed9259934081`.
- Include every upstream skill from issue #33 with at least one command entry or an explicit blocked/adapter-only reason.
- Classify command risk, license state, permissions, capabilities, trigger aliases, dependencies, limitations, and handoff schema.
- Implement `ooo anthropic-skills catalog <repo-or-path>` and read-only natural-language resolver candidates.

**Out of scope**
- Full-fidelity invocation of each upstream skill.
- Vendoring restricted document-skill code.

### PR 4 — Progressive invocation, provenance, and handoff MVP

**Scope**
- Implement `ooo anthropic-skills invoke <skill-name> <command> [args...]` as a bounded adapter path.
- Preserve progressive disclosure: metadata/catalog first, `SKILL.md` only on invocation, references/assets lazily by command adapter.
- Emit standard audit events (`plugin.invoked`, `plugin.permission_used`, `plugin.completed`, `plugin.failed`).
- Generate handoff artifacts for `success`, `failed`, `blocked`, and `cancelled` outcomes.
- Block unavailable source, restricted license, missing dependency, and untrusted execution paths explicitly.

**Out of scope**
- Unbounded shell pass-through.
- Silent grants for network-write or destructive behavior.

### PR 5 — Reference conversions, tests, and docs finalization

**Scope**
- Provide end-to-end adapter contracts for the three required proof points: `webapp-testing`, `mcp-builder`, and `skill-creator`.
- Add tests for manifest validation, inspection, catalog completeness, license policy, resolver behavior, blocked invocation, and handoff shape.
- Update README/catalog index and document controlled execution boundaries.
- Run final cleanup/review gate.

**Out of scope**
- Making `ooo auto` a skill-specific router.
- Turning this repository into a marketplace.

## Completion definition

The epic is complete after PR 5 merges if:
- every `anthropics/skills` skill has a command entry or explicit blocked/adapter-only reason;
- all commands are manifest-backed and carry usage, arguments, risk, capabilities, permissions, and entrypoint semantics;
- every invocation goes through the plugin firewall path;
- progressive disclosure, audit, provenance, and handoff are represented;
- restricted/source-available skills are not vendored; and
- `webapp-testing`, `mcp-builder`, and `skill-creator` are represented as first full-fidelity reference conversion contracts.

## Alignment with #27 capability-assimilation SSOT

Issue #27 states that `Q00/ouroboros-plugins` is a curated contract/reference repository, not a marketplace, and that plugins are a capability assimilation layer rather than command wrappers. This stack preserves that boundary as follows:

| #27 requirement | Issue #33 stack alignment |
| --- | --- |
| Core stays small; plugins assimilate external capability | `anthropic-agent-skills` adapts `anthropics/skills` into plugin contracts instead of adding skill-specific behavior to core or `ooo auto`. |
| Repository is contract/reference, not marketplace | The catalog is pinned reference evidence for one assimilation target, not a general hosted marketplace or open-ended listing. |
| Third-party repos remain distribution units | The upstream source remains `https://github.com/anthropics/skills`; restricted materials are not vendored into this repo. |
| Plugins are not trivial command wrappers | Commands declare usage, arguments, risk, capabilities, permissions, audit expectations, provenance, and handoff behavior. |
| Manifest v0.1 remains the executable minimum | The stack uses the existing v0.1 schema and opens no speculative manifest expansion. |
| Capabilities and permissions stay distinct | Catalog entries record core capabilities separately from filesystem/shell/network permissions. |
| Risk taxonomy is shared | Command and permission risk values remain `read_only`, `write`, or `destructive` only. |
| Lifecycle/trust/firewall remain mandatory | Resolver output only selects candidates; `invoke` still emits blocked handoffs when trust/source/license boundaries are not satisfied. |
| Audit, provenance, and handoff make assimilation safe | Every invocation path produces handoff-shaped evidence, loaded-file provenance, executed-script provenance, and standard audit event names. |
| `ooo auto` remains a consumer, not catch-all router | Handoffs are designed for future `ooo auto`/Workflow IR consumption; skill-specific branching remains in the plugin. |
| Reference plugins prove a contract boundary | The required `webapp-testing`, `mcp-builder`, and `skill-creator` conversions are bounded proof points for progressive disclosure, external protocol scaffolding, and Agent Skill conversion. |
| Schema expands only with demonstrated need | Any schema gap discovered by future full-fidelity adapters should become a follow-up issue with reference evidence, not an in-stack schema change. |

P0/P1 review gate for this stack: any change that turns `anthropic-agent-skills` into a marketplace, vendors restricted/source-available upstream material, bypasses the plugin firewall, silently executes upstream scripts, expands the manifest schema without reference evidence, or moves skill-specific routing into `ooo auto` is a blocker.
