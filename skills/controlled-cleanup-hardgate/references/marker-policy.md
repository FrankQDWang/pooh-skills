# Deprecation marker policy

## Goal
Make cleanup machine-readable enough that tooling can tell:
- what is deprecated
- what should replace it
- when removal is intended
- who should care

## Minimum fields
- deprecation cue
- replacement
- removal target (date or version)

## Examples

### Python
```python
# DEPRECATED: use new_create_order
# REMOVE-AFTER: 2026-06-30
# OWNER: checkout-platform
```

### TypeScript / JavaScript
```ts
/**
 * @deprecated Use createOrderV2
 * replace-with: createOrderV2
 * remove-after: 2026-06-30
 */
```

### Markdown / docs
```md
> Deprecated. Replace with `/api/v2/orders`.
> Remove after: 2026-06-30.
```

## Advice
Prefer dates or explicit released-version targets over vague TODO comments.
