# OptionBot Agent Guardrails

This file is the mandatory first stop for AI agents working in this repository.
It is intentionally short so future "continue development" sessions do not burn
context re-reading long project history.

## Fast Startup Packet

For ordinary development or review:

1. Read this file.
2. Read `AI_CONTEXT.md`.
3. Run `git status --short`.
4. Read only files directly related to the user's requested task.
5. State whether the request is read-only or change-making.
6. Ask for approval before editing, installing, migrating, deploying, restarting,
   or running any command that may alter local or production state.

Use `AI_TASK_QUEUE.md` when the user says "continue development" without naming
a specific task. Use `PROJECT_MAP.md` to find relevant files quickly.

## Approval Gate

Read-only analysis is allowed without approval.

Ask for explicit approval before:

- editing or creating files
- installing packages
- running build steps that may modify generated output
- changing database schema or migrations
- running workers, schedulers, or long-lived services
- deploying, restarting, or touching production infrastructure
- deleting, resetting, overwriting, or reverting work

Approval to make code or documentation changes is not approval to deploy.
Production deployment requires a separate explicit approval after shadow review.

## Protect The Running Bot

- Do not change runtime behavior unless the user explicitly approves that scope.
- Do not touch `bot.pid`, `bot.log`, `.env`, production secrets, or live services
  unless the user explicitly asks and the risk is explained first.
- Prefer documentation, tests, and isolated shadow work over broad refactors.
- Never assume field names, routes, tables, or function signatures from memory.
  Re-read the actual file before acting.

## Source Of Truth

When documents disagree, use this order:

1. actual code and migrations
2. `AI_CONTEXT.md`
3. `CURRENT_STATE.md`
4. `SAAS_MASTER_PLAN.md`
5. `README.md`
6. historical handoff documents

Report drift clearly instead of smoothing it over.

## Conditional Reading

Only read these deeper docs when relevant:

- `CURRENT_STATE.md`: when the compact context is not enough
- `SAAS_MASTER_PLAN.md`: roadmap/product-direction questions
- `README.md`: runtime/operator basics
- `BACKUP_PROCESS.md`: before meaningful approved change work
- `DEPLOY.md`, `RELEASE_SOP.md`, `ROLLBACK_SOP.md`: release, staging,
  preview, deploy, rollback, schema, auth, production-risk, or incident work
- `KEN_MASTER_HANDOFF.md`: historical context only, not sole truth

## Shadow And Production Rules

- Default meaningful frontend, backend, auth, schema, and data-touching work to
  local or shadow review first.
- Keep production separate from local/shadow/preview work.
- Do not treat the live frontend, live backend, live Supabase project, or running
  bot as a playground.
- If a task might touch live user data, live auth, production infra, or the
  running bot, call that out before proceeding.

## Definition Of Done For Approved Work

Before calling work done:

- relevant code paths were reviewed end to end
- API and schema assumptions still match actual code/migrations
- tests/checks were run when appropriate, or skipped with a reason
- docs were updated if behavior or workflow changed
- `AI_CONTEXT.md` still reflects the current operational truth
- a concise handoff was prepared or updated

## Current High-Risk Areas

Treat these carefully:

- multi-user data isolation
- Supabase table ownership and query scoping
- portfolio live-data path
- backend route mounting vs planned API surface
- frontend build/lint reliability
- anything mixing single-user bot behavior with SaaS behavior
