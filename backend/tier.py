"""
backend/tier.py — 3-tier subscription system
==============================================
Free:  3 scans/day, top 3 results visible, no portfolio, no config edit
Pro:   30 scans/day, all results, 10 portfolio trades, config edit  ($19.99/mo)
Max:   Unlimited scans, all results, unlimited portfolio, all features ($49.99/mo)
"""
import logging
from datetime import datetime, date

from fastapi import Depends, HTTPException, status
from data.supabase_client import SupabaseClient
from backend.auth import get_current_user

log = logging.getLogger(__name__)

# ── Tier definitions ──────────────────────────────────────────────────────

TIERS = {
    "free": {
        "label": "Free",
        "price": 0,
        "scans_per_day": 3,
        "visible_results": 3,       # top N results shown clearly
        "portfolio_limit": 0,        # no portfolio tracking
        "can_edit_config": False,
        "can_use_portfolio": False,
    },
    "pro": {
        "label": "Pro",
        "price": 19.99,
        "scans_per_day": 30,
        "visible_results": None,     # all results
        "portfolio_limit": 10,       # max 10 open trades
        "can_edit_config": True,
        "can_use_portfolio": True,
    },
    "max": {
        "label": "Max",
        "price": 49.99,
        "scans_per_day": None,       # unlimited
        "visible_results": None,     # all results
        "portfolio_limit": None,     # unlimited
        "can_edit_config": True,
        "can_use_portfolio": True,
    },
}


## BETA MODE: All users get Max tier until payment system launches.
## When ready to enforce tiers, set this to False.
BETA_ALL_MAX = True


def get_user_tier(user_id: str) -> str:
    """Look up user's tier from subscriptions table. Defaults to 'max' during beta."""
    if BETA_ALL_MAX:
        return "max"

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
        if row.get("status") in ("active", "trialing"):
            tier = row.get("tier", "free")
            return tier if tier in TIERS else "free"
        return "free"

    except Exception as e:
        log.warning("get_user_tier failed: %s — defaulting to free", e)
        return "free"


def get_daily_scan_count(user_id: str) -> int:
    """Count how many scans the user has triggered today."""
    try:
        supabase = SupabaseClient()
        if not supabase.is_enabled():
            return 0

        today_start = datetime.combine(date.today(), datetime.min.time()).isoformat()
        resp = (
            supabase._client.table("scan_results")
            .select("id", count="exact")
            .eq("user_id", user_id)
            .gte("scan_timestamp", today_start)
            .execute()
        )
        return resp.count or 0

    except Exception as e:
        log.warning("get_daily_scan_count failed: %s", e)
        return 0


def get_portfolio_count(user_id: str) -> int:
    """Count open trades in portfolio."""
    try:
        supabase = SupabaseClient()
        if not supabase.is_enabled():
            return 0

        resp = (
            supabase._client.table("trade_log")
            .select("id", count="exact")
            .is_("exit_date", "null")
            .execute()
        )
        return resp.count or 0

    except Exception as e:
        log.warning("get_portfolio_count failed: %s", e)
        return 0


# ── FastAPI dependencies ──────────────────────────────────────────────────

async def get_tier_info(user_id: str = Depends(get_current_user)) -> dict:
    """
    Returns full tier info for the user including limits and current usage.
    """
    tier_name = get_user_tier(user_id)
    tier = TIERS[tier_name]
    scans_today = get_daily_scan_count(user_id)
    scans_limit = tier["scans_per_day"]

    return {
        "user_id": user_id,
        "tier": tier_name,
        "tier_label": tier["label"],
        "is_pro": tier_name in ("pro", "max"),
        "is_max": tier_name == "max",
        # Scan limits
        "scans_per_day": scans_limit,
        "scans_today": scans_today,
        "scans_remaining": None if scans_limit is None else max(0, scans_limit - scans_today),
        "can_scan": scans_limit is None or scans_today < scans_limit,
        # Result limits
        "visible_results": tier["visible_results"],
        "total_results": None,  # filled by the endpoint
        # Config
        "can_edit_config": tier["can_edit_config"],
        # Portfolio
        "can_use_portfolio": tier["can_use_portfolio"],
        "portfolio_limit": tier["portfolio_limit"],
    }


async def require_pro(user_id: str = Depends(get_current_user)) -> str:
    """Raises 403 if not Pro or Max."""
    tier = get_user_tier(user_id)
    if tier not in ("pro", "max"):
        raise HTTPException(status_code=403, detail="Pro subscription required.")
    return user_id
