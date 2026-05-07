# Plugin Lifecycle

The MVP lifecycle is local-only. It supports explicit local paths and a managed
plugin home, but no remote registry or auto-update.

## Sources

```text
local_path
  A user points the manager at a local plugin directory.

plugin_home
  A plugin is installed under ~/.ouroboros/plugins/<name>.

first_party
  A UserLevel program shipped with Ouroboros itself.
```

Remote package resolution is out of scope for the MVP.

## States

```text
discovered
  The manifest can be inspected, but the plugin cannot run.

installed
  The plugin is registered or copied into plugin_home, but sensitive
  permissions are not granted.

trusted
  The user or policy granted specific scopes. Trust is scoped, not global.

disabled
  The plugin is installed but cannot run until re-enabled.

blocked
  Policy forbids execution.

first_party
  Reserved for programs shipped with Ouroboros. First-party programs still
  declare capabilities so they remain auditable.
```

## Commands

MVP command shape:

```bash
ouroboros plugin discover ./plugins/github-pr-ops
ouroboros plugin install ./plugins/github-pr-ops
ouroboros plugin inspect github-pr-ops
ouroboros plugin trust github-pr-ops --scope github:read
ouroboros plugin disable github-pr-ops
ouroboros plugin remove github-pr-ops
```

`discover` and `inspect` must not grant trust.

`install` must not grant destructive permissions.

`trust` grants named scopes only.

## Namespace Rules

Plugins own command namespaces such as `github-pr`.

The manager must reject collisions by default:

```text
github-pr already owned by github-pr-ops@0.1.0
```

An explicit override can be designed later, but should be auditable.

## Non-goals

- No remote registry
- No dependency resolver
- No auto-update
- No install-time destructive trust
- No implicit namespace override
