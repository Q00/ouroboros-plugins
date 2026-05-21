# Compound Engineering risk matrix

The current manifest schema supports plugin-level permissions only. This plugin therefore declares `filesystem:read` as required and all command-specific elevated scopes as optional, with the command-level requirements documented here.

| Command | Upstream skill | Risk | Requires confirmation | Required command permissions | Notes |
|---|---|---|---|---|---|
| `compound agent-native-architecture` | `ce-agent-native-architecture` | `write` | `false` | `filesystem:read, filesystem:write` | Writes bounded local handoff artifacts; external writes require optional trust scopes. |
| `compound agent-native-audit` | `ce-agent-native-audit` | `read_only` | `false` | `filesystem:read` | May write .omx/compound artifacts. |
| `compound brainstorm` | `ce-brainstorm` | `write` | `false` | `filesystem:read, filesystem:write` | Writes bounded local handoff artifacts; external writes require optional trust scopes. |
| `compound clean-gone-branches` | `ce-clean-gone-branches` | `destructive` | `true` | `filesystem:read, filesystem:write, git:write, shell:execute` | Blocked unless `--confirm` is supplied. |
| `compound code-review` | `ce-code-review` | `read_only` | `false` | `filesystem:read` | May write .omx/compound artifacts. |
| `compound commit` | `ce-commit` | `write` | `false` | `filesystem:read, filesystem:write, git:write, shell:execute` | Writes bounded local handoff artifacts; external writes require optional trust scopes. |
| `compound commit-push-pr` | `ce-commit-push-pr` | `destructive` | `true` | `filesystem:read, filesystem:write, git:write, github:pull_request:write, network:write, shell:execute` | Blocked unless `--confirm` is supplied. |
| `compound compound` | `ce-compound` | `write` | `false` | `filesystem:read, filesystem:write` | Writes bounded local handoff artifacts; external writes require optional trust scopes. |
| `compound compound-refresh` | `ce-compound-refresh` | `write` | `false` | `filesystem:read, filesystem:write` | Writes bounded local handoff artifacts; external writes require optional trust scopes. |
| `compound debug` | `ce-debug` | `write` | `false` | `filesystem:read, filesystem:write` | Writes bounded local handoff artifacts; external writes require optional trust scopes. |
| `compound demo-reel` | `ce-demo-reel` | `write` | `false` | `filesystem:read, filesystem:write` | Writes bounded local handoff artifacts; external writes require optional trust scopes. |
| `compound dhh-rails-style` | `ce-dhh-rails-style` | `write` | `false` | `filesystem:read, filesystem:write` | Writes bounded local handoff artifacts; external writes require optional trust scopes. |
| `compound doc-review` | `ce-doc-review` | `read_only` | `false` | `filesystem:read` | May write .omx/compound artifacts. |
| `compound frontend-design` | `ce-frontend-design` | `write` | `false` | `filesystem:read, filesystem:write` | Writes bounded local handoff artifacts; external writes require optional trust scopes. |
| `compound gemini-imagegen` | `ce-gemini-imagegen` | `write` | `false` | `filesystem:read, filesystem:write, network:write, api_key:gemini` | Writes bounded local handoff artifacts; external writes require optional trust scopes. |
| `compound ideate` | `ce-ideate` | `write` | `false` | `filesystem:read, filesystem:write` | Writes bounded local handoff artifacts; external writes require optional trust scopes. |
| `compound optimize` | `ce-optimize` | `write` | `false` | `filesystem:read, filesystem:write` | Writes bounded local handoff artifacts; external writes require optional trust scopes. |
| `compound plan` | `ce-plan` | `write` | `false` | `filesystem:read, filesystem:write` | Writes bounded local handoff artifacts; external writes require optional trust scopes. |
| `compound polish-beta` | `ce-polish-beta` | `write` | `false` | `filesystem:read, filesystem:write` | Writes bounded local handoff artifacts; external writes require optional trust scopes. |
| `compound product-pulse` | `ce-product-pulse` | `read_only` | `false` | `filesystem:read` | May write .omx/compound artifacts. |
| `compound proof` | `ce-proof` | `write` | `false` | `filesystem:read, filesystem:write` | Writes bounded local handoff artifacts; external writes require optional trust scopes. |
| `compound release-notes` | `ce-release-notes` | `read_only` | `false` | `filesystem:read` | May write .omx/compound artifacts. |
| `compound report-bug` | `ce-report-bug` | `write` | `false` | `filesystem:read, filesystem:write` | Writes bounded local handoff artifacts; external writes require optional trust scopes. |
| `compound resolve-pr-feedback` | `ce-resolve-pr-feedback` | `destructive` | `true` | `filesystem:read, filesystem:write, github:pull_request:write, network:write, git:write` | Blocked unless `--confirm` is supplied. |
| `compound riffrec-feedback-analysis` | `ce-riffrec-feedback-analysis` | `read_only` | `false` | `filesystem:read` | May write .omx/compound artifacts. |
| `compound sessions` | `ce-sessions` | `read_only` | `false` | `filesystem:read` | May write .omx/compound artifacts. |
| `compound setup` | `ce-setup` | `write` | `false` | `filesystem:read, filesystem:write, shell:execute` | Writes bounded local handoff artifacts; external writes require optional trust scopes. |
| `compound simplify-code` | `ce-simplify-code` | `write` | `false` | `filesystem:read, filesystem:write` | Writes bounded local handoff artifacts; external writes require optional trust scopes. |
| `compound slack-research` | `ce-slack-research` | `write` | `false` | `filesystem:read, filesystem:write, slack:read, network:read` | Writes bounded local handoff artifacts; external writes require optional trust scopes. |
| `compound strategy` | `ce-strategy` | `write` | `false` | `filesystem:read, filesystem:write` | Writes bounded local handoff artifacts; external writes require optional trust scopes. |
| `compound test-browser` | `ce-test-browser` | `write` | `false` | `filesystem:read, filesystem:write, browser:automation, shell:execute` | Writes bounded local handoff artifacts; external writes require optional trust scopes. |
| `compound test-xcode` | `ce-test-xcode` | `write` | `false` | `filesystem:read, filesystem:write, mcp:call, xcode:execute, shell:execute` | Writes bounded local handoff artifacts; external writes require optional trust scopes. |
| `compound update` | `ce-update` | `write` | `false` | `filesystem:read, filesystem:write, network:read` | Writes bounded local handoff artifacts; external writes require optional trust scopes. |
| `compound work` | `ce-work` | `write` | `false` | `filesystem:read, filesystem:write` | Writes bounded local handoff artifacts; external writes require optional trust scopes. |
| `compound work-beta` | `ce-work-beta` | `write` | `false` | `filesystem:read, filesystem:write` | Writes bounded local handoff artifacts; external writes require optional trust scopes. |
| `compound worktree` | `ce-worktree` | `write` | `false` | `filesystem:read, filesystem:write` | Writes bounded local handoff artifacts; external writes require optional trust scopes. |
| `compound lfg` | `lfg` | `destructive` | `true` | `filesystem:read, filesystem:write, shell:execute, git:write, github:pull_request:write, network:write` | Blocked unless `--confirm` is supplied. |
