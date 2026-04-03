# Evals

## Should Trigger

- A repo contains `.env`, key files, or token-like material and the user asks for secret hygiene review.
- A repo may have hardcoded passwords, API keys, or client secrets in code or config.
- The user wants repo-health coverage for secrets and hardcoded credential material.

## Should Not Trigger

- The request is only about dependency CVEs, lockfiles, or Bandit-style static security.
- The request is about cloud posture, IAM, runtime hardening, or container scanning.
- The user wants automatic rotation, deletion, or git-history rewriting instead of an audit.

## False Positive / Regression Cases

- Placeholder values like `changeme`, `example`, `dummy`, or `${ENV_VAR}` should not be called leaked secrets.
- Documentation examples that show fake tokens should not outrank real working-tree exposure.
- A repo without git history access should be reported as a trust gap, not as `clean`.
