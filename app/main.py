from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import HTTPException, RequestValidationError
from slowapi import Limiter
from slowapi.util import get_remote_address
from .config import settings
from .db import init_db
from .routers import merchants as merchants_router
from .routers import crm as crm_router
from .exceptions import (
    APIException,
    api_exception_handler,
    http_exception_handler,
    validation_exception_handler,
    general_exception_handler
)
import logging

logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)

def create_app():
    app = FastAPI(
        title="CRM Service API",
        version="1.0",
        debug=settings.DEBUG
    )

    # CORS
    allowed = [o.strip() for o in settings.CORS_ALLOWED_ORIGINS.split(",")]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed if allowed != ["*"] else ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register exception handlers for standardized error responses
    app.add_exception_handler(APIException, api_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)

    @app.on_event("startup")
    async def _startup():
        await init_db()
        logger.info("CRM Service database initialized")

    @app.on_event("shutdown")
    async def _shutdown():
        logger.info("CRM Service shutting down")

    # Rate limit example: 100 req/min per IP on all endpoints
    @app.middleware("http")
    async def rate_limit(request: Request, call_next):
        # You can selectively apply limiter here or with decorators per route
        response = await call_next(request)
        return response

    # Include routers
    app.include_router(merchants_router.router)
    app.include_router(crm_router.router)

    @app.get("/healthz")
    async def healthz():
        """Health check endpoint with database connectivity."""
        from .response_models import success_response

        try:
            # Test database connection
            from .db import pool
            if pool:
                async with pool.acquire() as conn:
                    await conn.fetchval("SELECT 1")
                db_status = "connected"
            else:
                db_status = "not_initialized"
        except Exception as e:
            db_status = f"error: {str(e)}"

        return success_response(
            message="CRM Service is healthy",
            data={
                "database": db_status,
                "environment": settings.ENVIRONMENT,
                "version": "1.0",
                "service": "crm"
            }
        )

    return app

app = create_app()
