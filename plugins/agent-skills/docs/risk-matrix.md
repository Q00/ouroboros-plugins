# Risk and permission matrix

| Mode | Meaning | Default behavior |
|---|---|---|
| `report` | Read-only analysis/report capability | Writes a handoff artifact; does not mutate target code. |
| `artifact_write` | Produces specs, plans, ADRs, or interview artifacts | Writes handoff artifacts only. |
| `guarded_edit` | Upstream workflow may edit code or run tools | Records blocked shell/browser authority unless explicitly granted. |
| `fanout` | Launch readiness synthesis over specialist personas | Records readiness handoff; does not deploy or release. |

No command is destructive by default. Destructive future behavior such as
pushing, merging, deleting, deploying, or mutating external systems must be a
separate command design with explicit trust grants.
