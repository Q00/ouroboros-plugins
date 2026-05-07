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
- `commands`
- `capabilities`
- `permissions`
- `entrypoint`

## Commands

Plugins own command namespaces.

Example:

```json
{
  "namespace": "github-pr",
  "commands": [
    {
      "name": "review",
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

- `seed:read`
- `seed:write`
- `ledger:read`
- `ledger:write`
- `state:read`
- `state:write`
- `provenance:write`
- `runtime:execute`
- `mcp:call`
- `handoff:attach`

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

## Non-goals

- No public registry in v1
- No auto-update in v1
- No implicit destructive permission grants
- No arbitrary mutation of core state
