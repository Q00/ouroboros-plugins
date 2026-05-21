# RFC: UserLevel Plugin Authoring and Capability Assimilation

Status: accepted consensus record for the local-only v0 plugin contract.

Related issues and references:

- Q00/ouroboros-plugins#27 — SSOT request for plugin authoring and capability assimilation.
- Q00/ouroboros-plugins#29 — external target repository assimilation reference package.
- `Q00/ouroboros/docs/rfc/userlevel-plugins.md` — corresponding core UserLevel plugin RFC.
- `docs/contract.md`, `docs/lifecycle.md`, `docs/permissions.md`, and `docs/audit.md`.
- `CONTRIBUTING.md`.

## Core thesis

Ouroboros plugins are not merely command wrappers. They are the capability
assimilation layer that turns external tools, open-source libraries, and domain
workflows into structured, auditable, permissioned, Seed-compatible Ouroboros
capabilities.

```text
External capability / OSS library / domain workflow
        ↓
Ouroboros plugin contract
        ↓
Seed / Ledger / State / Provenance / Permission / Audit / Handoff
        ↓
Ouroboros-native execution ecosystem
```

The plugin layer exists to keep core small while allowing the outside world to
become Ouroboros-native.

## Repository roles

### Ouroboros core

Core owns stable OS-like primitives:

- Seed
- Ledger
- State
- Runtime
- MCP
- Provenance
- safety boundaries
- permission checks
- audit event emission
- progress and status
- recovery and replay
- handoff
- workflow / harness vocabulary

Core should not absorb every useful domain workflow.

### `Q00/ouroboros-plugins`

This repository is a curated contract and reference repository. It hosts:

- manifest schemas,
- audit schemas,
- validators,
- lifecycle documentation,
- permission and trust documentation,
- audit and provenance documentation,
- reference plugins,
- authoring guidance,
- compatibility / conformance examples,
- and RFCs that define the plugin contract.

It is **not** a general marketplace, package registry, hosted discovery service,
or plugin-count-driven ecosystem surface. Success is measured by whether the
boundary holds and assimilated capabilities remain auditable and safe.

### Third-party plugin repositories

Third-party authors should maintain their own repositories:

```text
some-plugin-repo/
  README.md
  plugins/
    my-plugin/
      ouroboros.plugin.json
      README.md
      my_plugin/
        __main__.py
  catalog/
    index.json        # optional prompt metadata / ordering
```

Canonical install form:

```bash
ouroboros plugin add https://github.com/<author>/<repo> --plugin <plugin-name>
```

Local development form:

```bash
ouroboros plugin add . --plugin <plugin-name>
```

The repository URL is the unit of distribution. `plugins/<name>/` is the unit of
selection. `plugins/<name>/ouroboros.plugin.json` is the source of truth for
plugin identity and command declaration. `catalog/index.json` is optional
metadata, not the source of truth.

Subdirectory-leaking install strings are rejected:

```bash
git+https://github.com/Q00/ouroboros-plugins.git#plugins/github-pr-ops
```

Coupling install strings to internal layout prevents authors from refactoring
repositories without breaking users.

## Defensive and offensive purposes

The defensive purpose is to keep core and first-party programs such as
`ooo auto` from absorbing every domain-specific workflow:

- GitHub PR merge policy
- Jira workflow semantics
- Linear triage rules
- Slack incident update conventions
- release checklist conventions
- customer debugging playbooks
- research-loop-specific training heuristics

The offensive purpose is to make powerful external capabilities available inside
Ouroboros without weakening the substrate:

- GitHub PR analysis / merge readiness
- Karpathy-style autoresearch loops
- Semgrep / CodeQL / static analysis engines
- pytest / Hypothesis / mutation testing
- Playwright / browser QA / visual testing
- OpenAPI validation and SDK generation
- Terraform / Kubernetes operational workflows
- Jira / Linear / Slack / GitHub SDK workflows
- release automation tools
- evaluation frameworks
- data or ML experiment harnesses

## What makes a plugin Ouroboros-native

A trivial wrapper says:

```text
Run this external command.
```

An Ouroboros-native plugin says:

```text
Translate this external capability into an explicit, permissioned, auditable,
resumable, handoff-capable workflow.
```

