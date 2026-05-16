"""
backend/routers/portfolio.py — retired legacy portfolio router
===============================================================

This module is intentionally not mounted by `backend/app.py`.

The active portfolio API lives in `backend/routers/candidates.py`:

- GET  /candidates/portfolio
- GET  /candidates/portfolio/summary
- POST /candidates/{trade_id}/close

Keep this empty router as a guardrail for old imports while preventing the
stale `/portfolio/*` implementation from drifting away from current models.
"""

from fastapi import APIRouter

router = APIRouter()
