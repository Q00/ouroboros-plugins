# Issue #36 Vercel Agent Skills PR plan

Issue #36 is implemented as a stacked five-PR chain so the external `vercel-labs/agent-skills` repository is assimilated into AgentOS/Ouroboros through explicit contracts rather than through an unbounded prompt or shell wrapper.

## Merge order and scope

| PR | Branch | Scope |
| --- | --- | --- |
| PR 1 | `feat/issue36-vercel-agent-skills-pr1-contract` | Plugin package boundary, schema-valid manifest, catalog entry, README/UPSTREAM, upstream snapshot, entrypoint skeleton. |
| PR 2 | `feat/issue36-vercel-agent-skills-pr2-audits` | Read-only audit adapters, bounded path handling, upstream SKILL progressive disclosure, reports, handoff artifacts. |
| PR 3 | `feat/issue36-vercel-agent-skills-pr3-optimize` | `vercel optimize` metrics-first `signals.json`/`gate.json`/report pipeline and blocked/limited semantics. |
| PR 4 | `feat/issue36-vercel-agent-skills-pr4-deploy-safety` | Token preflight/redaction, preview deployment trust gate, production deployment block. |
| PR 5 | `feat/issue36-vercel-agent-skills-pr5-e2e` | AgentOS UX docs, audit-event emission/schema validation, final smoke/e2e coverage. |

## Alignment with issue #27 capability assimilation

Issue #27 defines `Q00/ouroboros-plugins` as a curated contract/reference repository, not a marketplace. It also defines plugins as the capability-assimilation layer that keeps core small while translating external tools into permissioned, auditable, handoff-capable Ouroboros capabilities.

This stack preserves those boundaries:

| #27 principle | Issue #36 implementation |
| --- | --- |
| Core stays small | No Vercel-specific behavior is added to Ouroboros core or `ooo auto`; all Vercel behavior lives in `plugins/vercel-agent-skills`. |
| Reference repo, not marketplace | The PR adds one curated reference assimilation package for the specifically analyzed upstream repository, not a general plugin marketplace. |
| Third-party repository is the distribution source | `UPSTREAM.md` and vendored `COMMIT` record `vercel-labs/agent-skills` at the observed commit; the plugin package is the adapter/distribution surface. |
| Not just a command wrapper | Commands emit bounded reports, `handoff.json`, provenance, permissions used, statuses, limitations, and downstream next actions. |
| Manifest is minimum executable boundary | `ouroboros.plugin.json` declares schema version, identity, commands, capabilities, permissions, entrypoint, risks, and audit events. |
| Capabilities and permissions stay distinct | Core capabilities (`ledger`, `provenance`, `state`, `handoff`, `progress`) are separate from external permissions (`filesystem:read`, `network:*`, `shell:execute`, `vercel:*`). |
| Shared risk taxonomy | Read-only audits and optimize are `read_only`; preview deployment is `write`; production deployment is `destructive` and blocked in v0. |
| Audit/provenance/handoff are required | Later PRs add machine-readable handoff and audit artifacts for executable runs. |
| Trust and safety gates | Network fetch failures, missing Vercel auth/project linkage, token handling, preview writes, and production deploy are explicit blocked/limited states. |

## Non-goals preserved

- No generic `ooo vercel run <anything>` shell wrapper.
- No implicit production deployment.
- No raw token persistence in stdout, audit, provenance, or handoff artifacts.
- No schema expansion unless a future concrete limitation is documented.
- No claim that `ouroboros-plugins` itself is the AgentOS ecosystem.
