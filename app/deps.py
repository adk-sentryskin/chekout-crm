"""Dependencies for CRM microservice"""
from fastapi import Header, HTTPException
from uuid import UUID
from typing import Optional
from .config import settings
import logging

logger = logging.getLogger(__name__)


async def get_merchant_id(x_merchant_id: str = Header(..., description="Merchant UUID")) -> UUID:
    """
    Extract and validate merchant_id from request headers.

    The parent service must provide X-Merchant-Id header with a valid UUID.
    This replaces Firebase authentication - merchant identity is now provided
    by the calling service.

    Args:
        x_merchant_id: UUID string from X-Merchant-Id header

    Returns:
        UUID: Validated merchant UUID

    Raises:
        HTTPException: If header is missing or invalid UUID
    """
    try:
        merchant_uuid = UUID(x_merchant_id)
        logger.debug(f"Merchant ID extracted: {merchant_uuid}")
        return merchant_uuid
    except ValueError:
        logger.warning(f"Invalid merchant_id format: {x_merchant_id}")
        raise HTTPException(
            status_code=400,
            detail=f"Invalid X-Merchant-Id header: must be a valid UUID"
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
