# Plugin Contract MVP

This document defines the first contract target for local-only UserLevel
plugins.

The goal is to stabilize the boundary before building a registry.

## Manifest

Each plugin package contains an `ouroboros.plugin.json` manifest.

Required fields:

- `schema_version`
- `name`
- `version`
- `description`
- `source`
- `commands`
- `capabilities`
- `permissions`
- `entrypoint`
- `audit`

## Sources

The MVP accepts only local sources:

- `local_path`: explicitly configured local directory
- `plugin_home`: installed directory under `~/.ouroboros/plugins`
- `first_party`: program shipped with Ouroboros

Network registry, marketplace search, and auto-update are out of scope.

### first_party flow

`first_party` is **not** part of the user-facing install lifecycle.
Programs with `source.type=first_party` ship with Ouroboros core (e.g.
`ooo auto`, `ooo run`, `ooo pm`) and are registered **at core boot**,
bypassing `discovered → installed → trusted`. They share the manifest
format with installable plugins so the loader (Q00/ouroboros#728) can
treat both kinds through one code path, and so first-party programs
remain auditable through the same capability/permission contract.

Concretely:

- The loader reads first-party manifests from a known location inside
  Ouroboros core (e.g. `src/ouroboros/programs/<name>/ouroboros.plugin.json`).
- Trust state is the literal `first_party` (per `States` in
  `lifecycle.md`); no user-issued `ouroboros plugin trust` step is
  needed.
- The manager will refuse `ouroboros plugin add` for any source that
  resolves to `source.type=first_party` — those manifests are not
  installable.
- `plugin.trusted` audit events are **not** emitted for first-party
  programs (there is no separate trust grant). All other events
  (`plugin.invoked`, `plugin.permission_used`, `plugin.completed`,
  `plugin.failed`) are emitted normally.

This is the resolution of the open question in Q00/ouroboros-plugins#8.

## Commands

Plugins own command namespaces.

Example:

```json
{
  "namespace": "github-pr",
  "commands": [
    {
      "name": "review",
      "summary": "Review a pull request and summarize readiness.",
      "risk": "read_only",
      "requires_confirmation": false,
      "usage": "ooo github-pr review <pull-request-url>"
    }
  ]
}
```

The manager must reject namespace collisions unless explicitly overridden by
the user.

## Capabilities

Capabilities declare access to Ouroboros core primitives.

Initial capability candidates:

- `seed` with `read` or `write`
- `ledger` with `read` or `write`
- `state` with `read` or `write`
- `provenance` with `write`
- `runtime` with `execute`
- `mcp` with `call`
- `handoff` with `attach`
- `progress` with `write`

Capabilities should be narrower than permissions. They describe core access,
not external system access.

## Permissions

Permissions declare external access.

Initial permission candidates:

- `filesystem:read`
- `filesystem:write`
- `network:read`
- `network:write`
- `shell:execute`
- `github:read`
- `github:pull_request:write`
- `slack:read`
- `slack:write`

Install should not imply trust for destructive permissions.
Each permission declares its risk tier and whether it is required for the
plugin's baseline operation.

## Risk taxonomy

A single 3-value risk enum is shared between `command.risk` and
`permission.risk`:

- `read_only` — no side effects on state or external systems.
- `write` — reversible side effects (writes ledger / state, idempotent
  external operations).
- `destructive` — irreversible side effects (merging PRs, deleting
  resources, sending messages, payments).

If `permissions[]` includes any `destructive` scope, the `commands` using
that scope should declare `risk: destructive` so the manager's
confirmation prompt is unambiguous. The trust UX
(Q00/ouroboros-plugins#9) is built around the destructive tier — granting
a destructive permission is a separate, deliberate user action.

This is the resolution of Q00/ouroboros-plugins#10. Older candidate
values (`writes_state`, `external_write`) are removed.

## Entrypoint

The MVP should support local command entrypoints first.

Example:

```json
{
  "entrypoint": {
    "type": "command",
    "command": "python -m github_pr_ops"
  }
}
```

Out-of-process execution is preferred for early plugin isolation.

## Audit

Every plugin invocation should record:

- Plugin name and version
- Command namespace and command name
- User-provided arguments
- Core capabilities used
- External permissions used
- Provenance source
- Result status

See `docs/audit.md` and `schemas/audit-event.schema.json`.

## Non-goals

- No public registry in v1
- No auto-update in v1
- No implicit destructive permission grants
- No arbitrary mutation of core state
