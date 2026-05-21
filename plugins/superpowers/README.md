# superpowers

Ouroboros-native adapter for [`obra/superpowers`](https://github.com/obra/superpowers).

This PR adds the schema-valid plugin manifest, a pinned upstream Superpowers
snapshot, and read-only discovery commands:

```bash
PYTHONPATH=plugins/superpowers python3 -m superpowers_ouroboros list
PYTHONPATH=plugins/superpowers python3 -m superpowers_ouroboros inspect brainstorming
```

The pinned snapshot is `obra/superpowers` `v5.1.0` at commit
`f2cbfbefebbfef77321e4c9abc9e949826bea9d7` under MIT license.

Follow-up PRs add Seed-compatible handoff generation, audit/provenance run
artifacts, full command mappings, tests, and catalog publication.
