# compound-engineering

AgentOS/Ouroboros adapter for [EveryInc/compound-engineering-plugin](https://github.com/EveryInc/compound-engineering-plugin).

This plugin packages Compound Engineering as a governed `ooo compound ...` capability instead of adding CE-specific behavior to Ouroboros core. It vendors upstream CE skill and agent prompt assets under `assets/` (MIT licensed; see `LICENSE.upstream.md`) and exposes every upstream CE skill as a schema-valid command.

## Install and trust UX

Install from this repository root, selecting the plugin by name rather than leaking the subdirectory path into user-facing install strings:

```bash
ouroboros plugin add . --plugin compound-engineering
```

The manifest declares `filesystem:read` as required and command-specific higher-risk scopes as optional until the schema supports command-scoped permissions. Grant only the scopes needed for the command you intend to run. Destructive commands also require explicit command confirmation.

## Core workflow

```bash
ooo compound brainstorm "make background job retries safer"
ooo compound plan .omx/compound/brainstorms/<artifact>.md
ooo compound work .omx/compound/plans/<artifact>.md
ooo compound code-review
ooo compound compound
```

The Python entrypoint can be smoke-tested directly:

```bash
PYTHONPATH=plugins/compound-engineering python3 -m compound_engineering --list-commands
PYTHONPATH=plugins/compound-engineering python3 -m compound_engineering brainstorm "test feature"
```

## Safety model

- No generic `compound run <anything>` shell wrapper is exposed.
- Each command maps to exactly one upstream CE skill.
- Read-only commands may write adapter audit/handoff artifacts under `.omx/compound`, but do not mutate project source or remote services.
- Write commands create bounded local artifacts unless the user grants additional command-specific permissions.
- Destructive commands are blocked by the adapter unless `--confirm` is supplied and the host has granted the relevant trust scopes.
- Secrets, raw tokens, and unbounded external payloads are not written to provenance.

## Durable outputs

Each invocation writes:

- a command artifact under `.omx/compound/<command-family>/`
- `.omx/compound/runs/<run-id>/result.json`
- `.omx/compound/runs/<run-id>/audit-event.json`

The result includes command name, input arguments, upstream repository/version/skill, generated files, used capabilities, permissions, risk, status, next recommended command, downstream handoff target, and bounded provenance.

## Commands

See `docs/command-mapping.md` for the complete 37-skill mapping and `docs/risk-matrix.md` for permission/risk details.
