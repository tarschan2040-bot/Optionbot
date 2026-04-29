"""
backend/auth.py — Supabase JWT authentication for FastAPI
=========================================================
Provides a FastAPI dependency `get_current_user` that:
  1. Extracts the Bearer token from the Authorization header
  2. Verifies it against Supabase's JWKS (ES256 public key)
  3. Returns the authenticated user_id (UUID string)

Usage in routers:
    from backend.auth import get_current_user

    @router.get("/protected")
    async def protected_route(user_id: str = Depends(get_current_user)):
        ...

Environment variables required:
    SUPABASE_URL — your Supabase project URL (already in .env)
"""
import os
import json
import logging
import time
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt, jwk
from jose.utils import base64url_decode

log = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
JWKS_URL = f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json" if SUPABASE_URL else ""

# Cache the JWKS keys so we don't fetch on every request
_jwks_cache: Optional[dict] = None
_jwks_cache_time: float = 0
_JWKS_CACHE_TTL = 3600  # re-fetch every hour

# FastAPI security scheme
_bearer_scheme = HTTPBearer()


# ── JWKS fetching ─────────────────────────────────────────────────────────

def _fetch_jwks() -> dict:
    """Fetch the JWKS from Supabase's well-known endpoint."""
    global _jwks_cache, _jwks_cache_time

    # Return cache if fresh
    if _jwks_cache and (time.time() - _jwks_cache_time) < _JWKS_CACHE_TTL:
        return _jwks_cache

    if not JWKS_URL:
        raise RuntimeError("SUPABASE_URL not set — cannot fetch JWKS.")

    import urllib.request
    log.info("Fetching JWKS from %s", JWKS_URL)
    try:
        req = urllib.request.Request(JWKS_URL)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            _jwks_cache = data
            _jwks_cache_time = time.time()
            log.info("JWKS fetched: %d key(s)", len(data.get("keys", [])))
            return data
    except Exception as e:
        log.error("Failed to fetch JWKS: %s", e)
        # Return stale cache if available
        if _jwks_cache:
            log.warning("Using stale JWKS cache.")
            return _jwks_cache
        raise


def _get_signing_key(token: str) -> dict:
    """
    Extract the correct signing key from JWKS based on the token's 'kid' header.
    """
    jwks = _fetch_jwks()
    keys = jwks.get("keys", [])

    # Decode token header to get kid
    header = jwt.get_unverified_header(token)
    kid = header.get("kid")
    alg = header.get("alg", "ES256")

    for key in keys:
        if key.get("kid") == kid:
            return key

    # If no kid match, try the first key
    if keys:
        log.warning("No kid match for '%s', using first available key.", kid)
        return keys[0]

    raise RuntimeError("No signing keys found in JWKS.")


# ── Dependency ────────────────────────────────────────────────────────────

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> str:
    """
    Verify the Supabase JWT and return the user_id (sub claim).

    Supports both ES256 (newer Supabase) and HS256 (older Supabase).

    Raises 401 if:
      - No token provided
      - Token is expired
      - Token signature is invalid
    """
    if not SUPABASE_URL:
        log.error("SUPABASE_URL not set — cannot verify tokens.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Auth not configured on server.",
        )

    token = credentials.credentials
    try:
        # Get the signing key from JWKS
        key_data = _get_signing_key(token)
        alg = key_data.get("alg", "ES256")

        # Build the public key from JWK
        public_key = jwk.construct(key_data, algorithm=alg)

        # Decode and verify
        payload = jwt.decode(
            token,
            public_key,
            algorithms=[alg],
            options={"verify_aud": False},
        )

        user_id: str = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token missing user ID.",
            )
        return user_id

    except JWTError as e:
        log.warning("JWT verification failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        log.error("Auth error: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed.",
            headers={"WWW-Authenticate": "Bearer"},
        )
