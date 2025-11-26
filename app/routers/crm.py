"""CRM Integration API - Generic CRM Integration Endpoints"""

from fastapi import APIRouter, Depends, HTTPException
from asyncpg import Connection
from datetime import datetime, timezone
import logging
import json

from ..deps import get_current_merchant
from ..db import get_conn
from ..services.crm import (
    crm_manager,
    CRMAuthError,
    CRMAPIError,
    CRMType
)
from ..models.crm import (
    CRMValidateRequest,
    CRMConnectRequest
)
from ..config import settings
from ..response_models import success_response, error_response, ErrorCodes

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/crm", tags=["crm"])


@router.post("/validate")
async def validate_crm_credentials(
    request: CRMValidateRequest,
    merchant=Depends(get_current_merchant)
):
    """
    Validate CRM credentials without saving them.

    This endpoint allows frontend to test CRM credentials before connecting.
    It works with all supported CRM types (Klaviyo, Salesforce, Creatio, etc.)

    Requires authentication via Firebase ID token.
    """
    merchant_id = merchant["merchant_id"]

    try:
        logger.info(f"Validating {request.crm_type} credentials for merchant {merchant_id}")

        # Convert crm_type string to CRMType enum
        try:
            crm_type_enum = CRMType(request.crm_type)
        except ValueError:
            return error_response(
                message=f"Unsupported CRM type: {request.crm_type}",
                error_code=ErrorCodes.INVALID_INPUT,
                details={"field": "crm_type"}
            ), 400

        # Validate credentials using CRM manager
        try:
            is_valid = await crm_manager.validate_credentials(
                crm_type_enum,
                request.credentials
            )

            if is_valid:
                logger.info(f"{request.crm_type} credentials validated successfully for merchant {merchant_id}")
                return success_response(
                    message=f"{request.crm_type.capitalize()} credentials are valid",
                    data={
                        "crm_type": request.crm_type,
                        "is_valid": True
                    }
                )
            else:
                return error_response(
                    message=f"Invalid {request.crm_type} credentials",
                    error_code=ErrorCodes.CRM_INVALID_CREDENTIALS,
                    details={"crm_type": request.crm_type}
                ), 400

        except CRMAuthError as e:
            logger.warning(f"{request.crm_type} authentication failed for merchant {merchant_id}: {str(e)}")
            return error_response(
                message=str(e),
                error_code=ErrorCodes.CRM_INVALID_CREDENTIALS,
                details={
                    "crm_type": request.crm_type,
                    "field": "credentials"
                }
            ), 401

        except CRMAPIError as e:
            logger.error(f"{request.crm_type} API error for merchant {merchant_id}: {str(e)}")
            return error_response(
                message=f"Failed to connect to {request.crm_type}. Please try again later.",
                error_code=ErrorCodes.CRM_CONNECTION_FAILED,
                details={
                    "crm_type": request.crm_type,
                    "error": str(e)
                }
            ), 503

        except ValueError as e:
            logger.error(f"Unregistered CRM service: {request.crm_type}")
            return error_response(
                message=str(e),
                error_code=ErrorCodes.CRM_INVALID_TYPE,
                details={"crm_type": request.crm_type}
            ), 400

    except Exception as e:
        logger.error(
            f"Unexpected error validating {request.crm_type} credentials for merchant {merchant_id}: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred while validating {request.crm_type} credentials"
        )