A good plugin defines:

- what goal it helps satisfy,
- what external capability it assimilates,
- what files or systems it may read,
- what files or systems it may write,
- what side effects it may cause,
- what risk class those side effects carry,
- what core primitives it needs,
- what evidence it emits,
- what handoff artifact it creates,
- how success/failure/blocking is represented,
- and how the user or harness can continue after it runs.

The `autoresearch` reference plugin illustrates this distinction: it does not
just run `uv run train.py`; it inspects repository shape, bounds editable files,
preserves metric and budget, generates Seed/handoff artifacts, records
provenance, and hands off to `ooo auto`.

## Manifest contract

Each plugin package contains `plugins/<name>/ouroboros.plugin.json`.

The v0.1 contract has eight required fields and two optional fields:

| Field | Status | Reason |
|---|---|---|
| `schema_version` | required | Routes validation and migration policy. |
| `name` | required | Stable plugin identity, install home, and audit identity. |
| `version` | required | Lockfile, trust invalidation, and upgrade semantics. |
| `source` | required | Trust-state and lifecycle semantics. |
| `commands` | required | User-facing callable surface. |
| `capabilities` | required | Core primitive access declaration. |
| `permissions` | required | External authority declaration. |
| `entrypoint` | required | Isolated execution boundary. |
| `description` | optional | Human-readable documentation. |
| `audit` | optional | Event vocabulary declaration / defaults. |

A valid manifest is only the executable minimum. A contract-compliant plugin
also preserves safety, auditability, provenance, bounded side effects, and
handoff semantics.

## Capabilities vs permissions

Capabilities describe access to Ouroboros core primitives:

- `seed:read`
- `seed:write`
- `ledger:write`
- `state:write`
- `provenance:write`
- `runtime:execute`
- `mcp:call`
- `handoff:attach`
- `progress:write`

Permissions describe external authority:

- `filesystem:read`
- `filesystem:write`
- `network:read`
- `network:write`
- `shell:execute`
- `github:read`
- `github:pull_request:write`
- `slack:write`

A plugin that cannot explain both its core capability needs and its external
authority needs is not fully contract-compliant.

## Risk taxonomy

Risk is shared across commands and permissions:

- `read_only` — no side effects on core state or external systems.
- `write` — reversible, bounded, or expected side effects.
- `destructive` — irreversible, high-impact, or production-affecting side effects.

Risk is not cosmetic metadata. It drives trust UX, confirmation behavior, review
expectations, and audit interpretation.

| Capability / action | Likely risk |
|---|---|
| inspect local files without writing artifacts | `read_only` |
| write handoff artifacts | `write` |
| update a Jira ticket | `write` |
| post to Slack | `write` or `destructive`, depending on context |
| merge a GitHub PR | `destructive` |
| apply Terraform | `destructive` |
| delete cloud resources | `destructive` |

A command that emits local artifacts or handoffs from inside the plugin is a
`write` command unless the artifact emission is performed outside the command by
the core firewall.

## Lifecycle, trust, and firewall

The lifecycle is:

```text
discovered → installed → trusted → invoked
```

Additional outcomes include:

```text
disabled
blocked
failed
completed
```

Rules:

- Discovery means the manifest can be read and inspected.
- Installation copies/registers the plugin and records lockfile state.
- Trust grants specific scopes, not blanket authority.
- Install does not imply trust.
- Destructive permissions require explicit user intent.
- Trust can be invalidated by version or artifact changes.
- Invocation goes through the firewall.
- Blocked invocations should emit blocked/failure semantics without pretending
  the plugin ran.

A plugin is run by Ouroboros only when invocation passed through manifest
validation, registry resolution, trust checks, permission checks, risk semantics,
and audit emission.

## Audit, provenance, and handoff

Auditability is the reason external capabilities can be assimilated without
becoming unbounded core code.

Every plugin invocation should answer:

- Which plugin and version ran?
- Which command ran?
- What arguments were supplied?
- Which core capabilities were used?
- Which external permissions were used?
- What artifact or result was produced?
- What source evidence supports the result?
- Was the invocation blocked, failed, cancelled, or completed?
- What should a human or harness do next?

Standard runtime events include:

- `plugin.invoked`
- `plugin.permission_used`
- `plugin.completed`
- `plugin.failed`

