# semgrep-static-analysis

Assimilates [Semgrep](https://github.com/semgrep/semgrep) local static-analysis scans into Ouroboros as a first-class AgentOS capability while preserving Semgrep's CLI mental model.

This plugin is intentionally not a Semgrep fork, wrapper marketplace entry, or parser reimplementation. Semgrep remains the scanning engine. Ouroboros adds the AgentOS layer around it: explicit capabilities, permission declarations, risk classification, audit-compatible events, bounded provenance, normalized evidence artifacts, and downstream handoff metadata.


## AgentOS assimilation boundary

This plugin is a reference implementation of the capability-assimilation model described in [Q00/ouroboros-plugins#27](https://github.com/Q00/ouroboros-plugins/issues/27). It is accepted here only because static analysis clarifies the plugin contract boundary:

- **Core stays small:** Ouroboros core does not learn Semgrep rule syntax, scanner internals, registry semantics, or autofix behavior.
- **The external capability remains external:** Semgrep is required as an installed executable and is not vendored or reimplemented.
- **The plugin translates, not merely wraps:** each scan is converted into declared capabilities, explicit permissions, risk classification, audit-compatible events, bounded provenance, normalized findings, and a handoff bundle.
- **The repository remains a reference surface, not a marketplace:** this plugin demonstrates an auditable static-analysis assimilation pattern that future scanners can follow without expanding the manifest spec speculatively.

A trivial wrapper would only run `semgrep`. This plugin preserves the Semgrep CLI mental model while making the execution inspectable, permissioned, and resumable inside Ouroboros.

## Command

```bash
PYTHONPATH=plugins/semgrep-static-analysis \
  python3 -m semgrep_static_analysis scan . --config rules/ci.yml
```

When an Ouroboros dispatcher is available, the manifest exposes the same v0 path as:

```bash
ooo semgrep scan <target-path> --config <local-rule-or-pack>
```

## Semgrep UX preservation

The v0 command preserves familiar Semgrep concepts:

- target path / scan root,
- `--config` for a local rule file or directory by default,
- optional explicit remote/registry config mode,
- `--include` and `--exclude`,
- raw JSON preservation,
- optional SARIF preservation with `--sarif`,
- `--error` when CI-style finding exit semantics are desired,
- Semgrep's own `.semgrepignore` behavior,
- Semgrep stderr and exit-code evidence.

The plugin builds an argv list and invokes the installed `semgrep` executable. It never shell-interpolates user input.

## Local-first privacy defaults

The default scan path is local, read-only, and privacy-preserving:

```text
semgrep scan --json --metrics=off --disable-version-check --config <local-config> <target>
```

By default, the plugin:

- requires target paths to stay inside the repository root,
- requires config paths to stay inside the repository root,
- disables Semgrep metrics with `--metrics=off`,
- disables version checks with `--disable-version-check`,
- does not allow registry, URL, or `auto` configs unless `--allow-remote-config` is explicitly passed,
- writes artifacts under `.omx/artifacts/semgrep/<run-id>/` by default, and any custom output directory must still stay inside the repository root.

Remote configs such as `p/ci`, `p/python`, `r/...`, `auto`, or `https://...` require the optional `network:read` permission path. This keeps local-first scans local by default.

## Dependency and license stance

Semgrep is LGPL-2.1. This repository does not vendor Semgrep source and does not silently install Semgrep. Install Semgrep separately using the Semgrep-supported method for your environment, then verify:

```bash
semgrep --version
```

The plugin records the detected Semgrep version in provenance for each run.

## Capabilities and permissions

Manifest core capabilities:

- `ledger:write` — record invocation, policy inputs, and summary verdict.
- `provenance:write` — record Semgrep version, config source, target paths, command shape, artifact hashes, and result counts.
- `handoff:attach` — attach normalized findings and summaries for downstream agents.
- `progress:write` — report scan progress and completion.

External permissions:

- required `filesystem:read` — read target source and local rule files.
- required `shell:execute` — invoke the installed Semgrep CLI with bounded arguments.
- optional `network:read` — registry, URL, or remote Semgrep config flows only.

Capabilities and permissions remain separate per the Ouroboros plugin contract.

## Artifacts

A successful scan writes a handoff bundle like:

```text
.omx/artifacts/semgrep/<run-id>/
  semgrep.raw.json
  semgrep.raw.sarif          # when --sarif is requested and Semgrep writes it
  semgrep.stderr.txt
  semgrep.findings.json
  semgrep.summary.md
  semgrep.provenance.json
  semgrep.audit.json
  semgrep.handoff.json
```

`semgrep.raw.json` preserves Semgrep's native output. `semgrep.findings.json` contains normalized Ouroboros-friendly findings with rule id, severity, message, Semgrep-reported path, path-trust marker, scan root, start/end positions, metadata, fix availability, fingerprint, and a JSON pointer back to the raw result.

`semgrep.provenance.json` contains bounded facts only: plugin/tool versions, command shape, target/config identity, local/remote config mode, metrics/network modes, exit code, duration, result counts, artifact paths, and artifact hashes. It must not contain source code, tokens, raw prompts, or unbounded scanner output blobs.

`semgrep.audit.json` prepares audit-compatible `plugin.invoked`, `plugin.permission_used`, and `plugin.completed` / `plugin.failed` events matching the repository audit schema. The dispatcher can pass `--trust-state`; the default marks local prepared events as `trusted` and records `audit_payload_mode=plugin-prepared` in provenance.

`semgrep.handoff.json` is the downstream attachment point for agent triage, remediation Seed generation, PR review, or policy gates.

## Failure and blocked states

The plugin reports explicit non-success states:

- `blocked` when Semgrep is missing, paths escape the repository, local configs are missing, or remote configs are requested without explicit opt-in.
- `failed` when Semgrep execution fails or its JSON output is malformed.
- `success` when Semgrep runs and output is normalized. Semgrep exit code `1` is treated as a successful scan with findings when `--error` is used, preserving Semgrep CI semantics.

## Future expansion boundary

Out of scope for v0:

- vendoring or reimplementing Semgrep,
- Semgrep AppSec Platform dependency,
- source upload by default,
- autofix apply,
- rule test command,
- CI-baseline command,
- Semgrep MCP integration.

Future commands should be added only after the read-only boundary is stable. Autofix apply must require `filesystem:write`, explicit confirmation, patch provenance, and before/after evidence.
