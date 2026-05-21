# Upstream source

- Repository: https://github.com/vercel-labs/agent-skills
- Observed commit: `7defe2d03c5fa8e39b63b12648c1fa10131b422a`
- Commit date from issue #36: 2026-05-19
- License: MIT (vendored in `upstream/agent-skills/LICENSE`)

Included skills:

1. `vercel-optimize`
2. `vercel-react-best-practices` (upstream directory `react-best-practices`)
3. `web-design-guidelines`
4. `vercel-react-native-skills` (upstream directory `react-native-skills`)
5. `vercel-react-view-transitions` (upstream directory `react-view-transitions`)
6. `vercel-composition-patterns` (upstream directory `composition-patterns`)
7. `deploy-to-vercel`
8. `vercel-cli-with-tokens`

The adapter preserves progressive disclosure: command discovery reads the manifest, while command execution reads the selected upstream `SKILL.md` and only the needed rules/references/scripts.
