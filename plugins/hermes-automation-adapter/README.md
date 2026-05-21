# hermes-automation-adapter

Static bridge from Hermes cron/job definitions into reviewable Ouroboros Seed drafts. It does not schedule jobs or run scripts.

```bash
PYTHONPATH=plugins/hermes-automation-adapter python3 -m ouroboros_hermes_cron inspect ~/.hermes/cron/jobs.json
PYTHONPATH=plugins/hermes-automation-adapter python3 -m ouroboros_hermes_cron import ~/.hermes/cron/jobs.json --out /tmp/hermes-cron
PYTHONPATH=plugins/hermes-automation-adapter python3 -m ouroboros_hermes_cron plan ~/.hermes/cron/jobs.json --job-id daily --out /tmp/daily.md
```
