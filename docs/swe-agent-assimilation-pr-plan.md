# Issue #43 PR implementation plan

Implement **5 PRs**:

1. **PR 1 — Design/RFC and PR scope contract**: `docs/swe-agent-assimilation.md`; no runtime changes.
2. **PR 2 — Plugin skeleton, manifest, and operator docs**: `plugins/swe-agent-harness/ouroboros.plugin.json`, plugin README, package entrypoint, catalog/README references.
3. **PR 3 — Artifact discovery and handoff conversion**: artifact discovery library, `collect-artifacts`, `handoff`, `verify-artifacts`, AgentOS bundle writers, fixture tests.
4. **PR 4 — Bounded runner and permission semantics**: `run`/`run-replay` pass-through, `--agentos-*` flags, blocked semantics, stdout/stderr capture, no default patch application/PR creation.
5. **PR 5 — Read-only tooling and quality gate**: `inspect`, `quick-stats`, smoke tests, contract validation, cleanup, and final review.

Merge completion of these PRs resolves the epic acceptance criteria without schema expansion, vendoring SWE-agent, host patch application, or default PR creation.

## #27 alignment matrix

Each stacked PR preserves the #27 UserLevel plugin authoring thesis: plugins are capability-assimilation boundaries, not arbitrary command wrappers or marketplace listings.

| PR | #27 alignment check | Merge-safety expectation |
|---|---|---|
| PR 1 | Records the defensive/offensive plugin-layer purpose, non-marketplace stance, external-tool assimilation rules, manifest/risk/trust/audit/handoff vocabulary, and schema-change restraint. | Documentation-only; safe to merge independently. |
| PR 2 | Adds a reference plugin package under `plugins/<name>/` with a v0.1 manifest, command namespace, capabilities, permissions, entrypoint, README, and catalog metadata. It keeps SWE-agent external instead of vendoring it into core. | Commands fail closed as skeleton placeholders until downstream stack lands; no destructive side effects. |
| PR 3 | Turns upstream SWE-agent artifacts into bounded AgentOS provenance/audit/handoff artifacts, which is the core difference between a wrapper and an Ouroboros-native capability. | Artifact collection is local-write only and does not execute SWE-agent. |
| PR 4 | Adds runtime execution only behind explicit shell/runtime trust and records blocked/failed/completed/submitted semantics. It preserves upstream CLI shape while enforcing AgentOS authority boundaries. | Real execution fails closed without explicit `--agentos-allow-execute`; host patch and PR mutation remain separately trusted. |
| PR 5 | Locks the contract with fixture tests and read-only inspection tooling, proving the reference plugin can be validated without external provider credentials or a real SWE-agent install. | Final stack is merge-ready when contract validation and unit tests pass. |

P0/P1 review rule for this epic: any PR that silently expands core, vendors SWE-agent, stores secrets, applies host patches by default, opens PRs by default, bypasses manifest validation, or emits misleading audit/provenance evidence is non-mergeable until fixed.
