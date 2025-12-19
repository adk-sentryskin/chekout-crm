"""Dependencies for CRM microservice"""
from fastapi import Header, HTTPException
from uuid import UUID
from typing import Optional
from .config import settings
import logging

logger = logging.getLogger(__name__)


async def get_user_id(x_user_id: str = Header(..., description="Firebase User ID")) -> UUID:
    """
    Extract and validate user_id from request headers.

    Args:
        x_user_id: UUID string from X-User-Id header

    Returns:
        UUID: Validated user UUID

    Raises:
        HTTPException: If header is missing or invalid UUID
    """
    try:
        user_uuid = UUID(x_user_id)
        logger.debug(f"User ID extracted: {user_uuid}")
        return user_uuid
    except ValueError:
        logger.warning(f"Invalid user_id format: {x_user_id}")
        raise HTTPException(
            status_code=400,
            detail=f"Invalid X-User-Id header: must be a valid UUID"
        )


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
