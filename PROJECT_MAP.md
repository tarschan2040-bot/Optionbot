# Project Map

Compact map for AI agents. Use this to find the right files without broad
repo scans.

## Runtime Entry Points

- `scheduler.py` — live scanner scheduler and optional Telegram bot runner.
- `START_BOT.sh`, `START_BOT.command` — local bot launch helpers.
- `backend/app.py` — FastAPI application and mounted routers.
- `backend/worker.py` — SaaS worker/background scan process.
- `frontend/src/app/` — Next.js app routes.

## Scanner Core

- `core/config.py` — `ScannerConfig`, defaults, validation, config hash.
- `core/models.py` — option, Greeks, and opportunity dataclasses.
- `core/scanner.py` — fetch, filter, Greeks, scoring orchestration.
- `core/greeks.py` — Black-Scholes Greeks, IV rank, annualized return.
- `core/indicators.py` — mean-reversion scoring.
- `core/scorer.py` — composite opportunity score.
- `strategies/covered_call.py` — covered-call filters.
- `strategies/cash_secured_put.py` — cash-secured-put filters.

## Data And Persistence

- `data/yfinance_fetcher.py` — Yahoo Finance data source.
- `data/ibkr_fetcher.py` — Interactive Brokers data source.
- `data/mock_fetcher.py` — synthetic dry-run source.
- `data/supabase_client.py` — trade workflow, scan history, and user config persistence.
- `migrations/` — Supabase schema changes.

## Backend API

- `backend/auth.py` — Supabase JWT verification.
- `backend/tier.py` — beta tier/scan-limit logic.
- `backend/routers/health.py` — health endpoint.
- `backend/routers/config.py` — authenticated scanner config CRUD.
- `backend/routers/scan.py` — scan results/history/manual trigger.
- `backend/routers/candidates.py` — mounted candidate and portfolio workflow.
- `backend/routers/portfolio.py` — retired empty guardrail router; not mounted in `backend/app.py`.
- `docs/API_ROUTES.md` — current mounted API route inventory and unmounted legacy/planned paths.

## Frontend

- `frontend/src/app/page.tsx` — current public/landing entry.
- `frontend/src/app/login/page.tsx` — login/signup UI.
- `frontend/src/app/dashboard/page.tsx` — dashboard route.
- `frontend/src/app/scan/page.tsx` — scan/results route.
- `frontend/src/app/settings/page.tsx` — app settings route.
- `frontend/src/app/account/page.tsx` — account/tier route.
- `frontend/src/app/portfolio/page.tsx` — portfolio route.
- `frontend/src/hooks/useSession.ts` — Supabase session hook.
- `frontend/src/lib/api.ts` — API client helpers.
- `frontend/src/lib/supabase.ts` — browser Supabase client.

## Tests And Checks

- `tools/test_greeks.py` — core Greeks tests.
- `tools/test_regressions.py` — recent regression coverage.
- `tools/check_supabase.py` — Supabase wiring check.
- `tools/check_telegram.py` — Telegram connection check.
- `tools/check_connection.py` — IBKR connection check.

## Operational Docs

- `AGENTS.md` — AI guardrails and startup workflow.
- `AI_CONTEXT.md` — compact current project truth.
- `AI_TASK_QUEUE.md` — approved-next-work queue for generic continuation.
- `PROJECT_MAP.md` — this file.
- `CURRENT_STATE.md` — fuller current-state record.
- `SHADOW_REVIEW.md` — local/shadow pre-deploy review checklist.
- `BACKUP_PROCESS.md` — backup convention.
- `DEPLOY.md` — deployment notes.
- `RELEASE_SOP.md` — release discipline.
- `ROLLBACK_SOP.md` — rollback discipline.
- `DECISIONS.md` — architectural/product decisions.
- `KEN_MASTER_HANDOFF.md` — historical handoff only.