@router.post("/connect")
async def connect_crm(
    request: CRMConnectRequest,
    merchant=Depends(get_current_merchant),
    conn: Connection = Depends(get_conn)
):
    """
    Connect a CRM integration for the current merchant.

    This endpoint:
    1. Validates the CRM credentials
    2. Encrypts and saves the credentials to the database
    3. Stores optional settings (sync_frequency, field_mapping, etc.)
    4. Returns the integration details

    Supports all CRM types: Klaviyo, Salesforce, Creatio, etc.

    Requires authentication via Firebase ID token.
    """
    merchant_id = merchant["merchant_id"]

    try:
        logger.info(f"Connecting {request.crm_type} integration for merchant {merchant_id}")

        # Convert crm_type string to CRMType enum
        try:
            crm_type_enum = CRMType(request.crm_type)
        except ValueError:
            return error_response(
                message=f"Unsupported CRM type: {request.crm_type}",
                error_code=ErrorCodes.CRM_INVALID_TYPE,
                details={"field": "crm_type"}
            ), 400

        # Step 1: Validate credentials
        try:
            is_valid = await crm_manager.validate_credentials(
                crm_type_enum,
                request.credentials
            )
            if not is_valid:
                return error_response(
                    message="Invalid CRM credentials",
                    error_code=ErrorCodes.CRM_INVALID_CREDENTIALS
                ), 400
        except CRMAuthError as e:
            logger.warning(f"{request.crm_type} authentication failed for merchant {merchant_id}: {str(e)}")
            return error_response(
                message=str(e),
                error_code=ErrorCodes.CRM_INVALID_CREDENTIALS,
                details={"field": "credentials"}
            ), 401
        except CRMAPIError as e:
            logger.error(f"{request.crm_type} API error for merchant {merchant_id}: {str(e)}")
            return error_response(
                message=f"Failed to connect to {request.crm_type}. Please try again later.",
                error_code=ErrorCodes.CRM_CONNECTION_FAILED,
                details={"error": str(e)}
            ), 503

        # Step 2: Check if integration already exists
        check_query = """
            SELECT integration_id, is_active
            FROM crm_integrations
            WHERE merchant_id = $1 AND crm_type = $2
        """
        existing = await conn.fetchrow(check_query, merchant_id, request.crm_type)

        # Step 3: Prepare data
        now = datetime.now(timezone.utc)
        credentials_json = json.dumps(request.credentials)
        settings_json = json.dumps(request.settings) if request.settings else json.dumps({})

        if existing:
            # Update existing integration
            integration_id = existing["integration_id"]
            logger.info(f"Updating existing {request.crm_type} integration {integration_id} for merchant {merchant_id}")

            update_query = """
                UPDATE crm_integrations
                SET
                    encrypted_credentials = encrypt_credentials($1::jsonb, $2),
                    settings = $3::jsonb,
                    is_active = TRUE,
                    updated_at = $4,
                    sync_status = 'connected',
                    sync_error = NULL
                WHERE merchant_id = $5 AND crm_type = $6
                RETURNING integration_id, merchant_id, crm_type, settings, is_active,
                          created_at, updated_at, last_sync_at, sync_status
            """

            result = await conn.fetchrow(
                update_query,
                credentials_json,
                settings.CRM_ENCRYPTION_KEY,
                settings_json,
                now,
                merchant_id,
                request.crm_type
            )
        else:
            # Create new integration
            logger.info(f"Creating new {request.crm_type} integration for merchant {merchant_id}")

            insert_query = """
                INSERT INTO crm_integrations (
                    merchant_id, crm_type, encrypted_credentials, settings,
                    is_active, created_at, updated_at, sync_status
                )
                VALUES (
                    $1, $2,
                    encrypt_credentials($3::jsonb, $4),
                    $5::jsonb, TRUE, $6, $7, 'connected'
                )
                RETURNING integration_id, merchant_id, crm_type, settings, is_active,
                          created_at, updated_at, last_sync_at, sync_status
            """

            result = await conn.fetchrow(
                insert_query,
                merchant_id,
                request.crm_type,
                credentials_json,
                settings.CRM_ENCRYPTION_KEY,
                settings_json,
                now,
                now
            )

        # Step 4: Format and return response
        integration_data = {
            "integration_id": str(result["integration_id"]),
            "merchant_id": str(result["merchant_id"]),
            "crm_type": result["crm_type"],
            "is_active": result["is_active"],
            "settings": result["settings"],
            "created_at": result["created_at"].isoformat(),
            "updated_at": result["updated_at"].isoformat(),
            "last_sync_at": result["last_sync_at"].isoformat() if result["last_sync_at"] else None,
            "sync_status": result["sync_status"]
        }

        logger.info(f"{request.crm_type} integration connected successfully for merchant {merchant_id}")

        return success_response(
            message=f"{request.crm_type.capitalize()} integration connected successfully",
            data={"integration": integration_data}
        )

    except Exception as e:
        logger.error(f"Unexpected error connecting {request.crm_type} for merchant {merchant_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred while connecting {request.crm_type} integration"
        )


