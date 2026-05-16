# Release SOP

Read `AGENTS.md` and `CURRENT_STATE.md` first; no production deploy without explicit approval.

This document defines the normal release path for OptionBot.

The core rule is simple:

- production stays separate from local and shadow work
- every meaningful change is reviewed in shadow first
- deployment needs its own explicit approval after shadow review

## Environment Model

Use these terms consistently:

- `Production`
  - what is live now for real users
  - current frontend on Vercel
  - current backend and worker on Railway
  - current live Supabase project
- `Shadow`
  - local or isolated review environment
  - safe place for testing and review before deploy
  - should have the access needed for the feature under review
  - should use a dedicated reviewer account, preferably already signed in for review flows
- `Preview`
  - hosted but not live
  - optional extra step between shadow and production

## Golden Rules

1. Approval to change code is not approval to deploy code.
2. No production deployment until the user has reviewed and approved the shadow result.
3. After shadow approval, get a second explicit approval before deploying.
4. Never experiment directly on the live frontend, live backend, or live Supabase project.
5. If a change touches auth, billing, schema, live user data, or core trading flows, slow down and release narrowly.

## Required Reading Before Release Work

- `AGENTS.md`
- `CURRENT_STATE.md`
- `BACKUP_PROCESS.md`
- `DEPLOY.md`
- `ROLLBACK_SOP.md`

## Standard Release Flow

### 1. Define the release scope

Write down:

- what is changing
- what is not changing
- which layer is affected:
  - frontend
  - backend API
  - worker
  - database/schema
  - auth configuration

If the release spans multiple layers, say so explicitly and call out the extra risk.

### 2. Build and review in shadow first

Do all implementation and review outside production.

Preferred shadow setups:

- frontend: local Next.js or isolated preview
- backend: local FastAPI or separate Railway shadow service
- database/auth: separate shadow Supabase project for risky or stateful testing

Shadow review expectations:

- reviewer can access the feature end to end
- reviewer account is ready and signed in when practical
- live user data is not used for destructive tests
- production secrets and production infra stay untouched

### 3. Get shadow approval

Before any deploy preparation, confirm that the user has reviewed the shadow result and wants to continue toward production.

This is approval gate one.

### 4. Create a backup

Before meaningful release work:

- create the timestamped repo backup zip
- create the matching changelog markdown file

Follow `BACKUP_PROCESS.md`.

If the release also changes database state, verify that platform backups or restore points are available before continuing.

### 5. Prepare the rollback plan

Before deployment, record:

- current live frontend deployment identifier
- current live backend deployment identifier
- current live worker deployment identifier
- latest known good Supabase backup or restore timestamp
- exact smoke tests to run after deploy
- first rollback action if the release fails

If you cannot describe the rollback path clearly, the release is not ready.

### 6. Prefer narrow releases

Deploy the smallest useful slice first.

Preferred order:

- frontend-only release
- backend-only release
- worker-only release
- schema-only change when unavoidable

Avoid combining schema, auth, backend, and frontend changes into one deployment unless the user explicitly accepts that risk.

### 7. Handle schema changes carefully

Database changes are higher risk because they are harder to undo instantly.

Rules:

- separate schema work from ordinary UI releases whenever possible
- prefer additive, backward-compatible migrations first
- do not assume a fast database rollback exists
- do not deploy schema and app changes together unless the compatibility path is clear

### 8. Get production deployment approval

After shadow review, backup preparation, and rollback planning, ask for final approval to deploy.

This is approval gate two.

Do not deploy without it.

### 9. Deploy by layer

Use the smallest safe deployment step.

Examples:

- frontend-only change: deploy Vercel frontend only
- backend-only change: deploy Railway backend service only
- worker change: deploy worker separately from backend if possible
- schema change: run migration in a dedicated window and verify before app promotion

### 10. Run smoke tests immediately

After deploy, check the paths that matter most.

Minimum smoke checks:

- homepage loads
- login or signup path still works
- one authenticated app page loads
- one critical API path succeeds
- logs show no obvious spike in failures

If the smoke test fails, move to `ROLLBACK_SOP.md` immediately.

### 11. Confirm release status honestly

Report one of:

- `deployed and verified`
- `deployed with partial verification`
- `rolled back`
- `stopped before deploy`

Do not blur those states together.

## Release Checklist

- Read the required docs
- Defined exact release scope
- Reviewed the change in shadow
- User approved the shadow result
- Backup created
- Rollback path written down
- Production deployment explicitly approved
- Release deployed narrowly
- Smoke tests completed
- Final status reported honestly

## Notes For This Repo

- Frontend is documented for Vercel in `DEPLOY.md`
- Backend and worker are documented for Railway in `DEPLOY.md`
- Supabase auth and redirect config are part of release risk, especially around login and confirmation flows
- Frontend build reliability has known edge cases in restricted environments, so build verification and shadow review matter

## Related Documents

- `AGENTS.md`
- `BACKUP_PROCESS.md`
- `DEPLOY.md`
- `ROLLBACK_SOP.md`
