# Permissions And Trust

Plugins are UserLevel programs. Many will want access to external systems such
as GitHub, Jira, Slack, CI, local repositories, and shell commands.

That makes the plugin manager a permission boundary, not just an installer.

## Principles

- Installing a plugin does not grant trust.
- Trust should be explicit, scoped, and auditable.
- Destructive permissions should never be enabled by default.
- Core state access should be declared separately from external permissions.
- Every invocation should leave provenance and audit records.

## Trust States

Draft trust states:

```text
installed    Plugin files are present but no permissions are granted.
trusted      User granted one or more scopes.
disabled     Plugin is installed but cannot run.
blocked      Plugin is blocked by policy.
first_party  Program ships with Ouroboros but still declares capabilities.
```

## Example Flow

```bash
ouroboros plugin add ./plugins/github-pr-ops
ouroboros plugin inspect github-pr-ops
ouroboros plugin trust github-pr-ops --scope github:read
ouroboros plugin trust github-pr-ops --scope github:pull_request:write
```

## Capability vs Permission

Capabilities describe access to Ouroboros core primitives:

```text
ledger:write
state:write
provenance:write
handoff:attach
```

Permissions describe external system access:

```text
github:read
github:pull_request:write
shell:execute
filesystem:write
```

This split matters because a plugin can be safe with respect to external
systems while still needing careful control over core state, or vice versa.

## Policy Questions

- Should trust be per user, per repo, or global?
- Should destructive scopes require confirmation on every run?
- Should plugins be able to request additional scopes at runtime?
- Should local plugins and registry plugins have different default trust?
