"""
Standardized response models for consistent API responses
"""
from pydantic import BaseModel
from typing import Any, Optional


class APIResponse(BaseModel):
    """Standard API response format"""
    success: bool
    message: str
    data: Optional[Any] = None
    error_code: Optional[str] = None


class ErrorResponse(BaseModel):
    """Standard error response format"""
    success: bool = False
    message: str
    error_code: str
    details: Optional[dict] = None


# Common success responses
def success_response(message: str = "Success", data: Any = None) -> dict:
    """Create a standardized success response"""
    return {
        "success": True,
        "message": message,
        "data": data
    }


def error_response(message: str, error_code: str = "ERROR", details: dict = None) -> dict:
    """Create a standardized error response"""
    response = {
        "success": False,
        "message": message,
        "error_code": error_code
    }
    if details:
        response["details"] = details
    return response


# Common error codes
class ErrorCodes:
    """Standard error codes for the API"""

    # Authentication errors (AUTH_*)
    INVALID_TOKEN = "AUTH_INVALID_TOKEN"
    MISSING_TOKEN = "AUTH_MISSING_TOKEN"
    TOKEN_EXPIRED = "AUTH_TOKEN_EXPIRED"
    TOKEN_REVOKED = "AUTH_TOKEN_REVOKED"
    UNAUTHORIZED = "AUTH_UNAUTHORIZED"

    # Merchant errors (MERCHANT_*)
    MERCHANT_NOT_FOUND = "MERCHANT_NOT_FOUND"
    MERCHANT_EXISTS = "MERCHANT_ALREADY_EXISTS"
    EMAIL_NOT_VERIFIED = "MERCHANT_EMAIL_NOT_VERIFIED"

    # Permission errors (PERM_*)
    FORBIDDEN = "PERM_FORBIDDEN"
    INSUFFICIENT_PERMISSIONS = "PERM_INSUFFICIENT"
    ADMIN_REQUIRED = "PERM_ADMIN_REQUIRED"

    # Validation errors (VAL_*)
    VALIDATION_ERROR = "VAL_VALIDATION_ERROR"
    INVALID_INPUT = "VAL_INVALID_INPUT"
    MISSING_FIELD = "VAL_MISSING_FIELD"
    INVALID_EMAIL = "VAL_INVALID_EMAIL"
    INVALID_PASSWORD = "VAL_INVALID_PASSWORD"

    # Resource errors (RES_*)
    NOT_FOUND = "RES_NOT_FOUND"
    ALREADY_EXISTS = "RES_ALREADY_EXISTS"

    # Server errors (SRV_*)
    INTERNAL_ERROR = "SRV_INTERNAL_ERROR"
    DATABASE_ERROR = "SRV_DATABASE_ERROR"
    EXTERNAL_SERVICE_ERROR = "SRV_EXTERNAL_SERVICE"

    # Rate limiting (RATE_*)
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"

    # CRM errors (CRM_*)
    CRM_INTEGRATION_NOT_FOUND = "CRM_INTEGRATION_NOT_FOUND"
    CRM_INTEGRATION_EXISTS = "CRM_INTEGRATION_EXISTS"
    CRM_INVALID_CREDENTIALS = "CRM_INVALID_CREDENTIALS"
    CRM_CONNECTION_FAILED = "CRM_CONNECTION_FAILED"
    CRM_SYNC_FAILED = "CRM_SYNC_FAILED"
    CRM_INVALID_TYPE = "CRM_INVALID_TYPE"


# HTTP status code mapping
HTTP_STATUS_CODES = {
    # Success
    "success": 200,

    # Client errors
    ErrorCodes.INVALID_TOKEN: 401,
    ErrorCodes.MISSING_TOKEN: 401,
    ErrorCodes.TOKEN_EXPIRED: 401,
    ErrorCodes.TOKEN_REVOKED: 401,
    ErrorCodes.UNAUTHORIZED: 401,

    ErrorCodes.FORBIDDEN: 403,
    ErrorCodes.INSUFFICIENT_PERMISSIONS: 403,
    ErrorCodes.ADMIN_REQUIRED: 403,

    ErrorCodes.MERCHANT_NOT_FOUND: 404,
    ErrorCodes.NOT_FOUND: 404,
    ErrorCodes.CRM_INTEGRATION_NOT_FOUND: 404,

    ErrorCodes.MERCHANT_EXISTS: 409,
    ErrorCodes.ALREADY_EXISTS: 409,
    ErrorCodes.CRM_INTEGRATION_EXISTS: 409,

    ErrorCodes.VALIDATION_ERROR: 400,
    ErrorCodes.INVALID_INPUT: 400,
    ErrorCodes.MISSING_FIELD: 400,
    ErrorCodes.INVALID_EMAIL: 400,
    ErrorCodes.INVALID_PASSWORD: 400,
    ErrorCodes.CRM_INVALID_CREDENTIALS: 400,
    ErrorCodes.CRM_INVALID_TYPE: 400,

    ErrorCodes.RATE_LIMIT_EXCEEDED: 429,

    # CRM errors
    ErrorCodes.CRM_CONNECTION_FAILED: 502,
    ErrorCodes.CRM_SYNC_FAILED: 500,

    # Server errors
    ErrorCodes.INTERNAL_ERROR: 500,
    ErrorCodes.DATABASE_ERROR: 500,
    ErrorCodes.EXTERNAL_SERVICE_ERROR: 502,
}


def get_status_code(error_code: str) -> int:
    """Get HTTP status code for error code"""
    return HTTP_STATUS_CODES.get(error_code, 500)
