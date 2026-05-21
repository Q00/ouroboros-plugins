# anthropic-agent-skills

`anthropic-agent-skills` is the reference assimilation plugin for the `anthropics/skills` repository.

It does not vendor restricted upstream materials. Instead, it records provenance, classifies license state, exposes manifest-backed command candidates, and routes runtime work through a bounded plugin adapter that can produce audit and handoff artifacts.

## Commands

```bash
PYTHONPATH=plugins/anthropic-agent-skills python3 -m agent_skills inspect <skill-dir>
PYTHONPATH=plugins/anthropic-agent-skills python3 -m agent_skills catalog <repo-or-path>
PYTHONPATH=plugins/anthropic-agent-skills python3 -m agent_skills validate <skill-dir-or-plugin-dir>
PYTHONPATH=plugins/anthropic-agent-skills python3 -m agent_skills resolve "Use the PDF skill to extract text"
PYTHONPATH=plugins/anthropic-agent-skills python3 -m agent_skills invoke webapp-testing test --repo <anthropics-skills-checkout>
PYTHONPATH=plugins/anthropic-agent-skills python3 -m agent_skills prepare-handoff webapp-testing test --status blocked
```

`invoke` is intentionally conservative in this MVP: it loads `SKILL.md` at invocation time, records provenance, and produces a handoff. It blocks commands that require restricted source, unavailable source, or untrusted script execution instead of exposing an unbounded shell wrapper.


This plugin is separate from the existing `plugins/agent-skills` adapter for other skill-pack assimilation targets. The separate package name prevents marketplace-style aggregation and keeps the issue #33 target pinned to `anthropics/skills`.
