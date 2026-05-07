# Plugin Contract MVP

This document defines the first contract target for local-only UserLevel
plugins.

The goal is to stabilize the boundary before building a registry.

## Manifest

Each plugin package contains an `ouroboros.plugin.json` manifest.

The manifest carries **8 required + 2 optional** top-level fields. The split is
deliberate — every required field is load-bearing for some part of the
lifecycle, lockfile, or firewall; every optional field has a sensible default
so plugin authors don't write ceremonial values.

| Field | Status | Default | Why this status |
|---|---|---|---|
| `schema_version` | required | — | Versioning policy (Q00/ouroboros-plugins#11) routes the validator to the right archived schema; the value is the entry point. |
| `name` | required | — | Identity. Used as plugin home directory name and as audit-event `plugin.name`. |
| `version` | required | — | Lockfile (Q00/ouroboros#732) and trust-bump invalidation (Q00/ouroboros-plugins#9 Q4) both key off this. |
| `source` | required | — | Loader (Q00/ouroboros#728) uses `source.type` to distinguish `local_path` / `plugin_home` / `first_party` for trust-state defaults. Inferring from install path is brittle. |
| `commands` | required | — | Without commands, the plugin has no callable surface. The firewall has nothing to dispatch. |
| `capabilities` | required | — | Audit trail. Without declared capabilities, "what authority did this plugin exercise" is unanswerable. |
| `permissions` | required | — | Same as capabilities, for external systems. The trust UX (Q00/ouroboros-plugins#9) is built around this list. |
| `entrypoint` | required | — | Subprocess launcher in Q00/ouroboros#729 needs a launch command. Even with the "command" type being the only allowed option today, the value is real. |
| `description` | optional | `""` | No code reads it; pure human documentation. Empty string is a valid default. |
| `audit` | optional | `{ "events": ["plugin.invoked", "plugin.permission_used", "plugin.completed", "plugin.failed"] }` | The firewall emits 4 standard events for every invocation. The manifest opts in to *additional* events only when needed. |

When this manifest changes (new field added, or a field's required-status
flips), bump the schema version per Q00/ouroboros-plugins#11.

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
- The lifecycle audit events `plugin.discovered`, `plugin.installed`,
  and `plugin.trusted` are **not** emitted for first-party programs,
  because they bypass the `discovered → installed → trusted` flow at
  core boot. The runtime events `plugin.invoked`,
  `plugin.permission_used`, `plugin.completed`, and `plugin.failed`
  are emitted normally.

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

See `docs/audit.md` and `schemas/0.1/audit-event.schema.json`.

## Versioning

The plugin manifest schema and the audit-event schema both follow
**SemVer-style `MAJOR.MINOR`** versioning. A schema bumps independently
of the other.

### What is breaking (MAJOR bump)

- Removing a field
- Renaming a field
- Removing a value from an `enum`
- Tightening a `pattern` so previously valid values become invalid
- Making an optional field required

### What is non-breaking (MINOR bump)

- Adding a new optional field
- Adding a new value to an `enum`
- Loosening a `pattern`
- Adding a new event type to `audit-event.schema.json`

### Bump cadence

On every applicable change. Do not batch breaking changes; each MAJOR
is a single deliberate decision.

### Support window

**Current MAJOR + previous MAJOR** (i.e. 2 MAJORs at any time). Anything
older is unsupported. The deprecation deadline for a MAJOR is announced
in this section when the next MAJOR ships.

### Storage layout

Schemas are archived per MAJOR:

```
schemas/
  0.1/
    plugin.schema.json
    audit-event.schema.json
  1.0/                      # when MAJOR 1 ships
    ...
```

`scripts/validate_contract.py` reads each manifest's `schema_version`
field and routes to the matching `schemas/<major>/plugin.schema.json`.
A manifest declaring an unsupported version is rejected with a clear
message naming the supported window.

### Migration

For the v0 → v1 transition (the first breaking transition), a manual
migration guide will live at `docs/migrations/0-to-1.md`. Automated
migration scripts are out of scope for v0; add when ecosystem size
demands.

### Independence between schemas

The manifest schema and the audit-event schema bump independently. A
manifest using `schema_version: "0.1"` may emit audit events using
`schema_version: "0.2"` if both are within their respective support
windows. The audit-event schema's `schema_version` field on each event
is the authoritative version marker.

This is the resolution of Q00/ouroboros-plugins#11.

## Non-goals

- No public registry in v1
- No auto-update in v1
- No implicit destructive permission grants
- No arbitrary mutation of core state
