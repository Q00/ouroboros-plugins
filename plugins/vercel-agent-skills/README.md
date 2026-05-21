# Vercel Agent Skills plugin

This plugin assimilates [`vercel-labs/agent-skills`](https://github.com/vercel-labs/agent-skills) into the AgentOS/Ouroboros plugin contract. It exposes Vercel Agent Skills through explicit `ooo vercel ...` commands, bounded permissions, risk semantics, provenance, and machine-readable handoff artifacts.

## Commands

- `ooo vercel optimize <project-path> [--project <id-or-name>] [--limited] [--out <dir>]`
- `ooo vercel react-best-practices <path-or-glob> [--format markdown|json]`
- `ooo vercel web-design-guidelines <file-or-glob> [--guidelines-url <url>] [--format markdown|json]`
- `ooo vercel react-native-skills <path-or-glob> [--format markdown|json]`
- `ooo vercel react-view-transitions <path-or-glob> [--mode audit|plan|implement]`
- `ooo vercel composition-patterns <path-or-glob> [--format markdown|json]`
- `ooo vercel cli-with-tokens preflight <project-path>`
- `ooo vercel cli-with-tokens env-check <project-path>`
- `ooo vercel deploy-preview <project-path> [--scope <team-slug>] [--claimable] [--no-wait] [--confirm]`
- `ooo vercel deploy-production <project-path>` is declared but disabled in v0.

## Artifact contract

Each command writes a run directory under `.ouroboros/plugins/vercel-agent-skills/runs/<run-id>/` unless `--out` is supplied. Runs include human-readable output and `handoff.json` with upstream provenance, risk, permissions used, status, artifacts, limitations, and next actions. Secrets are redacted before stdout, audit, or handoff persistence.

## Safety

Read-only commands never mutate project files. Preview deployment requires explicit confirmation and production deployment is blocked until destructive trust UX is available.
