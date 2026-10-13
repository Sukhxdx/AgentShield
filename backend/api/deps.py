"""Shared FastAPI dependencies."""

import hmac
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request

from backend.config import Settings, get_settings
from backend.runtime import Runtime


def get_runtime(request: Request) -> Runtime:
    """Return the objects created with the app."""
    return request.app.state.runtime


def require_api_key(
    settings: Annotated[Settings, Depends(get_settings)],
    x_api_key: Annotated[str | None, Header()] = None,
) -> None:
    """Reject requests that do not present the configured key."""
    expected = settings.api_key
    if not expected:
        return
    provided = x_api_key or ""
    if not hmac.compare_digest(provided.encode("utf-8"), expected.encode("utf-8")):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
