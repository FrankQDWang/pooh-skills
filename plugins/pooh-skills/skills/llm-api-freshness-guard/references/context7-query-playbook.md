# Context7 Query Playbook

For each surface:

1. identify the resolution level
2. choose the smallest doc surface that owns the behavior
3. ask one sharp query first
4. add only the extra queries needed to confirm or refute drift

Examples:

- `provider-resolved openai python openai sdk responses api structured output current usage`
- `family-resolved openai-compatible typescript current chat completions or responses compatibility guidance`
- `wrapper-resolved litellm current provider pass through tool calling streaming behavior`
