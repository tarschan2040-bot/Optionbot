"""
backend/app.py — FastAPI application entry point
=================================================
OptionBot SaaS API. Serves scan results, config CRUD, and user management.

Usage:
    uvicorn backend.app:app --reload --port 8000

    Or from project root:
    python -m uvicorn backend.app:app --reload --port 8000
"""
import sys
import os

# Ensure project root is on path so we can import core/, data/, etc.
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routers import health, config, scan, candidates

# ── App setup ─────────────────────────────────────────────────────────────

app = FastAPI(
    title="OptionBot API",
    description="Options scanner SaaS backend — scan, configure, and manage opportunities.",
    version="1.0.0-alpha",
)

# ── CORS — allow frontend (localhost dev + production domain) ─────────────

_origins = [
    "http://localhost:3000",
    "http://localhost:5173",
    "https://optionbot-theta.vercel.app",
    "https://app.optionbot.org",
    "https://optionbot.org",
]
_extra = os.getenv("FRONTEND_URL", "").strip()
if _extra:
    for origin in _extra.split(","):
        cleaned = origin.strip().rstrip("/")
        if cleaned and cleaned not in _origins:
            _origins.append(cleaned)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Register routers ──────────────────────────────────────────────────────

app.include_router(health.router, tags=["Health"])
app.include_router(config.router, prefix="/config", tags=["Config"])
app.include_router(scan.router, prefix="/scan", tags=["Scan"])
app.include_router(candidates.router, prefix="/candidates", tags=["Candidates"])
