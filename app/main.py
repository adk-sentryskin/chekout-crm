from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import HTTPException, RequestValidationError
from .config import settings
from .db import init_db
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

def create_app():
    app = FastAPI(
        title="CRM Microservice API",
        version="1.0",
        description="Microservice for managing CRM integrations and data synchronization",
        debug=settings.DEBUG
    )

    # CORS (optional - only if CRM service needs direct frontend access)
    if settings.CORS_ALLOWED_ORIGINS != "*":
        allowed = [o.strip() for o in settings.CORS_ALLOWED_ORIGINS.split(",")]
    else:
        allowed = ["*"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed,
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
        logger.info("✅ CRM Microservice started successfully")
        logger.info(f"   Environment: {settings.ENVIRONMENT}")
        logger.info(f"   Port: {settings.PORT}")
        logger.info(f"   Database: Connected")

    @app.on_event("shutdown")
    async def _shutdown():
        logger.info("CRM Microservice shutting down...")

    # Include CRM router only (no merchant management)
    app.include_router(crm_router.router)

    @app.get("/healthz")
    async def healthz():
        """
        Health check endpoint with database connectivity.

        Returns service status and database connection status.
        """
        from .response_models import success_response

        try:
            # Test database connection
            from .db import pool
            if pool:
                async with pool.acquire() as conn:
                    # Test basic query
                    await conn.fetchval("SELECT 1")

                    # Check if tables exist
                    tables_exist = await conn.fetchval("""
                        SELECT COUNT(*)
                        FROM information_schema.tables
                        WHERE table_schema = 'crm'
                          AND table_name IN ('crm_integrations', 'crm_sync_logs')
                    """)

                    if tables_exist == 2:
                        db_status = "connected"
                        schema_status = "ready"
                    else:
                        db_status = "connected"
                        schema_status = "missing_tables"
            else:
                db_status = "not_initialized"
                schema_status = "unknown"
        except Exception as e:
            db_status = f"error: {str(e)}"
            schema_status = "error"

        return success_response(
            message="CRM Microservice is healthy",
            data={
                "service": "crm-microservice",
                "version": "2.0",
                "environment": settings.ENVIRONMENT,
                "database": db_status,
                "schema": schema_status,
                "features": [
                    "CRM Integration Management",
                    "Contact Sync",
                    "Event Sync",
                    "Field Mapping",
                    "Multi-CRM Support"
                ]
            }
        )

    @app.get("/")
    async def root():
        """Root endpoint with API information."""
        from .response_models import success_response

        return success_response(
            message="CRM Microservice API",
            data={
                "service": "crm-microservice",
                "version": "2.0",
                "docs": "/docs",
                "health": "/healthz",
                "endpoints": {
                    "integration": [
                        "POST /crm/validate",
                        "POST /crm/connect",
                        "GET /crm/{crm_type}/status",
                        "DELETE /crm/{crm_type}/disconnect",
                        "GET /crm/list"
                    ],
                    "sync": [
                        "POST /crm/sync/contact",
                        "POST /crm/sync/event"
                    ]
                }
            }
        )

    return app

app = create_app()
