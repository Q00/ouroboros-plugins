# hermes-agent-runner

Bounded Hermes runtime bridge. The runner records session state, transcripts, and handoff artifacts so Hermes can operate as an external AgentOS capability under Ouroboros supervision.

```bash
PYTHONPATH=plugins/hermes-agent-runner python3 -m ouroboros_hermes_runner run "review this repo" --timeout 300
PYTHONPATH=plugins/hermes-agent-runner python3 -m ouroboros_hermes_runner status <session-id>
PYTHONPATH=plugins/hermes-agent-runner python3 -m ouroboros_hermes_runner resume <session-id>
PYTHONPATH=plugins/hermes-agent-runner python3 -m ouroboros_hermes_runner stop <session-id>
PYTHONPATH=plugins/hermes-agent-runner python3 -m ouroboros_hermes_runner export <session-id> --out /tmp/handoff
```

`chat` creates auditable attach metadata; interactive terminal attachment remains gated by explicit shell/network/provider trust.
