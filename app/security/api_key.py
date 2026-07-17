import secrets
from fastapi import Header
from app.core.config import get_settings
from app.core.exceptions import AppError

async def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """Validate the optional V1 API key without leaking comparison timing."""
    settings = get_settings()
    if not settings.require_api_key:
        return
    if not x_api_key or not settings.api_key or not secrets.compare_digest(x_api_key, settings.api_key):
        raise AppError(401, "INVALID_API_KEY", "A valid API key is required.")
