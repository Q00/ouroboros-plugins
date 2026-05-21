# Hermes AgentOS assimilation plan

Issue: [Q00/ouroboros-plugins#40](https://github.com/Q00/ouroboros-plugins/issues/40)

## Confirmed PR series

The epic should land as **five PRs**. This keeps the trust boundary reviewable and lets each merge produce independently useful AgentOS capability surface.

1. **PR1 — Research and contract fit**
   - Scope: document Hermes surfaces, fixture assumptions, v0.1 manifest fit, schema pressure, and the rest of the PR series.
   - Deliverables: this document, representative fixtures, and a no-schema-expansion decision record.
   - Merge result: reviewers can see why Hermes belongs in `ouroboros-plugins` and how each later PR resolves a slice of #40.

2. **PR2 — `hermes-skill-assimilator` read-only inspector**
   - Scope: plugin manifest, `inspect`, `catalog`, SKILL.md/plugin.yaml parsing, risk/capability classification, reports, tests.
   - Out of scope: executing skill instructions or converting them into runnable Ouroboros workflows.
   - Merge result: Hermes skills and plugin metadata can be inspected safely under the existing v0.1 contract.

3. **PR3 — `hermes-skill-assimilator` conversion/handoff**
   - Scope: `convert`, `hermes-skill-report.md`, `hermes-skill-capability-map.json`, `seed-handoff.md`, `permission-review.md`, optional `ouroboros.plugin.draft.json`, deterministic tests.
   - Out of scope: auto-trusting generated artifacts or executing imported instructions.
   - Merge result: at least one Hermes skill can become an Ouroboros-readable handoff artifact with provenance and unresolved trust decisions.

4. **PR4 — `hermes-automation-adapter` cron/job bridge**
   - Scope: `hermes-cron inspect`, `import`, `plan`, schedule/prompt/skills/scripts/delivery/workdir/profile/repeat/no-agent preservation, Seed-compatible drafts, risk maps, tests.
   - Out of scope: scheduling, running, or delivering imported jobs by default.
   - Merge result: Hermes automations become reviewable Seed drafts without bypassing the plugin firewall.

5. **PR5 — `hermes-agent-runner` bounded runtime bridge and AgentOS polish**
   - Scope: bounded non-interactive `run`, `status`, `resume`, `stop`, `export`, conservative `chat` attach metadata, session state, transcript/handoff artifacts, docs/trust model, final verification.
   - Out of scope: unbounded background daemons, implicit provider/network trust, or hidden schema expansion.
   - Merge result: Hermes can run as an external AgentOS capability with Ouroboros provenance, resumability, cancellation metadata, and auditable outputs.

## v0.1 contract fit

The current manifest schema can represent the initial family without expansion:

- read/import plugins use `state`, `provenance`, `handoff`, and `progress` capabilities plus `filesystem:read`/`filesystem:write` permissions;
- the runner adds `runtime:execute`, `ledger:write`, and optional `network:*`/provider scopes only as declared permissions;
- current audit events (`plugin.invoked`, `plugin.permission_used`, `plugin.completed`, `plugin.failed`) are enough for v0 artifacts.

Potential future fields such as `session_lifecycle`, `timeouts`, `secrets`, `network_endpoints`, and `artifact_schema` remain documented schema pressure. They are **not** added until a reference implementation proves the existing capabilities, permissions, audit events, and handoff artifacts cannot carry the evidence.

## Fixture pinning

The repository fixtures intentionally pin a small Hermes-like subset instead of vendoring Hermes:

- `tests/fixtures/hermes-agent/skills/research/domain-intel/SKILL.md` covers frontmatter, setup notes, shell snippets, URLs, env vars, and file references.
- `tests/fixtures/hermes-agent/plugins/search/plugin.yaml` covers plugin metadata inspection.
- `tests/fixtures/hermes-agent/cron/jobs.json` covers schedule, prompt, skills, scripts, delivery target, workdir, profile, repeat policy, and no-agent mode.

These fixtures exercise the assimilation contract without copying the full Hermes runtime into this repository.

## Completion mapping to #40

Merging all five PRs resolves the epic acceptance criteria: safe inspection, skill conversion, cron import, bounded runtime supervision, resumable/auditable state, contract validation, and documentation that frames Hermes as an Ouroboros-native capability adapter rather than a generic command wrapper.
