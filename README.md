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
  migrations/          MAJOR-version schema migration guides (added when needed)
schemas/
  0.1/
    plugin.schema.json       Draft JSON Schema for plugin manifests (v0.1)
    audit-event.schema.json  Draft JSON Schema for audit events (v0.1)
plugins/
  github-pr-ops/       Reference plugin skeleton
catalog/
  index.json           Local catalog (boring index for reproducibility,
                       NOT a package-registry server)
```

## Validate

A `contract-validation` GitHub Actions workflow runs the validator on every pull request and on pushes to `main`. To run it locally:

```bash
# Install validator deps. requirements-dev.txt is added by
# Q00/ouroboros-plugins#13; until that lands, install jsonschema directly.
pip install -r requirements-dev.txt 2>/dev/null || pip install "jsonschema>=4.21"
python3 scripts/validate_contract.py
PYTHONPATH=plugins/github-pr-ops python3 -m github_pr_ops review https://github.com/Q00/ouroboros/pull/1
```

## Status

Draft. This repository is for shaping the contract before committing to a
full package registry or marketplace.
