# Superpowers AgentOS Assimilation RFC

Issue: [Q00/ouroboros-plugins#28](https://github.com/Q00/ouroboros-plugins/issues/28)
Consensus context: [Q00/ouroboros-plugins#27](https://github.com/Q00/ouroboros-plugins/issues/27)

## PR plan and implementation scope

This epic should be merged as **five PRs**. Each PR is independently reviewable,
keeps schema risk bounded, and composes into the complete AgentOS assimilation
case.

1. **PR 1 — RFC/design and v0 boundaries**
   - Add this RFC and the plugin README boundary language.
   - Decide the reference-plugin location: `plugins/superpowers` in this repo.
   - Lock the namespace: `superpowers`.
   - Lock v0 behavior: non-destructive handoff generation only; no merge, push,
     branch deletion, discard, PR mutation, or firewall bypass.

2. **PR 2 — Manifest and skeleton command router**
   - Add `plugins/superpowers/ouroboros.plugin.json` under schema `0.1`.
   - Add `python -m superpowers_ouroboros` with `list`, `inspect`, `run`, and
     `prepare-handoff`.
   - Expose each upstream skill as `ooo superpowers <skill>` in the manifest.
   - Validate with `python3 scripts/validate_contract.py`.

3. **PR 3 — Pinned upstream discovery and command map**
   - Vendor a pinned `obra/superpowers` snapshot under
     `plugins/superpowers/vendor/superpowers`.
   - Parse `SKILL.md` frontmatter instead of hardcoding descriptions.
   - Generate `.omx/superpowers/skill-index.json` with upstream repo, version,
     commit, license, command, risk, capabilities, and permissions.
   - Test that no vendored upstream skill is missing from the command map.

4. **PR 4 — Handoff, audit, and provenance generation**
   - For every skill command, create a resumable run directory under
     `.omx/superpowers/runs/<run-id>/`.
   - Emit `invocation.json`, `provenance.json`, `handoff.md`, `seed.md`,
     `evidence.json`, and `audit.jsonl`.
   - Ensure each handoff states purpose, inputs, required capabilities,
     permissions, expected artifacts, verification evidence, and continuation.
   - Keep destructive upstream workflows report-only in v0.

5. **PR 5 — Tests, docs, and final integration hardening**
   - Add tests for manifest validation, skill coverage, risk classification,
     representative handoff generation, audit/provenance shape, and destructive
     exclusion.
   - Update `catalog/index.json`.
   - Document why this is Ouroboros-native assimilation rather than a thin prompt
     wrapper.


## Alignment with issue #27

This reference plugin is intentionally scoped to the consensus in #27:

- **Contract/reference repository, not marketplace** — `plugins/superpowers` is
  included because it proves an external agent methodology can be assimilated
  through the contract. It is not a request to host arbitrary third-party
  plugins here.
- **Not a thin wrapper** — commands produce inspectable metadata, permission
  plans, Seed-compatible handoffs, audit events, and provenance instead of just
  printing upstream prompts.
- **Capabilities vs permissions stay distinct** — capabilities describe
  Ouroboros primitives such as Seed, ledger, state, provenance, handoff, and
  progress; permissions describe external filesystem/shell/network authority.
- **Risk taxonomy is preserved** — v0 commands that write `.omx/superpowers`
  artifacts are `write`; destructive upstream branch operations are excluded
  rather than hidden behind a write-risk command.
- **Lifecycle/trust/firewall boundary remains intact** — install/trust semantics
  belong to Ouroboros. The plugin only declares commands, required scopes, and
  safe continuation artifacts.
- **`ooo auto` boundary is preserved** — Superpowers-specific branching remains
  in the plugin; downstream `ooo auto`, `$ralph`, or `$team` may consume the
  prepared handoffs.

## Architecture boundary

`superpowers` is a reference plugin, not a marketplace and not core runtime
logic. It demonstrates that an external agent methodology can become a
permissioned, inspectable, auditable UserLevel capability.

The adapter separates:

- **Skill discovery** from vendored upstream `SKILL.md` frontmatter.
- **Command declaration** in the v0.1 plugin manifest.
- **Permission planning** by command risk and future execution needs.
- **Execution handoff** through Seed-compatible artifacts.
- **Audit/provenance** through per-run JSON/JSONL artifacts.
- **Verification** through command-specific evidence contracts.

## V0 non-destructive policy

`finishing-a-development-branch` may describe destructive upstream options, but
v0 only prepares a completion report. Actual merge, discard, push, PR mutation,
or branch deletion requires a future destructive command declaration and trust UX.

## Schema decision

The current v0.1 manifest contract is sufficient for v0. Each upstream skill is
represented as a command entry and richer bundle metadata is emitted in generated
artifacts. Future schema work should be proposed only after this reference path
proves a concrete need.
