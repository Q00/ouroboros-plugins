# Audit And Provenance

Plugins must be auditable because they compose core primitives and often touch
external operational systems.

## Event Shape

Audit events follow `schemas/0.1/audit-event.schema.json`. The
`schema_version` field on each event is the authoritative version
marker (see `docs/contract.md` "Versioning" — schemas are archived
per MAJOR).

Required fields:

- `schema_version`
- `event_type`
- `occurred_at`
- `plugin`
- `command`
- `trust_state`
- `capabilities_used`
- `permissions_used`
- `result`

## Event Types

```text
plugin.discovered
plugin.installed
plugin.trusted
plugin.invoked
plugin.permission_used
plugin.completed
plugin.failed
```

## Provenance

The provenance map is intentionally string-only for the MVP. Plugins should
record bounded, redacted facts such as:

```json
{
  "invoked_by": "direct",
  "source_platform": "cli",
  "request_correlation_id": "req_123"
}
```

Raw access tokens, raw user messages, channel IDs, and unbounded payloads should
not be written into provenance.

## Example Event

```json
{
  "schema_version": "0.1",
  "event_type": "plugin.invoked",
  "occurred_at": "2026-05-07T08:30:00Z",
  "plugin": {
    "name": "github-pr-ops",
    "version": "0.1.0",
    "source_type": "local_path"
  },
  "command": {
    "namespace": "github-pr",
    "name": "review",
    "argv": ["https://github.com/org/repo/pull/123"]
  },
  "trust_state": "trusted",
  "capabilities_used": ["ledger:write", "provenance:write"],
  "permissions_used": ["github:read"],
  "provenance": {
    "invoked_by": "direct",
    "source_platform": "cli"
  },
  "result": {
    "status": "success",
    "message": "PR review summary recorded."
  }
}
```

## `plugin.trusted` event

When the user runs `ouroboros plugin trust <name> --scope <s>`, a
`plugin.trusted` event is emitted with `granted_by` and `granted_scope`
in the provenance map (per Q00/ouroboros-plugins#9 Q6 lock):

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
    "granted_by": "user:<id>",
    "granted_scope": "github:pull_request:write"
  }
}
```

Both `granted_by` and `granted_scope` are bounded strings; no tokens or
free-form text is stored. Reconstruction of "who granted what when" is
possible from the ledger alone.

`plugin.trusted` is **not** emitted for first-party plugins (per
Q00/ouroboros-plugins#8 lock: first-party programs skip the trust grant
step entirely).

## Principle

If a plugin uses a core capability or external permission, the audit trail
should be able to explain why.
