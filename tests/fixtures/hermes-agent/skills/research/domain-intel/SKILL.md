---
name: domain-intel
description: Research a domain and summarize external signals.
allowed-tools:
  - shell
  - web
optional: false
---

# Domain intelligence

Read `references/sources.md`, call https://example.com/search, and write `report.md`.

## Setup

Set `HERMES_API_KEY` and install `ripgrep`.

```bash
curl https://example.com/api?q="$DOMAIN"
python scripts/enrich.py --out report.md
```

Never delete production data.
