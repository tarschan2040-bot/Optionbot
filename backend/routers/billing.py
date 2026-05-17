"""
backend/routers/billing.py -- Stripe Billing integration
=========================================================

Creates Stripe Checkout Sessions for paid subscriptions, Customer Portal
Sessions for self-service billing, and processes Stripe webhooks to sync the
local `subscriptions` table.
"""
import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from backend.auth import get_current_user_claims
from data.supabase_client import SupabaseClient

log = logging.getLogger(__name__)
router = APIRouter()

STRIPE_API_VERSION = os.getenv("STRIPE_API_VERSION", "2026-02-25.clover")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000").split(",")[0].strip().rstrip("/")

PRICE_ENV = {
    ("pro", "monthly"): "STRIPE_PRICE_PRO_MONTHLY",
    ("pro", "annual"): "STRIPE_PRICE_PRO_ANNUAL",
    ("max", "monthly"): "STRIPE_PRICE_MAX_MONTHLY",
    ("max", "annual"): "STRIPE_PRICE_MAX_ANNUAL",
}

PUBLIC_PLANS = [
    {"tier": "free", "label": "Free", "monthly_price": 0, "annual_price": 0},
    {"tier": "pro", "label": "Pro", "monthly_price": 19.99, "annual_price": 15.99},
    {"tier": "max", "label": "Max", "monthly_price": 49.99, "annual_price": 39.99},
]


class CheckoutRequest(BaseModel):
    tier: str
    billing_period: str = "monthly"


class BillingSessionResponse(BaseModel):
    url: str


def _get_supabase() -> SupabaseClient:
    client = SupabaseClient()
    if not client.is_enabled():
        raise HTTPException(status_code=503, detail="Database not available.")
    return client


def _get_stripe():
    secret_key = os.getenv("STRIPE_SECRET_KEY", "").strip()
    if not secret_key:
        raise HTTPException(status_code=503, detail="Stripe is not configured.")

    try:
        import stripe
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="Stripe SDK is not installed.") from exc

    stripe.api_key = secret_key
    stripe.api_version = STRIPE_API_VERSION
    return stripe


def _price_id_for(tier: str, billing_period: str) -> str:
    key = (tier, billing_period)
    env_name = PRICE_ENV.get(key)
    if not env_name:
        raise HTTPException(status_code=422, detail="Unsupported billing plan.")

    price_id = os.getenv(env_name, "").strip()
    if not price_id:
        raise HTTPException(status_code=503, detail=f"{env_name} is not configured.")
    return price_id


def _tier_for_price(price_id: Optional[str]) -> str:
    if not price_id:
        return "free"
    for (tier, _period), env_name in PRICE_ENV.items():
        if os.getenv(env_name, "").strip() == price_id:
            return tier
    return "free"


def _stripe_get(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _stripe_dict(obj: Any) -> dict:
    if not obj:
        return {}
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "to_dict_recursive"):
        return obj.to_dict_recursive()
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    return {}


def _timestamp_to_iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        return None


def _subscription_price_id(subscription: Any) -> Optional[str]:
    items = _stripe_get(subscription, "items", {}) or {}
    data = _stripe_get(items, "data", []) or []
    if not data:
        return None
    price = _stripe_get(data[0], "price", {}) or {}
    return _stripe_get(price, "id")


def _subscription_period_end(subscription: Any) -> Any:
    period_end = _stripe_get(subscription, "current_period_end")
    if period_end:
        return period_end

    items = _stripe_get(subscription, "items", {}) or {}
    data = _stripe_get(items, "data", []) or []
    if not data:
        return None
    return _stripe_get(data[0], "current_period_end")


def _subscription_metadata(subscription: Any) -> dict:
    metadata = _stripe_get(subscription, "metadata", {}) or {}
    return _stripe_dict(metadata)


