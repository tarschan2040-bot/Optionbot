# Rollback SOP

Read `AGENTS.md` and `CURRENT_STATE.md` first; restore service before chasing perfection.

This document defines the fastest safe recovery path when a new release causes problems.

## Purpose

When something breaks after a release:

- stabilize production first
- roll back the narrowest affected layer first
- verify service is restored
- investigate only after the user-facing problem is under control

## Golden Rules

1. Freeze new deploys during an incident.
2. Do not keep shipping fixes blindly into a broken production environment.
3. Roll back the smallest affected layer first.
4. Frontend and backend rollbacks can be quick; database rollback is not usually instant.
5. If data integrity is in question, stop writes before trying to be clever.

## First Five Minutes

### 1. Confirm the symptom

Write down:

- what broke
- when it started
- which layer looks affected:
  - frontend
  - backend API
  - worker
  - database/auth
- whether the issue is complete outage, partial outage, or bad data

### 2. Freeze changes

- stop new deploys
- stop optional follow-up changes
- keep the incident path narrow

### 3. Choose the first rollback target

Use this order:

- frontend only if the issue is clearly UI or routing
- backend API if requests fail or app logic broke
- worker if background jobs are causing damage
- database/auth only if the failure is truly data/config related

### 4. Restore service first

If a quick rollback exists, use it before spending time on root cause analysis.

## Fastest Rollback Matrix

### Frontend issue on Vercel

Use when:

- homepage or app pages fail after a frontend release
- bad UI, routing, rendering, or frontend auth flow appeared after deploy

First action:

- roll back the Vercel production deployment

Important notes:

- Vercel says rollback happens immediately at the routing layer
- on Hobby, rollback is only to the immediately previous production deployment
- on Pro or Enterprise, more eligible prior production deployments are available
- rollback does not fix a broken environment variable change by itself
- after rollback, automatic production-domain assignment is turned off until a new deployment is explicitly promoted

Source references:

- https://vercel.com/docs/instant-rollback
- https://vercel.com/docs/deployments/rollback-production-deployment

### Backend API issue on Railway

Use when:

- frontend still loads but API calls fail
- server-side logic changed and requests started returning errors

First action:

- roll back the Railway backend service deployment

Important notes:

- Railway rollback restores the previously successful deployment
- Railway says both the Docker image and custom variables are restored
- older deployments may be unavailable if they fall outside retention limits

Source reference:

- https://docs.railway.com/deployments/deployment-actions

### Worker issue on Railway

Use when:

- background scans or async jobs are causing bad writes or repeated failures

First action:

- roll back or stop the worker service separately from the backend API if possible

Important notes:

- do not assume the API must roll back just because the worker failed
- if the worker is causing data damage, stopping it may be safer than waiting

### Database or auth issue on Supabase

Use when:

- schema change broke compatibility
- bad data was written
- auth configuration or redirect settings broke sign-in or confirmation flows

Important notes:

- database rollback is not the same kind of instant rollback as Vercel or Railway
- Supabase restore-to-new-project copies schema, data, roles, and auth user data
- it does not automatically carry over storage objects and settings, edge functions, auth settings and API keys, realtime settings, database extensions/settings, or read replicas
- this means database recovery should be treated as controlled restoration work, not a casual one-click undo

Source reference:

- https://supabase.com/docs/guides/platform/clone-project

## Platform-Specific Playbooks

### Vercel Frontend Rollback

1. Open the Vercel project
2. Go to the current production deployment
3. Use Instant Rollback to select the last known good deployment
4. Confirm the correct production domains are affected
5. Verify the site recovers

After rollback:

- re-check homepage
- re-check login flow
- re-check one authenticated route
- remember that auto-assignment to production is turned off until a later explicit promotion

If the incident was caused by environment variables:

- rolling back code alone may not fix it
- compare current production env vars and revert the bad env change directly

### Railway Backend or Worker Rollback

1. Open the Railway project
2. Open the affected service
3. Go to Deployments
4. Find the last known good successful deployment
5. Use Rollback
6. Verify logs and health immediately after

For the worker:

- if active damage is happening, stop or roll back the worker first
- only roll back the API too if the API is part of the problem

Operational note:

- Railway supports overlap and draining settings for smoother cutovers during normal deploys
- that helps reduce release risk, but rollback still depends on deployment retention and the previous successful version being available

Source reference:

- https://docs.railway.com/deployments/deployment-teardown

### Supabase Recovery Path

1. Stop further risky deploys
2. If possible, stop or reduce writes from the broken app path
3. Identify the last known good backup or restore point
4. Restore into a separate Supabase project first
5. Verify schema, auth data, and application-critical tables
6. Recreate any missing non-database settings:
   - storage
   - auth config
   - API keys
   - edge functions
   - realtime settings
   - extensions/settings as needed
7. Repoint the app only after verification

This is slower than Vercel or Railway rollback, which is why schema and auth changes must be handled cautiously in `RELEASE_SOP.md`.

## Verification After Rollback

Minimum checks:

- the previously broken user path now works
- no new deploy is still racing in behind the rollback
- logs are calmer than before rollback
- the incident scope is smaller or resolved

Report one of:

- `restored`
- `partially restored`
- `not restored`

## Incident Notes Template

Capture these facts before the details get lost:

- release date and time
- first user-visible symptom
- affected layer
- first rollback action taken
- result after rollback
- unresolved follow-up risk

## What Not To Do

- do not deploy more speculative fixes before stabilizing service
- do not assume database restore is instantaneous
- do not roll back unrelated layers just because one layer failed
- do not describe a partial recovery as fully resolved

## Related Documents

- `AGENTS.md`
- `BACKUP_PROCESS.md`
- `DEPLOY.md`
- `RELEASE_SOP.md`
