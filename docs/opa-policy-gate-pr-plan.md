# Issue #45 OPA policy gate PR plan

Issue: <https://github.com/Q00/ouroboros-plugins/issues/45>

The epic should land as a three-PR stack. Each PR is independently reviewable
and keeps the native OPA UX as the source of truth.

## PR 1 — Contract alignment, docs, manifest, examples

Branch/worktree: `feat/issue45-opa-pr1-contract` / `ouroboros-plugins-issue45-pr1`

Scope:

- Add `plugins/opa-policy-gate/ouroboros.plugin.json` with conservative v0
  commands: `eval`, `test`, `check`, `build-handoff`.
- Add README sections for native OPA UX preservation, v0 exclusions,
  permissions, bounded artifacts, reproduction, and #27/#45 alignment.
- Add minimal package entrypoint and example Rego/data/input/config fixtures.
- Add catalog/README references so the plugin is discoverable.
- No manifest schema expansion.

Exit criteria:

- Manifest validates with schema `0.1`.
- Existing tests pass.
- Runtime bridge may still return `blocked` because PR 2 owns execution.

## PR 2 — Bounded OPA CLI bridge and AgentOS artifacts

Branch/worktree: `feat/issue45-opa-pr2-bridge` / `ouroboros-plugins-issue45-pr2`

Scope:

- Replace the placeholder entrypoint with a bounded Python bridge.
- Parse repo-relative config files for `eval`, `test`, `check`, and
  `build-handoff`.
- Locate the installed `opa` binary and record OPA version.
- Build controlled OPA command lines; do not expose arbitrary passthrough.
- Enforce repo-relative input paths and write artifacts only below
  `.omx/artifacts/opa/`.
- Write raw stdout/stderr, normalized JSON result, provenance, handoff markdown,
  and `repro.sh`.
- Normalize exit code and OPA result semantics into `completed`, `failed`, and
  `blocked` with next actions.

Exit criteria:

- Commands are runnable via `PYTHONPATH=plugins/opa-policy-gate python3 -m opa_policy_gate ...`.
- Missing `opa` and invalid/out-of-bound requests produce blocked evidence.
- Existing contract validation still passes.

## PR 3 — Tests, hardening, and epic completion docs

Branch/worktree: `feat/issue45-opa-pr3-tests` / `ouroboros-plugins-issue45-pr3`

Scope:

- Add tests with a fake `opa` binary so CI does not require a local OPA install.
- Cover successful allow/deny eval, failing policy tests, invalid Rego/check
  failures, path traversal blocking, unsupported commands, missing binary,
  raw-output preservation, normalized artifact shape, and bounded build handoff.
- Add final README validation examples and note schema pressure points.
- Confirm no OPA-specific branching is required in Ouroboros core.

Exit criteria:

- `python3 scripts/validate_contract.py` passes.
- OPA plugin tests pass without network and without a real OPA install.
- Merging PRs 1→2→3 satisfies all issue #45 acceptance criteria for v0.

## #27 capability-assimilation alignment

Issue #45 is a concrete follow-up to issue #27, so each PR must preserve the
plugin-authoring SSOT constraints:

| #27 constraint | PR coverage |
|---|---|
| Core stays small; plugins assimilate external capability | PR 1 states OPA remains outside core and `ooo auto`; PR 2/3 keep OPA behavior in the plugin entrypoint only. |
| `ouroboros-plugins` is a curated contract/reference repo, not a marketplace | PR 1 justifies OPA as a reference plugin because it proves external policy-engine assimilation, not because OPA is merely useful. |
| A plugin is not just a command wrapper | PR 2 adds bounded config parsing, permission-aware path checks, provenance, normalized statuses, artifacts, and handoff rather than arbitrary passthrough. |
| Manifest is the minimum executable boundary | PR 1 uses schema `0.1` unchanged; richer artifact/upstream metadata stays in docs/config until schema pressure is proven. |
| Capabilities and permissions stay distinct | PR 1 manifest declares core capabilities separately from `filesystem:*` and `shell:execute` permissions. |
| Lifecycle/trust/firewall behavior is explicit | PR 1/2 document blocked states for missing OPA, untrusted/missing permission, out-of-bound paths, and unsupported commands. |
| Audit, provenance, and handoff make assimilation safe | PR 2 writes raw output, normalized result, provenance, handoff, and reproduction command for every successful OPA invocation. |
| `ooo auto` remains coherent and consumes handoffs | PR 1/2 expose policy evidence/handoff; they do not add OPA-specific routing to `ooo auto`. |
| Reference plugins must prove a contract boundary | The stack proves a policy-engine assimilation pattern, validation/handoff pattern, and audit/provenance pattern for mature OSS tools. |
| Schema expands only with demonstrated need | PR 3 records schema pressure points but intentionally does not expand the manifest schema in v0. |

A PR in this stack is not merge-ready if it weakens any of those #27
boundaries, especially by adding arbitrary command passthrough, implicit network
or server behavior, marketplace positioning, or OPA-specific core branching.

## Final implemented branches

- PR 1 branch: `feat/issue45-opa-pr1-contract` — docs, manifest, catalog, examples.
- PR 2 branch: `feat/issue45-opa-pr2-bridge` — bounded bridge and artifacts.
- PR 3 branch: `feat/issue45-opa-pr3-tests` — fake-OPA tests and final docs hardening.

Merge order must be PR 1 → PR 2 → PR 3. After PR 3, issue #45 v0 acceptance
criteria are covered without OPA-specific Ouroboros core changes and without
manifest schema expansion.