def _find_subscription_row_by_user(user_id: str) -> Optional[dict]:
    supabase = _get_supabase()
    resp = (
        supabase._client.table("subscriptions")
        .select("*")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    return rows[0] if rows else None


def _find_user_id_by_customer(customer_id: str) -> Optional[str]:
    supabase = _get_supabase()
    resp = (
        supabase._client.table("subscriptions")
        .select("user_id")
        .eq("stripe_customer_id", customer_id)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    return rows[0].get("user_id") if rows else None


def _upsert_subscription_row(row: dict) -> None:
    supabase = _get_supabase()
    supabase._client.table("subscriptions").upsert(row, on_conflict="user_id").execute()


def _sync_subscription_from_stripe(subscription: Any, user_id: Optional[str] = None) -> bool:
    customer_id = _stripe_get(subscription, "customer")
    subscription_id = _stripe_get(subscription, "id")
    status_value = _stripe_get(subscription, "status", "incomplete")
    price_id = _subscription_price_id(subscription)
    metadata = _subscription_metadata(subscription)

    resolved_user_id = user_id or metadata.get("user_id")
    if not resolved_user_id and customer_id:
        resolved_user_id = _find_user_id_by_customer(str(customer_id))
    if not resolved_user_id:
        log.warning("Ignoring Stripe subscription %s without a mapped user_id.", subscription_id)
        return False

    tier = metadata.get("tier") or _tier_for_price(price_id)
    if status_value not in ("active", "trialing"):
        # Keep Stripe identifiers, but feature gating will fall back to Free.
        tier = tier if tier in ("pro", "max") else "free"

    _upsert_subscription_row({
        "user_id": resolved_user_id,
        "stripe_customer_id": customer_id,
        "stripe_subscription_id": subscription_id,
        "tier": tier if tier in ("pro", "max") else "free",
        "status": status_value,
        "current_period_end": _timestamp_to_iso(_subscription_period_end(subscription)),
    })
    return True


def _create_or_get_customer(user_id: str, email: Optional[str]) -> str:
    stripe = _get_stripe()
    existing = _find_subscription_row_by_user(user_id)
    customer_id = (existing or {}).get("stripe_customer_id")
    if customer_id:
        return customer_id

    params = {"metadata": {"user_id": user_id}}
    if email:
        params["email"] = email
    customer = stripe.Customer.create(**params)
    customer_id = _stripe_get(customer, "id")

    _upsert_subscription_row({
        "user_id": user_id,
        "stripe_customer_id": customer_id,
        "tier": "free",
        "status": "active",
    })
    return customer_id


@router.get("/plans")
async def get_billing_plans():
    """Return public plan metadata and whether Stripe env is configured."""
    return {
        "plans": PUBLIC_PLANS,
        "stripe_configured": bool(os.getenv("STRIPE_SECRET_KEY", "").strip()),
        "beta_all_max": os.getenv("OPTIONBOT_BETA_ALL_MAX", "true").strip().lower()
        not in ("0", "false", "no", "off"),
    }


@router.post("/checkout", response_model=BillingSessionResponse)
async def create_checkout_session(
    body: CheckoutRequest,
    claims: dict = Depends(get_current_user_claims),
):
    """Create a hosted Stripe Checkout Session for a paid subscription."""
    tier = body.tier.lower().strip()
    billing_period = body.billing_period.lower().strip()
    price_id = _price_id_for(tier, billing_period)
    stripe = _get_stripe()

    user_id = claims["sub"]
    customer_id = _create_or_get_customer(user_id, claims.get("email"))
    success_url = f"{FRONTEND_URL}/account?billing=success&session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{FRONTEND_URL}/account/plans?billing=cancelled"

    session = stripe.checkout.Session.create(
        mode="subscription",
        customer=customer_id,
        client_reference_id=user_id,
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
        allow_promotion_codes=True,
        metadata={"user_id": user_id, "tier": tier, "billing_period": billing_period},
        subscription_data={"metadata": {"user_id": user_id, "tier": tier}},
    )
    return BillingSessionResponse(url=_stripe_get(session, "url"))


@router.post("/portal", response_model=BillingSessionResponse)
async def create_customer_portal_session(claims: dict = Depends(get_current_user_claims)):
    """Create a hosted Stripe Customer Portal Session for the current user."""
    stripe = _get_stripe()
    user_id = claims["sub"]
    subscription = _find_subscription_row_by_user(user_id)
    customer_id = (subscription or {}).get("stripe_customer_id")
    if not customer_id:
        raise HTTPException(status_code=404, detail="No Stripe customer found for this account.")

    session = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=f"{FRONTEND_URL}/account",
    )
    return BillingSessionResponse(url=_stripe_get(session, "url"))


@router.post("/webhook")
async def stripe_webhook(request: Request):
    """Receive Stripe webhook events and sync local subscription state."""
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "").strip()
    if not webhook_secret:
        raise HTTPException(status_code=503, detail="Stripe webhook is not configured.")

    stripe = _get_stripe()
    payload = await request.body()
    signature = request.headers.get("stripe-signature")
    if not signature:
        raise HTTPException(status_code=400, detail="Missing Stripe signature.")

    try:
        event = stripe.Webhook.construct_event(payload, signature, webhook_secret)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid webhook payload.") from exc
    except stripe.error.SignatureVerificationError as exc:
        raise HTTPException(status_code=400, detail="Invalid webhook signature.") from exc

    event_type = _stripe_get(event, "type")
    event_data = _stripe_get(_stripe_get(event, "data", {}), "object", {})

    if event_type == "checkout.session.completed":
        if _stripe_get(event_data, "mode") == "subscription":
            user_id = _stripe_get(event_data, "client_reference_id") or _stripe_get(
                _stripe_get(event_data, "metadata", {}) or {},
                "user_id",
            )
            subscription_id = _stripe_get(event_data, "subscription")
            if subscription_id:
                subscription = stripe.Subscription.retrieve(subscription_id)
                _sync_subscription_from_stripe(subscription, user_id=user_id)
    elif event_type in (
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
    ):
        _sync_subscription_from_stripe(event_data)
    else:
        log.debug("Stripe webhook ignored event type %s", event_type)

    return {"received": True}
