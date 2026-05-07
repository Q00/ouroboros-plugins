# Ouroboros Plugins

UserLevel plugin ecosystem for Ouroboros.

Ouroboros core should provide stable OS primitives. Plugins and first-party
programs compose those primitives into domain-specific workflows.

```text
+-------------------------------------------------------------------+
|                Installable UserLevel Programs                      |
|                                                                   |
|  github-pr-ops   merge-assistant   jira-sync   linear-triage       |
|  slack-incident  release-coordinator  customer-debugger  ...       |
+-------------------------------+-----------------------------------+
                                |
                                | plugin contract / declared scopes
                                v
+-------------------------------------------------------------------+
|                First-party UserLevel Programs                      |
|                                                                   |
|  ooo auto     ooo run     ooo pm     ooo review?     ...           |
+-------------------------------+-----------------------------------+
                                |
                                | stable OS primitives
                                v
+-------------------------------------------------------------------+
|                         Ouroboros Core / OS                         |
|                                                                   |
|  Seed      Ledger      State      Runtime      MCP                 |
|  Provenance  Safety Boundaries  Progress/Status  Handoff           |
+-------------------------------------------------------------------+
```

## Repository Purpose

This repository is the home for the UserLevel plugin contract and reference
plugin packages. It is intentionally not a registry server yet.

The initial goal is a local-only contract MVP:

- Plugin manifest format
- Command namespace declaration
- Core capability declaration
- External permission declaration
- Provenance and audit requirements
- Example UserLevel plugin package

## Core Boundary

Ouroboros core owns primitives:

- Seed generation and validation
- Ledger and evidence/provenance tracking
- Durable workflow state
- Runtime/provider abstraction
- MCP tool surfaces
- Safety boundaries and permission checks
- Progress, recovery, and status reporting
- Execution handoff and result attachment

Plugins own domain-specific workflows:

- GitHub PR operations
- Merge assistance
- Jira/Linear synchronization
- Slack incident workflows
- Release coordination
- Customer debugging playbooks

## Example UX

```bash
ouroboros plugin add ./plugins/github-pr-ops
ouroboros plugin trust github-pr-ops --scope github:read,pull_request:write

ooo github-pr review https://github.com/org/repo/pull/123
ooo github-pr merge --policy team-default
```

## Layout

```text
docs/
  architecture.md      Layer model and design principles
  contract.md          Plugin contract MVP
  lifecycle.md         Local-only plugin lifecycle
  permissions.md       Permission and trust model
  audit.md             Audit and provenance event model
schemas/
  plugin.schema.json   Draft JSON Schema for plugin manifests
  audit-event.schema.json
plugins/
  github-pr-ops/       Reference plugin skeleton
registry/
  index.json           Local index placeholder
```

## Validate

```bash
python3 scripts/validate_contract.py
PYTHONPATH=plugins/github-pr-ops python3 -m github_pr_ops review https://github.com/Q00/ouroboros/pull/1
```

## Status

Draft. This repository is for shaping the contract before committing to a
full package registry or marketplace.
