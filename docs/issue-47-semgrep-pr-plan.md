# Issue #47 Semgrep AgentOS Assimilation PR Plan

Issue: https://github.com/Q00/ouroboros-plugins/issues/47


## Issue #27 capability-assimilation alignment

Issue #47 is a concrete static-analysis reference case for the plugin-authoring thesis in [#27](https://github.com/Q00/ouroboros-plugins/issues/27): plugins are not arbitrary wrappers or marketplace entries; they are the capability assimilation layer that keeps core small while translating external tools into structured, auditable, permissioned, handoff-capable Ouroboros capabilities.

The four PRs preserve that boundary as follows:

- **PR 1** proves repository/reference fit rather than marketplace growth: the manifest uses the existing `0.1` contract, records a capability-oriented plugin name, separates core capabilities from external permissions, documents Semgrep as an external engine, and rejects schema expansion until a reference need is proven.
- **PR 2** implements the defensive boundary from #27: Semgrep remains outside core, invocation is isolated behind a bounded argv runner, file/config/output paths are repo-bounded, local-first scanning is the default, and remote registry configs are explicit `network:read` opt-ins.
- **PR 3** implements the offensive assimilation layer from #27: raw Semgrep output is preserved while Ouroboros receives normalized findings, bounded provenance, audit-compatible events, explicit states, and handoff metadata that downstream agents can consume.
- **PR 4** locks conformance evidence: tests prove the wrapper does more than invoke a command by checking permission boundaries, normalized artifacts, handoff generation, blocked/failed semantics, and Semgrep exit-code preservation.

Together, the stack satisfies the #27 distinction between a trivial wrapper (`run semgrep`) and an Ouroboros-native capability (`Semgrep + declared authority + risk model + provenance + audit + handoff + verification`).

## Decision: 4 PRs

The epic should be merged as four reviewable PRs. Each PR is independently coherent, but together they complete the v0 read-only Semgrep AgentOS capability.

### PR 1 — Contract, manifest, catalog, and product boundary

Scope:
- Add `plugins/semgrep-static-analysis/ouroboros.plugin.json` using schema `0.1` with no schema expansion.
- Add the catalog entry.
- Add README documenting Semgrep UX preservation, local-first privacy defaults, non-goals, dependency/licensing stance, permission/capability split, and future expansion boundaries.

Acceptance:
- `python3 scripts/validate_contract.py` passes.
- Reviewers can validate that Semgrep fits the current plugin contract.

### PR 2 — Safe read-only scan runner

Scope:
- Add Python entrypoint for `scan`.
- Require an installed `semgrep` executable; do not vendor/install Semgrep.
- Build argv lists instead of shell strings.
- Enforce repo-bounded target/config paths.
- Default to local configs, metrics off, version check disabled, and no source upload assumptions.
- Model remote/registry configs as an explicit opt-in path.

Acceptance:
- Unit tests cover argv construction, path bounds, local-vs-remote config handling, and missing executable failure.

### PR 3 — Artifacts, normalization, and provenance

Scope:
- Preserve raw Semgrep JSON and optional SARIF.
- Normalize findings into an Ouroboros-friendly JSON artifact.
- Generate Markdown summaries.
- Hash artifacts and write bounded provenance.
- Preserve exit-code and stderr evidence in bounded artifacts.

Acceptance:
- Unit tests cover empty findings, findings, malformed JSON, artifact hashes, summary output, and Semgrep exit semantics.

### PR 4 — Audit/handoff integration and final verification

Scope:
- Emit audit-compatible event payloads for invoked, permission-used, completed/failed/blocked states.
- Emit a handoff manifest that downstream agents can attach to Seed/Ledger/State workflows.
- Complete README usage examples and v0/future command boundary.
- Run repository contract validation and relevant unit tests.

Acceptance:
- All issue #47 acceptance criteria for the v0 read-only scan path are satisfied.
- Merging PRs 1–4 closes the epic for the initial Semgrep AgentOS assimilation.

## Implemented branch layout

This worktree implements all four PR scopes together so the branch can be split into the PRs above if desired, or reviewed as one integrated reference implementation.
