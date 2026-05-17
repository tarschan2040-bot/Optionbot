"""
backend/routers/public.py -- Public lead capture endpoints.
"""
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from data.supabase_client import SupabaseClient

log = logging.getLogger(__name__)
router = APIRouter()


class NewsletterSignupRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    source: str = Field(default="landing_page", max_length=80)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if "@" not in cleaned or "." not in cleaned.split("@")[-1]:
            raise ValueError("Enter a valid email address.")
        return cleaned


class ContactMessageRequest(BaseModel):
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    email: str = Field(min_length=3, max_length=254)
    message: str = Field(min_length=5, max_length=1000)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if "@" not in cleaned or "." not in cleaned.split("@")[-1]:
            raise ValueError("Enter a valid email address.")
        return cleaned


def _get_supabase() -> SupabaseClient:
    client = SupabaseClient()
    if not client.is_enabled():
        raise HTTPException(status_code=503, detail="Database not available.")
    return client


def _client_ip(request: Request) -> Optional[str]:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip() or None
    return request.client.host if request.client else None


@router.post("/newsletter")
async def subscribe_newsletter(body: NewsletterSignupRequest, request: Request):
    """Save a public newsletter/opportunity-alert signup."""
    supabase = _get_supabase()
    now = datetime.now(timezone.utc).isoformat()
    row = {
        "email": body.email.lower().strip(),
        "source": body.source.strip() or "landing_page",
        "status": "active",
        "ip_address": _client_ip(request),
        "user_agent": request.headers.get("user-agent"),
        "created_at": now,
        "updated_at": now,
    }

    try:
        supabase._client.table("newsletter_subscribers").upsert(
            row,
            on_conflict="email",
        ).execute()
    except Exception as exc:
        log.exception("newsletter signup failed")
        raise HTTPException(status_code=500, detail="Unable to save signup.") from exc

    return {"ok": True, "message": "You are subscribed."}


@router.post("/contact")
async def submit_contact_message(body: ContactMessageRequest, request: Request):
    """Save a public contact message for manual follow-up."""
    supabase = _get_supabase()
    row = {
        "first_name": body.first_name.strip(),
        "last_name": body.last_name.strip(),
        "email": body.email.lower().strip(),
        "message": body.message.strip(),
        "status": "new",
        "ip_address": _client_ip(request),
        "user_agent": request.headers.get("user-agent"),
    }

    try:
        supabase._client.table("contact_messages").insert(row).execute()
    except Exception as exc:
        log.exception("contact message failed")
        raise HTTPException(status_code=500, detail="Unable to send message.") from exc

    return {"ok": True, "message": "Message received."}
