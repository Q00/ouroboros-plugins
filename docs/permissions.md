# Permissions And Trust

Plugins are UserLevel programs. Many will want access to external systems such
as GitHub, Jira, Slack, CI, local repositories, and shell commands.

That makes the plugin manager a permission boundary, not just an installer.

## Principles

- Installing a plugin does not grant trust.
- Trust is **explicit, scoped, and auditable**.
- Destructive permissions are never enabled by default.
- Core capability access is declared separately from external permission access.
- Every invocation leaves provenance and audit records.

## Trust States

```text
installed    Plugin files are present but no permissions are granted.
trusted      User granted one or more scopes.
disabled     Plugin is installed but cannot run.
blocked      Plugin is blocked by policy.
first_party  Program ships with Ouroboros (see lifecycle.md "first_party flow"
             — these skip discovered → installed → trusted entirely).
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

## Permission scope grammar

Scopes are **exact strings**. Parent scopes do **not** imply children.

- `github:pull_request:write` is granted by exactly `github:pull_request:write`, never by the prefix `github:pull_request`.
- A scope's segments (`<service>:<resource>:<action>`) are organizational hints; the manager treats the full string as opaque.

This is the resolution of question 3 below.

---

The rest of this document answers the 6 questions that arise the moment a
plugin declares a destructive `required: true` permission. Each subsection
contains a **Decision**, a **Rationale**, and a **Worked example** so the
behavior is testable. These answers are the resolution of
[Q00/ouroboros-plugins#9](https://github.com/Q00/ouroboros-plugins/issues/9).

## Q1 — Default behavior on first invoke without trust

**Decision**: Refuse with a clear error pointing to the exact `trust` command.
Do **not** prompt interactively at the call site.

**Rationale**: Interactive prompts during plugin invocation create a coercion
surface — a malicious or buggy plugin could phrase the prompt to trick the
user. Forcing the user to issue a separate, deliberate
`ouroboros plugin trust ...` command keeps trust grants out of the plugin's
own UI. The error message must name the exact missing scope and the exact
command to grant it; no implicit retries.

**Worked example**:

```bash
$ ooo plugin add ./hypothetical-merge-assistant
Installed: hypothetical-merge-assistant 0.1.0
Required scopes (declared in manifest):
  - github:pull_request:write (destructive)

$ ooo merge-assistant merge https://github.com/Q00/ouroboros/pull/725
Error: plugin requires `github:pull_request:write` (destructive),
       which is not yet trusted. Run:
       ooo plugin trust hypothetical-merge-assistant --scope github:pull_request:write
exit 1
# Ledger emits:
#   plugin.failed (status=blocked, message references missing scope)
# NO plugin.invoked emitted (per Q00/ouroboros#729 firewall early-return rule).
```

## Q2 — `command.requires_confirmation` AND `permission.risk: destructive` — how many prompts?

**Decision**: **One prompt per invocation**, governed by the **command-level**
`requires_confirmation` flag (the user-visible action). Permission risk gates
*whether trust was granted at all*, not per-invocation confirmation.

**Rationale**: Two prompts for the same intent is noise. The command-level
flag answers the user-facing "are you sure?"; permission risk has already
been handled when the user explicitly granted destructive scope via
`ouroboros plugin trust`. Surfacing a second prompt at every call would
train users to dismiss prompts reflexively.

**Worked example**:

```bash
$ ooo plugin trust hypothetical-merge-assistant --scope github:pull_request:write
Granted: github:pull_request:write (destructive). Recorded in ledger.

$ ooo merge-assistant merge https://github.com/Q00/ouroboros/pull/725
This command is destructive and requires confirmation.
Plugin: hypothetical-merge-assistant 0.1.0
Action: merge https://github.com/Q00/ouroboros/pull/725
Continue? [y/N] y
# Single confirmation. Then plugin invokes; firewall emits the standard
# event sequence (plugin.invoked, plugin.permission_used,
# plugin.completed/failed).
```

## Q3 — Trust scope expression: parent scope implies child?

**Decision**: **Exact-scope only**. `--scope github:pull_request` does NOT
imply `github:pull_request:write`. Each leaf scope must be granted
explicitly.

**Rationale**: Implicit children are how `sudo` gets into trouble — broad
grants surprise users. Exact-scope is verbose but transparent. Plugin authors
who feel the verbosity should split their plugin into smaller scopes, not ask
the manager to grant more.

**Worked example**:

```bash
$ ooo plugin trust X --scope github:pull_request
Granted: github:pull_request

