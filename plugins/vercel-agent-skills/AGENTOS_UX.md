# AgentOS UX and assimilation contract

The Vercel Agent Skills pack is exposed as one curated AgentOS/Ouroboros plugin named `vercel-agent-skills`. The adapter intentionally treats `vercel-labs/agent-skills` as the assimilated external repository and `Q00/ouroboros-plugins` as the plugin contract/distribution surface.

## Natural-language routing

Runtime routers should map these requests to the explicit command surface, then let the adapter load only the selected upstream skill assets:

| User intent | Command |
| --- | --- |
| "Optimize my Vercel project" | `ooo vercel optimize <project-path>` |
| "Review this React component for performance" | `ooo vercel react-best-practices <path-or-glob>` |
| "Audit my UI for accessibility and UX" | `ooo vercel web-design-guidelines <file-or-glob>` |
| "Review this Expo screen" | `ooo vercel react-native-skills <path-or-glob>` |
| "Plan view transitions" | `ooo vercel react-view-transitions <path-or-glob> --mode plan` |
| "Review component composition" | `ooo vercel composition-patterns <path-or-glob>` |
| "Check Vercel token auth" | `ooo vercel cli-with-tokens preflight <project-path>` |
| "Deploy a preview" | `ooo vercel deploy-preview <project-path> --confirm` |

## Durable outputs

Each invocation writes:

- `handoff.json` for downstream AgentOS automation;
- `audit-event.json` compatible with `schemas/0.1/audit-event.schema.json`;
- command-specific reports such as `report.md`, `signals.json`, `gate.json`, `token-preflight.json`, or `deployment-plan.json`.

## PR chain for issue #36

1. Contract, vendored upstream snapshot, manifest, catalog, skeleton.
2. Read-only audit adapters and bounded handoff tests.
3. Vercel optimize metrics-first gate and blocked/limited semantics.
4. Token redaction, preview deployment gates, production block.
5. AgentOS UX docs, audit-event validation, and final smoke verification.

Merging the chain in order gives every upstream skill an explicit command, safety/risk semantics, provenance, audit, and handoff behavior.