@router.get("/{crm_type}/status")
async def get_crm_status(
    crm_type: str,
    merchant=Depends(get_current_merchant),
    conn: Connection = Depends(get_conn)
):
    """
    Get the current CRM integration status for the authenticated merchant.

    Returns integration details if connected, or null if not connected.
    Works for any CRM type: klaviyo, salesforce, creatio, etc.
    """
    merchant_id = merchant["merchant_id"]

    try:
        # Validate CRM type
        try:
            CRMType(crm_type.lower())
        except ValueError:
            return error_response(
                message=f"Unsupported CRM type: {crm_type}",
                error_code=ErrorCodes.CRM_INVALID_TYPE
            ), 400

        query = """
            SELECT integration_id, merchant_id, crm_type, settings, is_active,
                   created_at, updated_at, last_sync_at, sync_status, sync_error
            FROM crm_integrations
            WHERE merchant_id = $1 AND crm_type = $2
        """

        result = await conn.fetchrow(query, merchant_id, crm_type.lower())

        if not result:
            return success_response(
                message=f"No {crm_type} integration found",
                data={"integration": None}
            )

        integration_data = {
            "integration_id": str(result["integration_id"]),
            "merchant_id": str(result["merchant_id"]),
            "crm_type": result["crm_type"],
            "is_active": result["is_active"],
            "settings": result["settings"],
            "created_at": result["created_at"].isoformat(),
            "updated_at": result["updated_at"].isoformat(),
            "last_sync_at": result["last_sync_at"].isoformat() if result["last_sync_at"] else None,
            "sync_status": result["sync_status"],
            "sync_error": result["sync_error"]
        }

        return success_response(
            message=f"{crm_type.capitalize()} integration status retrieved",
            data={"integration": integration_data}
        )

    except Exception as e:
        logger.error(f"Error retrieving {crm_type} status for merchant {merchant_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve {crm_type} integration status"
        )


@router.delete("/{crm_type}/disconnect")
async def disconnect_crm(
    crm_type: str,
    merchant=Depends(get_current_merchant),
    conn: Connection = Depends(get_conn)
):
    """
    Disconnect a CRM integration for the authenticated merchant.

    This marks the integration as inactive but does not delete the record.
    Works for any CRM type: klaviyo, salesforce, creatio, etc.
    """
    merchant_id = merchant["merchant_id"]

    try:
        # Validate CRM type
        try:
            CRMType(crm_type.lower())
        except ValueError:
            return error_response(
                message=f"Unsupported CRM type: {crm_type}",
                error_code=ErrorCodes.CRM_INVALID_TYPE
            ), 400

        query = """
            UPDATE crm_integrations
            SET
                is_active = FALSE,
                sync_status = 'disconnected',
                updated_at = $1
            WHERE merchant_id = $2 AND crm_type = $3 AND is_active = TRUE
            RETURNING integration_id
        """

        result = await conn.fetchrow(query, datetime.now(timezone.utc), merchant_id, crm_type.lower())

        if not result:
            return error_response(
                message=f"No active {crm_type} integration found",
                error_code=ErrorCodes.CRM_INTEGRATION_NOT_FOUND
            ), 404

        logger.info(f"{crm_type} integration disconnected for merchant {merchant_id}")

        return success_response(
            message=f"{crm_type.capitalize()} integration disconnected successfully",
            data={
                "integration_id": str(result["integration_id"]),
                "disconnected_at": datetime.now(timezone.utc).isoformat()
            }
        )

    except Exception as e:
        logger.error(f"Error disconnecting {crm_type} for merchant {merchant_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to disconnect {crm_type} integration"
        )


@router.get("/list")
async def list_integrations(
    merchant=Depends(get_current_merchant),
    conn: Connection = Depends(get_conn)
):
    """
    List all CRM integrations for the authenticated merchant.

    Returns a list of all connected CRMs with their status.
    """
    merchant_id = merchant["merchant_id"]

    try:
        query = """
            SELECT integration_id, merchant_id, crm_type, settings, is_active,
                   created_at, updated_at, last_sync_at, sync_status, sync_error
            FROM crm_integrations
            WHERE merchant_id = $1
            ORDER BY created_at DESC
        """

        results = await conn.fetch(query, merchant_id)

        integrations = []
        for row in results:
            integrations.append({
                "integration_id": str(row["integration_id"]),
                "merchant_id": str(row["merchant_id"]),
                "crm_type": row["crm_type"],
                "is_active": row["is_active"],
                "settings": row["settings"],
                "created_at": row["created_at"].isoformat(),
                "updated_at": row["updated_at"].isoformat(),
                "last_sync_at": row["last_sync_at"].isoformat() if row["last_sync_at"] else None,
                "sync_status": row["sync_status"],
                "sync_error": row["sync_error"]
            })

        return success_response(
            message="Integrations retrieved successfully",
            data={
                "integrations": integrations,
                "total": len(integrations)
            }
        )

    except Exception as e:
        logger.error(f"Error listing integrations for merchant {merchant_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to list integrations"
        )
