# Architecture

Ouroboros plugins are UserLevel programs built on top of Ouroboros core
primitives.

The architecture separates three layers:

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
|                                                                   |
|  Product-level workflows maintained with Ouroboros, but still      |
|  programs above core rather than core itself.                      |
+-------------------------------+-----------------------------------+
                                |
                                | stable OS primitives
                                v
+-------------------------------------------------------------------+
|                         Ouroboros Core / OS                         |
|                                                                   |
|  Seed      Ledger      State      Runtime      MCP                 |
|  Provenance  Safety Boundaries  Progress/Status  Handoff           |
+-------------------------------+-----------------------------------+
                                |
                                | bounded adapters / external calls
                                v
+-------------------------------------------------------------------+
|                    External Systems / Runtimes                      |
|                                                                   |
|  GitHub   Jira   Linear   Slack   CI   Local repo   Agent CLIs      |
+-------------------------------------------------------------------+
```

## Core

Core provides stable primitives:

- Seed
- Ledger
- State
- Runtime
- MCP
- Provenance
- Safety
- Execution handoff
- Progress, recovery, and status

Core should not encode every domain workflow directly.

## First-party UserLevel Programs

`ooo auto` is a first-party UserLevel program. It is not the core.

Its product boundary is:

```text
goal -> clarification/interview -> Seed -> validation -> execution handoff
```

Additional first-party programs can exist, but they should have explicit
product boundaries instead of expanding `ooo auto` indefinitely.

## Installable UserLevel Programs

Installable plugins are domain workflows that use core primitives through a
declared contract. They should own their namespace, permissions, and user
experience.

Examples:

- `github-pr-ops`
- `merge-assistant`
- `jira-sync`
- `linear-triage`
- `slack-incident`
- `release-coordinator`

## Design Principle

When evaluating a new workflow, ask:

1. Is this an OS primitive?
2. Is this part of an existing first-party UserLevel program boundary?
3. Or should it be a separate installable UserLevel program?
