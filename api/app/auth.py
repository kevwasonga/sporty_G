"""API auth. Optional bearer token when API_TOKEN is configured."""

from fastapi import Header, HTTPException

from .config import settings


def require_api_key(authorization: str | None = Header(default=None)) -> None:
    if not settings.api_token:
        return
    if authorization != f"Bearer {settings.api_token}":
        raise HTTPException(status_code=401, detail="Invalid or missing API token")