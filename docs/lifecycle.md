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

Distribution shape: **local path + git URL only**. Hosted package
registries, marketplace search, and auto-update are explicit non-goals
(see `Non-goals` below and Q00/ouroboros#725 for the framing).

## Repository-URL Source

`ouroboros plugin add <repo-url>` is the canonical install path. The repo URL
is the **unit of distribution**; the catalog inside the repo is the
**unit of selection**. The manager:

1. Performs a shallow clone (`git clone --depth 1`) of the repo into a
   cache directory under `~/.ouroboros/cache/`.
2. Reads each `plugins/<name>/ouroboros.plugin.json` in the repo to build
   a catalog.
3. Prompts the user to select one or more plugins (multi-select).
4. Installs each selected plugin into `~/.ouroboros/plugins/<name>/` and
   records it in `~/.ouroboros/plugins.lock`.

Interactive flow:

```text
$ ouroboros plugin add https://github.com/Q00/ouroboros-plugins

Repository: Q00/ouroboros-plugins (b3a91f2)

Select plugins to install:

  [ ] autoresearch       0.1.0   prepare autoresearch handoffs for ooo auto
  [x] github-pr-ops      0.1.0   review and prepare PR merges
  [ ] release-coordinator 0.1.0   coordinate changelog and rollout
  [ ] issue-triage        0.1.0   classify product/engineering issues

Press space to toggle, enter to confirm, esc to cancel.
```

Non-interactive form for scripts and CI:

```bash
ouroboros plugin add https://github.com/Q00/ouroboros-plugins --plugin autoresearch
ouroboros plugin add https://github.com/Q00/ouroboros-plugins --plugin github-pr-ops
ouroboros plugin add https://github.com/Q00/ouroboros-plugins --plugin github-pr-ops --plugin release-coordinator
```

Local path source still works for development and offline use:

```bash
ouroboros plugin add . --plugin autoresearch
ouroboros plugin add . --plugin github-pr-ops
```

### Catalog convention

For a repo to be installable via `ouroboros plugin add <repo-url>`:

- Top-level `plugins/` directory.
- Each immediate subdirectory of `plugins/` is one plugin and contains
  an `ouroboros.plugin.json`.
- Optional `catalog/index.json` (or `registry/index.json` pre-rename)
  may carry a curated ordering / metadata for the prompt.

Plugins outside `plugins/` are ignored by the catalog reader.

## Anti-patterns

The manager **rejects** install strings that leak repository layout into
the user-visible URL. Examples that are explicitly unsupported:

```bash
# Subdirectory-leaking install string — rejected with a clear error.
ouroboros plugin add git+https://github.com/Q00/ouroboros-plugins.git#plugins/github-pr-ops
```

Error message:

```text
error: subdirectory-form install strings (#plugins/...) are not supported.
       Use 'ouroboros plugin add <repo-url> --plugin <name>' instead.
```

Why: the repository URL is the unit of distribution. Coupling the install
string to internal directory layout makes plugin authors unable to refactor
their repos without breaking installs.

Other unsupported forms:

```bash
# Trying to "install" the catalog file directly.
ouroboros plugin add https://github.com/Q00/ouroboros-plugins/blob/main/catalog/index.json   # rejected

# Bare PyPI-style names (no remote package registry exists).
ouroboros plugin add github-pr-ops   # rejected unless ./github-pr-ops or similar is a path
```

## States

```text
discovered
  The manifest can be inspected, but the plugin cannot run.

installed
  The plugin is registered or copied into plugin_home, but sensitive
  permissions are not granted.

trusted
  The user or policy granted specific scopes. Trust is scoped, not global.
  Trust is stored per-user at ~/.ouroboros/plugins/<name>/trust.json.
  Trust is invalidated by any version bump (re-grant required after
  `ouroboros plugin update`). See docs/permissions.md Q4 and Q5.

disabled
  The plugin is installed but cannot run until re-enabled.

blocked
  Policy forbids execution.

first_party
  Reserved for programs shipped with Ouroboros (e.g. `ooo auto`).
  First-party programs are registered at core boot, NOT through
  `discovered → installed → trusted`. They still declare capabilities
  and permissions so they remain auditable, but no user-issued
  `ouroboros plugin trust` step is needed.

  Consequences:
    - `ouroboros plugin add` refuses any source resolving to first_party.
    - The lifecycle audit events plugin.discovered, plugin.installed,
      and plugin.trusted are not emitted for first-party programs
      (the discovery / install / trust steps are skipped). The
      runtime events plugin.invoked, plugin.permission_used,
      plugin.completed, plugin.failed are emitted normally.

  See docs/contract.md "first_party flow" for the manifest-sharing
  rationale.
```

## Commands

MVP command shape:

```bash
ouroboros plugin add <repo-url>                       # multi-select prompt
ouroboros plugin add <repo-url> --plugin <name>       # non-interactive
ouroboros plugin add ./plugins/github-pr-ops          # local-path source
ouroboros plugin discover ./plugins/github-pr-ops
ouroboros plugin install ./plugins/github-pr-ops
ouroboros plugin inspect github-pr-ops
ouroboros plugin list
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
