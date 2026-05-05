# Anthropic Agent SDK reader

Use when Agent SDK or Claude Code integration behavior is uncertain.

Actions:

1. Prefer official docs — start from `https://docs.claude.com/en/docs/agent-sdk/overview` and related pages (many hosts expose `llms.txt` for crawling).
2. Cross-check the installed Python package (`claude-agent-sdk`) or TS package (`@anthropic-ai/claude-agent-sdk`) for exact types and option names.
3. Record durable repo-local notes in `docs/AGENT_SDK_NOTES.md` when you learn something non-obvious (keep entries short and dated).

Notes:

- The Claude Code SDK branding has consolidated under **Claude Agent SDK**.
- Python package: `claude-agent-sdk`; TypeScript: `@anthropic-ai/claude-agent-sdk`.
- Running the Python SDK still requires the **Claude Code CLI** (`claude`) available on `PATH` or via `ClaudeAgentOptions.cli_path`.
