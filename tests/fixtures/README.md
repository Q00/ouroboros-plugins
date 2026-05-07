# Negative fixtures for validate_contract.py

Each `bad-*.json` file is a manifest crafted to violate exactly one schema rule.
The validator must reject each one with a non-zero exit code.

| Fixture | Violation |
|---|---|
| `bad-name-pattern.json` | `name` contains whitespace, violating the pattern |
| `bad-unknown-capability.json` | `capabilities[0].name` uses an enum value not in the schema |
| `bad-unknown-source-type.json` | `source.type` uses `"remote"`, not in the enum |
| `bad-additional-property.json` | extra unknown top-level key (`weird_key`) violates `additionalProperties: false` |
| `bad-missing-required.json` | `name` removed entirely (required field) |

The `tests/test_validator.py` suite (or a CI step) iterates over these and
asserts each one fails. Adding a new schema constraint should add a fixture.
