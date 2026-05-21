# hermes-skill-assimilator

Static adapter for Hermes Agent skills and plugin metadata. It never executes imported Hermes instructions.

```bash
PYTHONPATH=plugins/hermes-skill-assimilator python3 -m ouroboros_hermes_skill inspect /path/to/hermes-agent
PYTHONPATH=plugins/hermes-skill-assimilator python3 -m ouroboros_hermes_skill catalog /path/to/hermes-agent --out /tmp/hermes-skill-report.md
```

