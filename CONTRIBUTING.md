# Contributing

This repository hosts the UserLevel plugin contract and a small set of
curated reference plugins. It is **not** a general-purpose plugin marketplace.

See [Q00/ouroboros#725](https://github.com/Q00/ouroboros/issues/725) for the
framing decisions that make this repo a "contract firewall" rather than a
marketplace.

## What we accept

- Bug fixes to the contract validator, schemas, and reference plugins.
- Documentation improvements.
- Schema clarifications proposed via an issue first.

## What we do not accept (here)

- New third-party plugins. Maintain those in your own repository and install
  via `ouroboros plugin add <your-repo-url>`.
- Changes that expand the manifest surface preemptively. The contract evolves
  only when an existing reference plugin demonstrably needs the new field.

## Process

1. Open an issue describing the problem or proposal.
2. Wait for maintainer ack before opening a PR for any contract change.
3. Install the validator's dev dependency (added by
   Q00/ouroboros-plugins#13). Until that PR lands the validator is
   stdlib-only and this step is a no-op:
   ```bash
   pip install -r requirements-dev.txt 2>/dev/null || pip install "jsonschema>=4.21"
   ```
4. Run `python3 scripts/validate_contract.py` locally before pushing. The
   validator must exit `0`.

## Code review

`@Q00` reviews every change via `CODEOWNERS`. Please be patient — this repo
intentionally moves at maintainer-review speed, not at marketplace speed.
