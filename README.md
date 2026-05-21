# Ouroboros Plugins

UserLevel plugin ecosystem for Ouroboros.

Ouroboros core should provide stable OS primitives. Plugins and first-party
programs compose those primitives into domain-specific workflows.

```text
+-------------------------------------------------------------------+
|                Installable UserLevel Programs                      |
|                                                                   |
|  autoresearch    github-pr-ops   merge-assistant   jira-sync       |
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
- Anthropic Agent Skills assimilation reference plugin for `anthropics/skills`

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
- Autoresearch experiment handoff
- Merge assistance
- Jira/Linear synchronization
- Slack incident workflows
- Release coordination
- Customer debugging playbooks

## Example UX

```bash
ouroboros plugin add https://github.com/Q00/ouroboros-plugins --plugin autoresearch
ouroboros plugin add https://github.com/Q00/ouroboros-plugins --plugin github-pr-ops
ouroboros plugin trust github-pr-ops --scope github:read --scope github:pull_request:write

ooo auto-research prepare /path/to/autoresearch --goal "Improve validation bpb"
ooo github-pr review https://github.com/org/repo/pull/123
ooo github-pr merge --policy team-default
```

Ouroboros `v0.39.1+` prompts for non-destructive required permissions during
`plugin add`, so `autoresearch` can grant `filesystem:read` and
`filesystem:write` during install. Destructive scopes, including PR write
scopes, still require an explicit `plugin trust` command.

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
  anthropic-agent-skills/ Anthropic Agent Skills assimilation reference plugin
  autoresearch/        Autoresearch-to-ooo-auto handoff plugin
  github-pr-ops/       Reference plugin skeleton
catalog/
  index.json           Local catalog (boring index for reproducibility,
                       NOT a package-registry server)
```

## Validate

A `contract-validation` GitHub Actions workflow runs the validator on every pull request and on pushes to `main`. To run it locally:

```bash
pip install -r requirements-dev.txt
python3 scripts/validate_contract.py
PYTHONPATH=plugins/autoresearch python3 -m ouroboros_autoresearch inspect /path/to/autoresearch
PYTHONPATH=plugins/autoresearch python3 -m ouroboros_autoresearch prepare /path/to/autoresearch --goal "Improve validation bpb"
PYTHONPATH=plugins/github-pr-ops python3 -m github_pr_ops review https://github.com/Q00/ouroboros/pull/1
```

During plugin development, install from the local checkout instead:

```bash
ouroboros plugin add . --plugin autoresearch
```

The first step is required: `validate_contract.py` imports `jsonschema` from
`requirements-dev.txt`. On a clean checkout, skipping it makes the validator
exit `2` with a "jsonschema is required" message.

## Status

Draft. This repository is for shaping the contract before committing to a
full package registry or marketplace.