## `ooo auto` boundary

`ooo auto` remains a first-party UserLevel program, not a catch-all router. It
may consume plugin-prepared handoffs, Seeds, or artifacts, but every
domain-specific classifier or external-tool branch should not be added to
`ooo auto`.

Examples:

- GitHub PR operations belong in `github-pr-ops` / related plugins.
- Autoresearch loop preparation belongs in `autoresearch`.
- Jira synchronization belongs in a Jira plugin.
- Slack incident workflow belongs in a Slack/incident plugin.
- Terraform or Kubernetes operations belong in infrastructure plugins.

This keeps `ooo auto` coherent while allowing plugins to become powerful.

## Reference plugin policy

Reference plugins in this repository are accepted only when they prove or
clarify a contract boundary.

`github-pr-ops` proves GitHub PR operational workflows belong outside core and
keeps destructive merge behavior out of v0 until destructive trust UX is locked.

`autoresearch` proves an external research loop can be assimilated as structured
Seed/handoff artifacts rather than becoming domain logic in `ooo auto`.

`target-capabilities` proves the issue #29 external target-repository
assimilation pattern: command-level risk, exact permissions, bounded artifacts,
provenance, handoff, fail-closed dependency detection, and destructive gating.

Future reference plugins should prove at least one of:

- a new permission pattern,
- a new lifecycle pattern,
- a new handoff pattern,
- a new audit/provenance pattern,
- a new external capability assimilation pattern,
- or a boundary that must not enter core.

## Open-source library assimilation checklist

When wrapping an external open-source library or tool, answer:

### Capability identity

- What external capability is being assimilated?
- Is it a library, CLI, SDK, service integration, workflow, or harness?
- Why should it become an Ouroboros plugin instead of remaining standalone?

### Ouroboros translation

- What Seed, handoff, artifact, or workflow concept does the tool map to?
- What does the plugin produce that Ouroboros can understand?
- Does it attach evidence to a run/step/artifact projection?
- Does it create a human-readable handoff?

### Boundaries

- What files may it read?
- What files may it write?
- What network endpoints may it contact?
- What commands may it run?
- What production or external systems may it mutate?
- Can all paths be made repo-relative or otherwise bounded?

### Permissions and risk

- What required permissions are needed?
- Which are optional?
- Which are read-only, write, or destructive?
- What user trust action is expected before invocation?

### Execution semantics

- Is the external tool deterministic enough for audit?
- What is the verification command?
- How are failures represented?
- How are partial results represented?
- How can a human resume or inspect the result?

### Contract fit

- Does the plugin require a new manifest field?
- If yes, can the need be proven by a reference plugin?
- Can the same behavior be expressed with existing capabilities, permissions,
  audit, and handoff instead?

Arbitrary libraries can be assimilated, but not arbitrarily. The plugin contract
is the translation layer.

## Contribution policy

This repository accepts:

- schema fixes,
- validator fixes,
- documentation improvements,
- reference plugin fixes,
- contract clarifications proposed through issues,
- and carefully justified reference plugins that prove a contract need.

It does not accept by default:

- arbitrary third-party plugins,
- marketplace-style listings,
- speculative manifest expansion,
- plugin count growth as a goal,
- or contract changes without a demonstrated reference need.

The manifest surface expands only when an existing reference plugin
demonstrably needs the new field and the need cannot be represented by the
existing contract.

## Future direction and non-goals

Allowed and encouraged:

- repo-based plugin distribution,
- high-quality external capability adapters,
- conservative schema evolution,
- explicit permission and risk boundaries,
- stronger audit/provenance integration,
- handoff artifacts that `ooo auto` and the harness can consume,
- Workflow IR / Run / Step / Artifact integration when available,
- lifecycle hooks that are permissioned and audited,
- external author repositories for long-tail plugins,
- curated reference plugins only when they clarify the contract.

Rejected non-goals:

- central hosted marketplace as a product surface,
- plugin count as a success metric,
- auto-update without explicit trust semantics,
- implicit destructive permission grants,
- arbitrary core state mutation,
- domain-specific branching inside `ooo auto`,
- unbounded command wrappers with no audit/handoff semantics,
- plugin APIs that bypass the firewall.
