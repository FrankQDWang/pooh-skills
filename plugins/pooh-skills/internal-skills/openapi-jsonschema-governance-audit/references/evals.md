# Evaluation cases

Use these as the minimum regression set for skill triggering and drift checks.

## Should trigger

1. “审计这个仓库的 OpenAPI / JSON Schema 治理面，看看 lint、bundle、breaking change detection 是不是都在。”
2. “检查我们的 Redocly、Spectral、Ajv/check-jsonschema 和 CI 到底有没有形成 API schema 门。”
3. “给我一份 schema artifact 报告，重点看 source of truth、bundle 健康度和 ruleset。”

## Should not trigger

1. “检查 TypeScript 运行时 schema 在边界上有没有真的生效。”
2. “给前端组件加视觉回归测试。”
3. “看 Python 仓库的 Ruff 规范栈是不是该清理旧工具。”

## False Positive / Regression Cases

1. 仓库只有 `openapi.generated.yaml`，真正源文件在别的私有仓。期望：标明证据不完整或 `blocked`，不要假装本仓可单独完成治理判断。
2. 仓库同时存在 `redocly bundle` 产物和源 spec。期望：先识别 canonical source，再判断 bundle 是否只是发布副产物。
3. 仓库只有 JSON Schema 配置文件，没有 OpenAPI。期望：OpenAPI 相关类别可 `not-applicable`，不要拖低整个 skill 的可信度。
