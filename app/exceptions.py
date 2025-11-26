"""
Custom exceptions and exception handlers for standardized error responses
"""
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import HTTPException, RequestValidationError
from .response_models import error_response, ErrorCodes, get_status_code


class APIException(Exception):
    """Base exception for API errors with standardized format"""

    def __init__(
        self,
        message: str,
        error_code: str = ErrorCodes.INTERNAL_ERROR,
        details: dict = None
    ):
        self.message = message
        self.error_code = error_code
        self.details = details
        super().__init__(self.message)


class AuthenticationError(APIException):
    """Authentication related errors"""

    def __init__(self, message: str, error_code: str = ErrorCodes.UNAUTHORIZED, details: dict = None):
        super().__init__(message, error_code, details)


class AuthorizationError(APIException):
    """Authorization/Permission related errors"""

    def __init__(self, message: str, error_code: str = ErrorCodes.FORBIDDEN, details: dict = None):
        super().__init__(message, error_code, details)


class ValidationError(APIException):
    """Validation related errors"""

    def __init__(self, message: str, error_code: str = ErrorCodes.INVALID_INPUT, details: dict = None):
        super().__init__(message, error_code, details)


class NotFoundError(APIException):
    """Resource not found errors"""

    def __init__(self, message: str, error_code: str = ErrorCodes.NOT_FOUND, details: dict = None):
        super().__init__(message, error_code, details)


class BadRequestError(APIException):
    """Bad request / invalid input errors"""

    def __init__(self, message: str, error_code: str = ErrorCodes.INVALID_INPUT, details: dict = None):
        super().__init__(message, error_code, details)


# Exception handlers

async def api_exception_handler(request: Request, exc: APIException) -> JSONResponse:
    """Handler for custom API exceptions"""
    status_code = get_status_code(exc.error_code)

    return JSONResponse(
        status_code=status_code,
        content=error_response(
            message=exc.message,
            error_code=exc.error_code,
            details=exc.details
        )
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Convert FastAPI HTTPException to standardized format"""

    # Map HTTP status codes to error codes
    error_code_map = {
        401: ErrorCodes.UNAUTHORIZED,
        403: ErrorCodes.FORBIDDEN,
        404: ErrorCodes.NOT_FOUND,
        409: ErrorCodes.ALREADY_EXISTS,
        429: ErrorCodes.RATE_LIMIT_EXCEEDED,
        500: ErrorCodes.INTERNAL_ERROR,
    }

    error_code = error_code_map.get(exc.status_code, ErrorCodes.INTERNAL_ERROR)

    # Try to extract more specific error code from detail message
    detail = str(exc.detail)
    if "Missing Authorization header" in detail or "authorization" in detail.lower():
        error_code = ErrorCodes.MISSING_TOKEN
    elif "Invalid ID token" in detail or "invalid" in detail.lower() and "token" in detail.lower():
        error_code = ErrorCodes.INVALID_TOKEN
    elif "revoked" in detail.lower():
        error_code = ErrorCodes.TOKEN_REVOKED
    elif "Merchant not found" in detail:
        error_code = ErrorCodes.MERCHANT_NOT_FOUND
    elif "admin role required" in detail.lower() or "admin" in detail.lower():
        error_code = ErrorCodes.ADMIN_REQUIRED

    return JSONResponse(
        status_code=exc.status_code,
        content=error_response(
            message=detail,
            error_code=error_code
        )
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Convert Pydantic validation errors to standardized format"""

    errors = exc.errors()
    error_details = {
        "validation_errors": [
            {
                "field": ".".join(str(loc) for loc in error["loc"]),
                "message": error["msg"],
                "type": error["type"]
            }
            for error in errors
        ]
    }

    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=error_response(
            message="Validation error",
            error_code=ErrorCodes.INVALID_INPUT,
            details=error_details
        )
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handler for unexpected exceptions"""

    # Log the error (in production, you'd want proper logging)
    import traceback
    print(f"Unhandled exception: {exc}")
    print(traceback.format_exc())

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response(
            message="An unexpected error occurred",
            error_code=ErrorCodes.INTERNAL_ERROR,
            details={"error": str(exc)} if request.app.debug else None
        )
    )
