# Git workflow

## Permanent branches

- `prod`: production releases; pull requests only.
- `staging`: QA and demos; pull requests only.
- `dev`: integration branch for completed features.

## Feature work

Create feature branches from `dev` using `feat/<feature_name>`. Open a pull request back into `dev`, require review, then promote `dev` to `staging` and `staging` to `prod` after verification.

## Hotfixes

Create `hotfix/<fix_name>` from `prod`. Merge the reviewed pull request into `prod`, then merge `prod` back into both `staging` and `dev`.

## Commits

Use Conventional Commits and include an issue ID for material changes:

```text
feat: add bank deposit reconciliation #123
fix: prevent duplicate provider leases #124
docs: document deployment workflow #125
```

Do not commit `.env`, credentials, OAuth data, runtime databases, logs, dependencies, or build output.
