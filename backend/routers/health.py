"""
backend/routers/health.py — Health check + user tier endpoint
"""
from fastapi import APIRouter, Depends
from data.supabase_client import SupabaseClient
from backend.auth import get_current_user
from backend.tier import get_tier_info

router = APIRouter()


@router.get("/health")
async def health_check():
    """
    Basic health check. Returns API status and Supabase connectivity.
    No auth required — used by uptime monitors and load balancers.
    """
    supabase = SupabaseClient()
    db_ok = supabase.test_connection() if supabase.is_enabled() else False

    return {
        "status": "ok",
        "service": "optionbot-api",
        "version": "1.0.0-alpha",
        "supabase_connected": db_ok,
    }


@router.get("/me")
async def get_me(tier_info: dict = Depends(get_tier_info)):
    """Return the current user's tier info including scan limits and usage."""
    return tier_info
