# OptionBot Backend API Routes

Last verified: 2026-05-15 21:39 Europe/London

This is the mounted FastAPI surface from `backend/app.py`. Treat this file as
the route inventory before changing frontend API calls, backend routers, or
deployment docs.

Verification command:

```bash
python3 -B - <<'PY'
from backend.app import app

for route in app.routes:
    if not hasattr(route, "methods"):
        continue
    methods = ",".join(sorted(set(route.methods) - {"HEAD", "OPTIONS"}))
    print(f"{methods} {route.path}")
PY
```

## Mounted Routers

`backend/app.py` mounts:

- `backend.routers.health` at the API root
- `backend.routers.config` with prefix `/config`
- `backend.routers.scan` with prefix `/scan`
- `backend.routers.candidates` with prefix `/candidates`

`backend/routers/portfolio.py` is a retired empty guardrail router and is not
mounted by `backend/app.py`.

## Current Mounted Endpoints

| Method | Path | Source |
| --- | --- | --- |
| `GET` | `/health` | `backend/routers/health.py` |
| `GET` | `/me` | `backend/routers/health.py` |
| `GET` | `/config` | `backend/routers/config.py` |
| `PUT` | `/config` | `backend/routers/config.py` |
| `GET` | `/scan/results` | `backend/routers/scan.py` |
| `POST` | `/scan/trigger` | `backend/routers/scan.py` |
| `GET` | `/scan/status` | `backend/routers/scan.py` |
| `GET` | `/scan/results/{index}` | `backend/routers/scan.py` |
| `GET` | `/scan/history` | `backend/routers/scan.py` |
| `GET` | `/candidates` | `backend/routers/candidates.py` |
| `POST` | `/candidates/star` | `backend/routers/candidates.py` |
| `POST` | `/candidates/{candidate_id}/confirm` | `backend/routers/candidates.py` |
| `DELETE` | `/candidates/{candidate_id}` | `backend/routers/candidates.py` |
| `GET` | `/candidates/portfolio` | `backend/routers/candidates.py` |
| `GET` | `/candidates/portfolio/summary` | `backend/routers/candidates.py` |
| `POST` | `/candidates/{trade_id}/close` | `backend/routers/candidates.py` |

The automatic FastAPI documentation routes also exist locally:

- `GET /docs`
- `GET /docs/oauth2-redirect`
- `GET /redoc`
- `GET /openapi.json`

## Not Currently Mounted

These paths appear in older plans or legacy router comments, but are not mounted
by the current backend app:

- `/auth/signup`
- `/auth/login`
- `/stripe/webhook`
- `/stripe/portal`
- `/portfolio/candidates`
- `/portfolio/candidates/confirm/{id}`
- `/portfolio/candidates/{id}`
- `/portfolio/positions`
- `/portfolio/summary`

Auth is currently handled by Supabase on the frontend, with the backend
verifying Supabase JWTs through `backend/auth.py`. Stripe/billing routes remain
planned work, not implemented backend API.
