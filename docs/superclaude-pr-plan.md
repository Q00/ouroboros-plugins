# SuperClaude AgentOS Assimilation PR Plan

Issue: Q00/ouroboros-plugins#32  
Target upstream: SuperClaude-Org/SuperClaude_Framework  
Pinned snapshot: `226c45cc93b865108843a669c6545d421784b68c` (`2026-04-27T08:38:57+05:30`)  
Upstream version/license: `4.3.0`, MIT

## Decision: 5 PRs

The epic should land as **5 PRs**. This keeps each reviewable while ensuring the final merged sequence satisfies the whole epic without requiring Ouroboros core changes.

### PR 1 — Snapshot, provenance, and legal baseline

**Scope**
- Add `plugins/superclaude/` package shell.
- Vendor or reproducibly sync the pinned upstream SuperClaude assets.
- Preserve upstream MIT license attribution.
- Record exact upstream commit, date, version, license, command/skill/agent/mode inventory, and the README mismatch: upstream prose says 7 skills but the pinned snapshot contains 6 concrete `SKILL.md` folders.

**Out of scope**
- Runtime behavior beyond static asset inspection.
- Contract/schema changes.

**Acceptance**
- Provenance is visible in plugin docs and machine-readable catalog metadata.
- Upstream assets can be audited back to the pinned commit.

### PR 2 — Manifest and command catalog

**Scope**
- Add `plugins/superclaude/ouroboros.plugin.json` using schema `0.1`.
- Enumerate all 30 upstream commands under namespace `superclaude`.
- Add skill exposure routes for concrete skills, including non-overlapping `confidence-check` and `token-efficiency`.
- Assign conservative risk tiers and permission declarations.
- Add a generated/maintained command catalog with source paths and metadata that schema v0.1 cannot express.

**Out of scope**
- Relaxing the namespace regex for `sc`.
- Adding manifest-native asset metadata fields.

**Acceptance**
- `python3 scripts/validate_contract.py` passes.
- Manifest covers every pinned upstream command.
- `sc` is documented as a desired compatibility alias blocked by current schema/runtime constraints.

### PR 3 — Skills, agents, modes, MCP, and hook mapping

**Scope**
- Package all upstream command, skill, agent, mode, MCP, and hook assets.
- Add discovery metadata for agents/modes/skills.
- Document MCP recommendations without auto-installing servers.
- Translate upstream hooks into documented Ouroboros lifecycle expectations and record unsupported lifecycle gaps as follow-up contract questions.

**Out of scope**
- Automatic MCP installation.
- Hidden hook execution that bypasses the plugin firewall.

**Acceptance**
- Every concrete upstream `SKILL.md` has an Ouroboros route.
- Agent and mode assets are discoverable.
- Hook/MCP behavior is transparent and non-implicit.

### PR 4 — Runtime adapter, audit, and handoff artifacts

**Scope**
- Implement `python -m superclaude_ouroboros` entrypoint.
- Dispatch `ooo superclaude <command> ...` and `ooo superclaude skill <skill> ...`.
- Load selected command, skill, agent, and mode assets.
- Emit structured JSON results and standard audit event payloads.
- Write handoff artifacts for planning/research/workflow-style commands when an artifact directory is supplied.
- Block write/destructive paths unless required trust scopes are present in the invocation environment.

**Out of scope**
- Reimplementing all SuperClaude automation internals.
- Performing destructive Git/network operations in MVP.

**Acceptance**
- Read-only commands run without write trust.
- Write commands are blocked without required scopes.
- Destructive Git paths require explicit destructive trust plus confirmation.
- Runtime does not require SuperClaude-specific branching in Ouroboros core.

### PR 5 — Tests, docs, catalog, and final epic closure

**Scope**
- Add contract, inventory, route, and smoke tests.
- Add README with original SuperClaude UX → Ouroboros UX mapping.
- Add catalog entry.
- Validate representative commands: `help`, `analyze`, `brainstorm`, `confidence-check`, `pm`, `test`, `workflow`.
- Document follow-up contract questions for aliases, asset metadata, lifecycle hooks, MCP recommendations, and prompt-native commands.

**Out of scope**
- Shipping schema v0.2/v1 changes.
- Opening remote PRs from CI credentials.

**Acceptance**
- All repo tests pass.
- Issue #32 acceptance criteria are satisfied by the merged sequence.

## Implementation note for this worktree

This worktree implements the full 5-PR scope together so it can be split into the PRs above during review. No SuperClaude-specific behavior is added to Ouroboros core.
