# Current State

Read `AGENTS.md` and `CURRENT_STATE.md` first; no code changes without my approval.

Last updated: 2026-05-02

This is the concise operational snapshot for new AI agents. It should describe reality, not aspiration.

## Product Direction

- Core product remains a Python options scanner and Telegram-controlled bot.
- SaaS direction is web-first, with FastAPI backend and Next.js frontend layered around the scanner.
- Telegram should be treated as an operator channel and possible premium notification channel, not the only future interface.

## What Exists and Works

- `scheduler.py` runs the scanner and Telegram bot.
- Dry-run path works through `python scheduler.py --once --no-telegram --dry-run`.
- Core scanner tests pass: `python3 -m pytest -q` was green during the latest review.
- The scanner core, scoring pipeline, and existing Telegram workflow are in usable shape.
- SaaS scaffolding exists:
  - `backend/` FastAPI app
  - `frontend/` Next.js app
  - `migrations/` for SaaS-related tables
  - `user_configs` and scan result concepts are present
- Frontend signup now sends email confirmations to `/auth/callback` on the current site origin.

## Implemented but Incomplete

- Multi-user configuration layer exists conceptually and partially in code.
- Candidate workflow API exists in `backend/routers/candidates.py`.
- Scan/config API routes exist.
- Frontend dashboard shell exists.

## Known Issues From Latest Review

1. Multi-tenant safety is not complete.
   - Candidate and portfolio workflows are not fully scoped by `user_id`.
   - Treat any multi-user launch assumptions as unsafe until this is fixed in code and schema.

2. Portfolio live-data path is broken.
   - `backend/routers/portfolio.py` constructs `OptionContract` with fields that do not match `core/models.py`.

3. Backend plan vs mounted routes are not fully aligned.
   - Not every planned route is mounted in `backend/app.py`.

4. Frontend build reliability is uneven.
   - Current frontend build depends on remote Google font fetches.
   - Frontend linting has shown dependency-tree issues in the latest review environment.

## What Is Not Yet Safe To Assume

- That the SaaS layer is ready for production multi-user traffic
- That portfolio endpoints are live and correct
- That all planned auth, Stripe, and notification surfaces are mounted and working
- That documentation always matches the actual implementation

## Current Development Guardrail

Any new AI agent should treat this repository as:

- safe for read-only analysis without approval
- not safe for code changes without explicit approval

Before making changes, read `AGENTS.md` and ask the user for approval.

## Recommended Next Priorities

1. Finish trade workflow schema migration and legacy row backfill for `trade_candidates` and `trade_log`
2. Decide whether portfolio is active now or explicitly deferred
3. Bring route mounting and docs into sync
4. Stabilize frontend build and lint paths
5. Add high-value regression tests for cross-user isolation and core scan flow
