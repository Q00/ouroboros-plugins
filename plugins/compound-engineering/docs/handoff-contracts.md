# Compound Engineering handoff contracts

Each adapter invocation produces a JSON run envelope with these stable fields:

- `plugin`: adapter name and version
- `command`: namespace, command name, and argv
- `input`: sanitized input text
- `source`: upstream repository, version, skill, and vendored skill asset path
- `risk`, `status`, and `message`
- `capabilities_used`, `permissions_used`, and `required_permissions`
- `artifacts`: command artifact, run result JSON, and audit event JSON
- `handoff`: summary, next recommended command, downstream target, and resumability guidance
- `audit.provenance`: bounded reconstructable provenance

The audit event JSON conforms to `schemas/0.1/audit-event.schema.json`.
