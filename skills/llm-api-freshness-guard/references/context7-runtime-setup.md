# Context7 Runtime Setup Notes

This skill assumes Context7 is available in the runtime.

## Codex / OpenAI

`agents/openai.yaml` declares a Context7 MCP dependency so Codex can use the remote Context7 server directly when the environment supports MCP dependencies.

## General rules

- Do not hardcode API keys into `SKILL.md`.
- Do not commit Context7 credentials into the repo.
- Use environment configuration or the client's MCP settings.
- If Context7 is missing, the skill must fall back to `local-scan-only` and say so plainly.
