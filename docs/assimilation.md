# External Repository Capability Assimilation

This document is the contract-bearing answer to
[Q00/ouroboros-plugins#29](https://github.com/Q00/ouroboros-plugins/issues/29).
It defines how an **external target repository** becomes an Ouroboros AgentOS
plugin package without making `Q00/ouroboros-plugins` the assimilated project
and without turning this repository into a marketplace mirror.

## Framing

```text
external target repository
  -> assimilated as an Ouroboros plugin package / command pack
  -> governed by AgentOS plugin contracts, permissions, audit, artifacts, and handoffs
  -> usable by Ouroboros workflows and users
```

`ouroboros-plugins` supplies schemas, lifecycle rules, validation, reference
fixtures, and documentation. The external target repository supplies the
domain-specific capabilities. A full third-party command pack should normally
live in its own author repository and be installed by URL:

```bash
ouroboros plugin add https://github.com/<author>/<target>-ouroboros --plugin target-capabilities
```

This repository may host a reference skeleton or contract fixture when it
proves the boundary.

## PR decomposition for issue #29

The epic should be delivered as **5 reviewable PRs**. The PRs are ordered and
stackable; each one is mergeable on its own and narrows the remaining risk.

### PR 1 — Contract alignment and assimilation RFC

Scope:

- Add this `docs/assimilation.md` SSOT.
- Link issue #29 from repository docs as the external-repo assimilation track.
- State the non-marketplace policy and the canonical distribution shape.
- Decide v0 naming and namespacing: one package named `target-capabilities`,
  command namespace `target`, with command-level risk.

Acceptance:

- Docs consistently say the target is an external repository.
- Docs do not imply `ouroboros-plugins` itself is being assimilated.
- Open questions that require future trust UX are explicitly deferred.

### PR 2 — Manifest schema pressure points and validation

Scope:

- Extend command metadata so each command can declare per-command permissions,
  upstream capability mapping, artifact contract, handoff contract, timeout,
  result states, and redaction policy.
- Keep the v0.1 schema backward compatible: existing manifests remain valid.
- Add validator/test coverage for the new metadata.

Acceptance:

- `python3 scripts/validate_contract.py` validates all repository manifests.
- Tests prove command-level permission/artifact/handoff metadata is accepted.
- Unknown metadata remains rejected by `additionalProperties: false`.

### PR 3 — Reference target-capabilities package skeleton

Scope:

- Add `plugins/target-capabilities/ouroboros.plugin.json`.
- Add `python -m target_capabilities` bounded entrypoint.
- Implement `list-commands`, `inspect`, and `doctor`.
- Detect installed/pinned target dependencies using `--target-root` or
  `TARGET_CAPABILITIES_ROOT` and fail closed when unavailable.

Acceptance:

- The package can be invoked through `PYTHONPATH=plugins/target-capabilities`.
- Missing dependencies return structured `blocked` output, not opaque crashes.
- Paths are bounded; relative member paths cannot escape the target checkout.

### PR 4 — Artifact, provenance, handoff, and command tranche behavior

Scope:

- Every command writes bounded artifacts under
  `.ouroboros/artifacts/target-capabilities/<command>/<run-id>/`.
- Artifacts include `result.json`, `report.md`, `stdout.txt`, `stderr.txt`,
  `provenance.json`, and `handoff.json`.
- Implement read-only inventory/inspection, write planning/report generation,
  and a destructive sample command that blocks unless explicit trust and
  confirmation are present.

Acceptance:

- Outputs contain plugin, assimilated repository, command, status, risk,
  artifacts, handoff, and next actions.
- Write commands summarize bounded writes.
- Destructive commands are blocked without explicit trust and confirmation.

### PR 5 — AgentOS continuation docs, tests, and final quality gate

Scope:

- Document how `ooo auto` or an equivalent harness consumes the handoff.
- Add tests for happy paths, blocked missing dependency, bounded paths,
  artifact/handoff shape, and destructive gating.
- Update README/catalog and run final cleanup/review.

Acceptance:

- The issue #29 acceptance criteria are covered by docs, manifests, code, and
  tests.
- `pytest` and contract validation pass.
- Final review has no blocking architecture or code-quality findings.

## Command metadata contract

Command-level metadata is optional in schema v0.1 so existing manifests remain
valid. Assimilation plugins SHOULD declare it for every command.

```json
{
  "namespace": "target",
  "name": "inspect",
  "risk": "read_only",
  "permissions": ["filesystem:read"],
  "upstream": {
    "capability": "repository-inspection",
    "mode": "pinned_checkout"
  },
  "artifacts": {
    "writes": ["result.json", "report.md", "provenance.json", "handoff.json"]
  },
  "handoff": {
    "produces": true,
    "consumer": "ooo auto"
  },
  "timeout_seconds": 30,
  "result_states": ["completed", "blocked", "failed"],
  "redaction": {
    "rules": ["no secrets", "bounded excerpts only"]
  }
}
```

## Upstream dependency strategy

v0 supports two explicit modes:

1. **Installed tool mode** — the command can call a known installed tool.
2. **Pinned checkout mode** — `--target-root` or `TARGET_CAPABILITIES_ROOT`
   points to a local checkout.

Managed install and auto-update are deferred until trust invalidation and
update semantics are stronger. Missing dependencies must fail closed:

```json
{
  "status": "blocked",
  "reason": "target_dependency_not_found",
  "message": "Install the target tool or configure TARGET_CAPABILITIES_ROOT before invoking this plugin."
}
```

## Artifact and handoff contract

Each invocation creates a run directory containing bounded, inspectable files:

```text
.ouroboros/artifacts/target-capabilities/<command>/<run-id>/
  result.json
  report.md
  stdout.txt
  stderr.txt
  provenance.json
  handoff.json
```

The `result.json` payload is also printed to stdout. It includes:

- plugin and version
- assimilated repository identifier
- command and command risk
- result status (`completed`, `blocked`, `failed`, `cancelled`)
- artifact paths
- handoff path
- next suggested Ouroboros commands

`handoff.json` is intentionally a small continuation object. It is safe for
`ooo auto` or another harness to consume because it points to bounded artifacts
rather than embedding unbounded external content.

## Permission and risk policy

- Read-only commands may inspect the target and write their own bounded
  artifacts.
- Write commands may create plans, reports, local artifacts, or bounded patches
  only inside declared roots.
- Destructive commands require both previously granted trust and explicit
  per-invocation confirmation. If either is absent, they return `blocked` and
  do not perform the destructive operation.

Destructive v0 examples are reference gates only. Real publish, deploy, merge,
delete, credential import, or production-affecting operations remain deferred
until Ouroboros core trust UX is proven.

## AgentOS continuation

A target command should suggest concrete next actions, for example:

```json
[
  {"command": "ooo target report --handoff <handoff.json>", "reason": "Summarize produced artifacts"},
  {"command": "ooo auto --handoff <handoff.json>", "reason": "Continue from target handoff"}
]
```

Continuation consumers must read the handoff, verify the artifact paths are
inside the run directory, and then attach the result to Seed / Run / Step /
Artifact records as appropriate. The target plugin does not bypass the plugin
firewall and does not mutate Ouroboros core state directly.
