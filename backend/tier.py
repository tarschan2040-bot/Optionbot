"""
backend/tier.py — Subscription tier checking and feature gating
================================================================
Provides FastAPI dependencies to check user tier and enforce limits.

Free tier restrictions:
  - Max 2 tickers
  - Read-only config (can view but not update)
  - No manual scan trigger (only sees yesterday's results)
  - No trade workflow (star/confirm disabled)

Pro tier:
  - Unlimited tickers
  - Full config editing
  - Real-time scans (manual + 3 daily scheduled)
  - Full trade workflow
"""
import logging
from typing import Optional

from fastapi import Depends, HTTPException, status
from data.supabase_client import SupabaseClient
from backend.auth import get_current_user

log = logging.getLogger(__name__)

# ── Tier limits ───────────────────────────────────────────────────────────

FREE_TICKER_LIMIT = 2
FREE_RESULT_LIMIT = 5  # only top 5 results shown


def get_user_tier(user_id: str) -> str:
    """
    Look up the user's subscription tier from the subscriptions table.
    Returns 'free' or 'pro'. Defaults to 'free' if no row found.
    """
    try:
        supabase = SupabaseClient()
        if not supabase.is_enabled():
            return "free"

        resp = (
            supabase._client.table("subscriptions")
            .select("tier, status")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        rows = resp.data or []
        if not rows:
            return "free"

        row = rows[0]
        # Only active/trialing subscriptions count
        if row.get("status") in ("active", "trialing"):
            return row.get("tier", "free")
        return "free"

    except Exception as e:
        log.warning("get_user_tier failed for %s: %s — defaulting to free", user_id[:8], e)
        return "free"


# ── FastAPI dependencies ──────────────────────────────────────────────────

async def require_pro(user_id: str = Depends(get_current_user)) -> str:
    """
    Dependency that raises 403 if user is not on Pro tier.
    Use on endpoints that require Pro access.
    """
    tier = get_user_tier(user_id)
    if tier != "pro":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This feature requires a Pro subscription.",
        )
    return user_id


async def get_tier_info(user_id: str = Depends(get_current_user)) -> dict:
    """
    Dependency that returns user_id and tier info.
    Use when you need to vary behavior by tier (not block entirely).
    """
    tier = get_user_tier(user_id)
    return {
        "user_id": user_id,
        "tier": tier,
        "is_pro": tier == "pro",
        "ticker_limit": None if tier == "pro" else FREE_TICKER_LIMIT,
        "result_limit": None if tier == "pro" else FREE_RESULT_LIMIT,
    }
