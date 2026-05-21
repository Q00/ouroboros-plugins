# Issue #30 PR plan: GSD → AgentOS via `gsd-agentos`

Issue #30 should be delivered as **6 PRs**. Each PR is mergeable on its own and preserves the Ouroboros plugin firewall; together they satisfy the epic acceptance criteria.

## PR 1 — Catalog and contract mapping

**Scope:** add `plugins/gsd-agentos`, its manifest, and a reviewed command catalog generated from pinned upstream `gsd-build/get-shit-done` `commands/gsd/*.md`.

**Includes:** command names, aliases, descriptions, argument hints, upstream paths/checksums, namespace `gsd`, risk tiers, permissions, expected artifacts, mutation flags, catalog validation tests, and root catalog registration.

**Excludes:** executing upstream GSD commands or writing project handoffs.

## PR 2 — Read-only runtime and inspection

**Scope:** provide the plugin CLI inspection surface: `list`, `explain`, `validate-catalog`, and policy-checked read-only invocation.

**Includes:** trust-scope checks, missing-trust error text, read-only audit/provenance events, and tests for list/explain/blocked behavior.

**Excludes:** filesystem-writing handoff conversion and shell-backed execution.

## PR 3 — Handoff-producing write commands

**Scope:** create AgentOS/Ouroboros-readable handoff bundles for GSD planning, execution, verification, and review artifacts.

**Includes:** `.planning/*` projection to `.ouroboros/handoffs/gsd/*.md` and `.json`, bounded artifact metadata/checksums, next-action hints, and fixture tests.

**Excludes:** calling real upstream GSD machinery.

## PR 4 — Bounded upstream runner

**Scope:** add shell-backed execution only behind explicit `shell:execute` trust.

**Includes:** environment-configured runner, timeout, bounded stdout/stderr capture, exit-code classification, audit/provenance, and tests with a harmless fake runner.

**Excludes:** destructive command enablement by default.

## PR 5 — High-impact command confirmation policy

**Scope:** harden destructive/high-impact commands such as `ship`, `complete-milestone`, `pr-branch`, `undo`, `autonomous`, `audit-fix`, and `update`.

**Includes:** destructive risk classification, `requires_confirmation`, command-level `--confirm <command>` gate, blocked/cancelled/completed tests, and documented trust semantics.

**Excludes:** new core permission types; git/network remain modeled through existing scopes.

## PR 6 — AgentOS integration polish and documentation

**Scope:** end-to-end documentation and integration proof that the plugin is a reference implementation of the capability-assimilation contract from #27.

**Includes:** README examples, trust commands, mental-model mapping, acceptance-criteria traceability, validation commands, and root catalog/readme references.

**Excludes:** marketplace support for arbitrary GSD extensions or changes to `ooo auto` routing.

## Issue #27 alignment matrix

This stack intentionally treats GSD as a #27 capability-assimilation reference,
not as a loose command-wrapper collection. Each PR proves a different part of
the #27 contract thesis:

| PR | #27 contract alignment | Merge-safety check |
| --- | --- | --- |
| PR 1 — plan | Records `Q00/ouroboros-plugins` as the curated contract/reference surface for this assimilation, not a marketplace for arbitrary GSD extensions. | Scope explicitly rejects marketplace behavior and `ooo auto` routing changes. |
| PR 2 — contract | Makes the manifest and reviewed catalog the executable boundary: namespace, command declarations, capabilities, permissions, risk tiers, and upstream provenance are declared before runtime behavior. | Every catalog command is represented in `ouroboros.plugin.json`; no hidden command surface. |
| PR 3 — runtime/handoff | Converts GSD from "run this external prompt/CLI" into permissioned, auditable, resumable AgentOS behavior with policy checks, provenance records, handoff bundles, and bounded runner semantics. | Read-only invocations do not write target repos; shell execution requires explicit `shell:execute`. |
| PR 4 — tests | Locks the #27 firewall properties in tests: catalog coverage, manifest exposure, permission blocking, destructive confirmation, handoff generation, and bounded runner behavior. | Regression tests fail if GSD drifts into unbounded wrapper behavior. |
| PR 5 — plugin docs | Explains author/user-facing trust, audit, handoff, and destructive confirmation semantics so the plugin remains recognizable as GSD while becoming Ouroboros-native. | Docs preserve capabilities-vs-permissions and explicit trust semantics. |
| PR 6 — root docs | Surfaces GSD as a reference capability-assimilation example alongside other contract-bearing plugins. | Root docs do not present the repo as a marketplace or plugin-count surface. |

The stack also preserves the specific #27 boundaries:

- **Core stays small:** no changes to Ouroboros core or first-party `ooo auto` routing.
- **Repository role:** this repo remains a curated contract/reference repository.
- **Not just wrappers:** GSD commands are declared, permissioned, risk-classified,
  audited, provenance-bearing, and handoff-capable.
- **Capabilities vs permissions:** manifest capabilities model Ouroboros substrate
  access; permissions model external authority.
- **Risk taxonomy:** command and permission risk use `read_only`, `write`, and
  `destructive` consistently.
- **Lifecycle/trust/firewall:** invocation is blocked before runtime behavior when
  trust is missing or destructive confirmation is absent.
- **Audit/provenance/handoff:** invocation outputs include bounded records and
  AgentOS-readable handoff projections.
- **No marketplace expansion:** no support for arbitrary GSD extensions,
  auto-update, or subdirectory-leaking install strings is added.