$ ooo X merge ...
Error: plugin requires `github:pull_request:write`, which is not yet
       trusted. (Note: `github:pull_request` is granted but does not
       imply child scopes.)
       Run: ooo plugin trust X --scope github:pull_request:write
```

## Q4 — Re-trust on version bump

**Decision**: **Trust is invalidated on any version bump**. The user must
re-grant scopes for the new version explicitly.

**Rationale**: A new version may declare new scopes or change the meaning of
existing ones (e.g. broaden what `github:read` actually reads). One extra
trust step on upgrade is cheap; silent permission drift is not.

**Worked example**:

```bash
# Currently: plugin X@0.1.0 trusted with github:read
$ ooo plugin update X
Updated: X 0.1.0 → 0.2.0
Trust state reset. Previously granted scopes:
  - github:read (re-grant required)
New scopes declared:
  - github:read (was granted in 0.1.0)
  - github:repo:read (new in 0.2.0; never granted)
Run `ooo plugin trust X --scope github:read --scope github:repo:read`
to re-grant.

$ ooo X some-command ...
Error: plugin requires `github:read`, which is not trusted (version bump
       invalidated previous grant).
       Run: ooo plugin trust X --scope github:read
```

The `plugin.trusted` event for the new grants names `version="0.2.0"` so
the audit trail shows the trust was issued against the new version.

## Q5 — Trust storage: per-user vs per-repo

**Decision**: **Per-user**, at `~/.ouroboros/plugins/<name>/trust.json`.

**Rationale**: Plugin installation is already per-user
(`~/.ouroboros/plugins/<name>/`); trust scoped to the same axis is
consistent. Per-repo trust would mean re-granting every time a user clones
a new project, which is poor UX without a clear security win — the threat
model is "this plugin is doing too much," not "this plugin is doing too
much in this specific repo." If a real per-repo policy use case appears,
add it as an opt-in policy file later.

**Worked example**:

```bash
$ ooo plugin trust X --scope github:read
Wrote: ~/.ouroboros/plugins/X/trust.json
{
  "schema_version": "0.1",
  "plugin": "X",
  "version": "0.1.0",
  "granted_scopes": [
    {
      "scope": "github:read",
      "granted_at": "2026-05-07T12:00:00Z",
      "granted_by": "user:shaun0927"
    }
  ]
}
```

## Q6 — `plugin.trusted` audit event required fields

**Decision**: The `plugin.trusted` event uses the same envelope as every
other audit event (per `schemas/0.1/audit-event.schema.json`). The
`provenance` map carries `granted_by` and `granted_scope` as bounded
string values per `docs/audit.md`.

**Rationale**: Reconstruction of "who granted what when" must be possible
from the ledger alone, without a separate trust-history store. Both fields
are bounded strings — no token leakage risk.

**Worked example**:

```json
{
  "schema_version": "0.1",
  "event_type": "plugin.trusted",
  "occurred_at": "2026-05-07T12:00:00Z",
  "plugin": {
    "name": "hypothetical-merge-assistant",
    "version": "0.1.0",
    "source_type": "plugin_home"
  },
  "command": {
    "namespace": "trust",
    "name": "grant",
    "argv": ["--scope", "github:pull_request:write"]
  },
  "trust_state": "trusted",
  "capabilities_used": [],
  "permissions_used": [],
  "result": {
    "status": "success",
    "message": "Granted scope github:pull_request:write"
  },
  "provenance": {
    "granted_by": "user:shaun0927",
    "granted_scope": "github:pull_request:write"
  }
}
```

## Example flow (end-to-end)

```bash
ouroboros plugin add ./plugins/github-pr-ops
ouroboros plugin inspect github-pr-ops
ouroboros plugin trust github-pr-ops --scope github:read
# (No second `trust` line for github:pull_request:write — that scope is
# `required: false` on github-pr-ops; merge is removed in v0 per
# Q00/ouroboros-plugins#7.)
```
