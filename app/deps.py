"""Dependencies for CRM microservice"""
from fastapi import Header, HTTPException
from typing import Optional
from .config import settings
import logging

logger = logging.getLogger(__name__)


async def get_user_id(x_user_id: str = Header(..., description="Firebase User ID")) -> str:
    """
    Extract and validate user_id from request headers.

    Args:
        x_user_id: Firebase user ID from X-User-Id header

    Returns:
        str: Validated user ID

    Raises:
        HTTPException: If header is missing or invalid
    """
    if not x_user_id or not x_user_id.strip():
        logger.warning("Empty user_id provided")
        raise HTTPException(
            status_code=400,
            detail="Invalid X-User-Id header: cannot be empty"
        )

    logger.debug(f"User ID extracted: {x_user_id}")
    return x_user_id.strip()


async def verify_api_key(x_api_key: Optional[str] = Header(None, description="API Key for service-to-service auth")) -> bool:
    """
    Optional API key verification for service-to-service authentication.

    Only validates if API_KEY is configured in settings.
    Use this dependency on endpoints that should only be called by trusted services.

    Args:
        x_api_key: API key from X-Api-Key header

    Returns:
        bool: True if valid or not configured

    Raises:
        HTTPException: If API key is invalid
    """
    if settings.API_KEY is None:
        # API key auth not configured, allow request
        return True

    if x_api_key is None:
        raise HTTPException(
            status_code=401,
            detail="Missing X-Api-Key header"
        )

    if x_api_key != settings.API_KEY:
        logger.warning(f"Invalid API key attempt")
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )

    return True
