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
