"""
backend/routers/config.py — User config CRUD endpoints
=======================================================
GET  /config       — get authenticated user's ScannerConfig
PUT  /config       — update authenticated user's ScannerConfig
"""
import logging
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.auth import get_current_user
from backend.tier import get_tier_info, FREE_TICKER_LIMIT
from core.config import ScannerConfig
from data.supabase_client import SupabaseClient

log = logging.getLogger(__name__)
router = APIRouter()


# ── Pydantic models (request/response) ────────────────────────────────────

class ConfigResponse(BaseModel):
    """Full ScannerConfig as returned to the frontend."""
    tickers: List[str]
    strategy: str
    data_source: str

    min_dte: int
    max_dte: int
    strike_range_pct: float

    cc_delta_min: float
    cc_delta_max: float
    csp_delta_min: float
    csp_delta_max: float

    min_theta: float
    min_iv_rank: float
    max_iv_rank: float
    min_iv: float
    max_vega: float

    min_annualised_return: float
    min_premium: float
    min_open_interest: int
    min_volume: int
    max_bid_ask_spread_pct: float

    weight_iv: float
    weight_theta_yield: float
    weight_delta_safety: float
    weight_liquidity: float
    weight_ann_return: float
    weight_mean_reversion: float

    use_mean_reversion: bool
    mr_rsi_period: int
    mr_z_period: int
    mr_roc_period: int
    mr_w_rsi: float
    mr_w_z: float
    mr_w_roc: float
    mr_trend_guard: bool
    mr_trend_pct: float

    config_hash: str = ""


class ConfigUpdate(BaseModel):
    """
    Partial config update. All fields optional — only send what you want to change.
    The frontend can send just `{"min_iv": 0.35}` to update a single field.
    """
    tickers: Optional[List[str]] = None
    strategy: Optional[str] = None
    data_source: Optional[str] = None

    min_dte: Optional[int] = None
    max_dte: Optional[int] = None
    strike_range_pct: Optional[float] = None

    cc_delta_min: Optional[float] = None
    cc_delta_max: Optional[float] = None
    csp_delta_min: Optional[float] = None
    csp_delta_max: Optional[float] = None

    min_theta: Optional[float] = None
    min_iv_rank: Optional[float] = None
    max_iv_rank: Optional[float] = None
    min_iv: Optional[float] = None
    max_vega: Optional[float] = None

    min_annualised_return: Optional[float] = None
    min_premium: Optional[float] = None
    min_open_interest: Optional[int] = None
    min_volume: Optional[int] = None
    max_bid_ask_spread_pct: Optional[float] = None

    weight_iv: Optional[float] = None
    weight_theta_yield: Optional[float] = None
    weight_delta_safety: Optional[float] = None
    weight_liquidity: Optional[float] = None
    weight_ann_return: Optional[float] = None
    weight_mean_reversion: Optional[float] = None

    use_mean_reversion: Optional[bool] = None
    mr_rsi_period: Optional[int] = None
    mr_z_period: Optional[int] = None
    mr_roc_period: Optional[int] = None
    mr_w_rsi: Optional[float] = None
    mr_w_z: Optional[float] = None
    mr_w_roc: Optional[float] = None
    mr_trend_guard: Optional[bool] = None
    mr_trend_pct: Optional[float] = None


# ── Helpers ───────────────────────────────────────────────────────────────

def _config_to_response(config: ScannerConfig) -> ConfigResponse:
    """Convert ScannerConfig dataclass to API response model."""
    from dataclasses import asdict
    d = asdict(config)
    d.pop("dry_run", None)
    d["config_hash"] = config.config_hash()
    return ConfigResponse(**d)


def _get_supabase() -> SupabaseClient:
    client = SupabaseClient()
    if not client.is_enabled():
        raise HTTPException(status_code=503, detail="Database not available.")
    return client


# ── Endpoints ─────────────────────────────────────────────────────────────

@router.get("", response_model=ConfigResponse)
async def get_config(user_id: str = Depends(get_current_user)):
    """Get the authenticated user's scanner configuration."""
    supabase = _get_supabase()
    config = supabase.ensure_user_config(user_id)
    return _config_to_response(config)


@router.put("", response_model=ConfigResponse)
async def update_config(
    update: ConfigUpdate,
    tier_info: dict = Depends(get_tier_info),
):
    """
    Update the authenticated user's scanner configuration.
    Pro only — free users have read-only config with default parameters.
    """
    user_id = tier_info["user_id"]

    if not tier_info["is_pro"]:
        raise HTTPException(
            status_code=403,
            detail="Editing scan parameters requires a Pro subscription.",
        )

    supabase = _get_supabase()

    # Load existing config (or create default)
    config = supabase.ensure_user_config(user_id)

    # Apply partial updates
    update_data = update.model_dump(exclude_none=True)
    if not update_data:
        return _config_to_response(config)

    for field_name, value in update_data.items():
        if hasattr(config, field_name):
            setattr(config, field_name, value)

    # Validate before saving
    try:
        config.validate()
    except AssertionError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # Save to DB
    if not supabase.save_user_config(user_id, config):
        raise HTTPException(status_code=500, detail="Failed to save config.")

    log.info("Config updated for user %s: %s", user_id, list(update_data.keys()))
    return _config_to_response(config)
