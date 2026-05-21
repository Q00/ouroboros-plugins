# opa-policy-gate

`opa-policy-gate` is a reference Ouroboros plugin for assimilating
[Open Policy Agent](https://github.com/open-policy-agent/opa) as an
AgentOS-native policy gate without degrading the native OPA experience.

The goal is capability assimilation, not a fork and not a marketplace entry:
Rego remains Rego, OPA CLI concepts remain recognizable, and raw OPA output is
preserved so a human can reproduce a decision with `opa` directly.

## V0 command surface

```bash
ooo opa eval --config .ouroboros/opa/policy-gate.json
ooo opa test --config .ouroboros/opa/policy-tests.json
ooo opa check --config .ouroboros/opa/policy-check.json
ooo opa build-handoff --config .ouroboros/opa/policy-bundle.json
```

The manifest intentionally uses a repo-relative config file for repeatable OPA
inputs because schema `0.1` has a small argument model. This avoids premature
manifest expansion while preserving OPA-shaped inputs like repeated `--data`.

## Native OPA UX preservation promise

Preserved:

- Rego package/query semantics.
- Existing repo-relative policy, data, input, bundle, schema, and capability
  file layouts.
- OPA JSON output as the primary machine-readable substrate.
- OPA `eval`, `test`, `check`, and `build` mental models.
- OPA error semantics for undefined decisions, parse/compile errors, unsafe
  variables, and test failures.
- OPA version visibility and a recorded reproduction command.

Added by Ouroboros:

- Manifest-declared permissions and trust gates.
- Repo-relative path bounding.
- Audit/provenance records.
- Normalized AgentOS statuses (`completed`, `failed`, `blocked`).
- Human-readable and downstream-consumable handoff artifacts.

## V0 exclusions

V0 deliberately excludes:

- `opa run -s` / server mode.
- REST Policy API writes or remote policy mutation.
- Implicit network fetches.
- Arbitrary OPA command passthrough.
- `opa fmt --write`.
- Bundle signing / key handling.
- Terraform, Kubernetes, or production apply-style mutation.

## Artifact model

Every command writes only under a bounded run directory:

```text
.omx/artifacts/opa/<command>/<run_id>/
  raw-stdout.json
  raw-stderr.txt
  normalized-result.json
  provenance.json
  handoff.md
  repro.sh
```

`build-handoff` may additionally write `bundle.tar.gz` in that same run
directory. Raw OPA output remains available for reproduction/debugging, while
`normalized-result.json` and `handoff.md` give downstream Ouroboros workflows a
stable policy evidence shape.

## Permissions

Required v0 permissions:

- `filesystem:read` — read bounded policy, data, input, bundle, schema, and
  config files.
- `shell:execute` — invoke the installed `opa` CLI with bounded arguments.
- `filesystem:write` — write evidence and handoff artifacts only under
  `.omx/artifacts/opa/`.

Install must not imply trust. If `opa` is missing, paths escape the repository,
permissions are not trusted, or an unsupported command is requested, the plugin
returns `blocked`/`failed` evidence without pretending OPA ran.

## Reproduce outside Ouroboros

For the example config in this plugin, the equivalent native OPA command is:

```bash
opa eval --format json --data plugins/opa-policy-gate/examples/allow.rego \
  --data plugins/opa-policy-gate/examples/data.json \
  --input plugins/opa-policy-gate/examples/input.json \
  --fail data.example.allow
```

The bridge records an exact `repro.sh` for each invocation.

## Issue alignment

This plugin implements the OPA epic in
[Q00/ouroboros-plugins#45](https://github.com/Q00/ouroboros-plugins/issues/45)
and follows the capability-assimilation direction from #27: mature OSS tools
can become AgentOS-native through the plugin contract without moving domain
branches into Ouroboros core.
