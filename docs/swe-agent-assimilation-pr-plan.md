# Issue #43 PR implementation plan

Implement **5 PRs**:

1. **PR 1 — Design/RFC and PR scope contract**: `docs/swe-agent-assimilation.md`; no runtime changes.
2. **PR 2 — Plugin skeleton, manifest, and operator docs**: `plugins/swe-agent-harness/ouroboros.plugin.json`, plugin README, package entrypoint, catalog/README references.
3. **PR 3 — Artifact discovery and handoff conversion**: artifact discovery library, `collect-artifacts`, `handoff`, `verify-artifacts`, AgentOS bundle writers, fixture tests.
4. **PR 4 — Bounded runner and permission semantics**: `run`/`run-replay` pass-through, `--agentos-*` flags, blocked semantics, stdout/stderr capture, no default patch application/PR creation.
5. **PR 5 — Read-only tooling and quality gate**: `inspect`, `quick-stats`, smoke tests, contract validation, cleanup, and final review.

Merge completion of these PRs resolves the epic acceptance criteria without schema expansion, vendoring SWE-agent, host patch application, or default PR creation.
