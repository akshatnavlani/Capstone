"""Shared-secret API-key auth for write endpoints.

Deliberately basic: one shared secret via X-API-Key, no per-track keys or
roles. Disabled entirely when API_KEY isn't set (local dev default) so it
never blocks running the app without configuration -- set API_KEY in .env
to require it.
"""

from fastapi import Header, HTTPException

from app.config import settings


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    if not settings.api_key:
        return  # auth disabled -- no API_KEY configured
    if x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Missing or invalid X-API-Key header")
