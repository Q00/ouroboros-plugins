# Issue #29 implementation PR plan

Issue #29 should be implemented as five PRs:

1. **PR 1: Contract/RFC docs** — add `docs/assimilation.md`, clarify that the
   assimilation target is an external repository, define non-goals and v0
   distribution policy.
2. **PR 2: Schema and validator metadata** — extend v0.1 command metadata for
   per-command permissions, upstream mapping, artifacts, handoff, timeout,
   result states, and redaction policy; keep existing manifests compatible.
3. **PR 3: Reference package skeleton** — add `target-capabilities` manifest,
   bounded Python entrypoint, dependency detection, `list-commands`, `inspect`,
   and `doctor`.
4. **PR 4: Artifact/handoff command tranches** — implement inventory/read-only,
   plan/report write behavior, safe destructive blocking, audit/provenance-ready
   artifacts, and continuation handoff output.
5. **PR 5: Integration docs/tests/final gate** — update README/catalog, add
   tests for contract acceptance criteria, validate manifests, run final cleanup
   and review.

The branch `feat/issue-29-agentos-assimilation` contains a complete stacked
implementation of all five PR scopes for local review. If maintainers prefer
separate GitHub PRs, split this branch at the commits matching the sections
above.
