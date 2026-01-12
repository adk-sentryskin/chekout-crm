"""CRM Integration API - Generic CRM Integration Endpoints"""

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from asyncpg import Connection
from datetime import datetime, timezone
from uuid import UUID
from typing import List, Optional, Dict, Any
import logging
import json

from ..deps import get_user_id
from ..db import get_conn
from ..services import (
    crm_manager,
    CRMAuthError,
    CRMAPIError,
    CRMType
)
from ..models.crm import (
    CRMValidateRequest,
    CRMConnectRequest,
    CRMUpdateRequest,
    EventData,
    SyncEventRequest,
    SyncFrequency
)
from ..schemas.standard_contact import StandardContactData, StandardEventData
from ..services.field_mapper import field_mapping_service, FieldMappingError
from ..config import settings
from ..response_models import success_response, error_response, ErrorCodes

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/crm", tags=["crm"])


@router.post("/validate")
async def validate_crm_credentials(
    request: CRMValidateRequest,
    user_id: str = Depends(get_user_id)
):
    """
    Validate CRM credentials without saving them.

    This endpoint allows testing CRM credentials before connecting.
    Works with all supported CRM types (Klaviyo, Salesforce, Creatio, etc.)

    **Headers Required:**
    - X-User-Id: Firebase user ID

    **Request Body:**
    ```json
    {
      "crm_type": "klaviyo",
      "credentials": {"api_key": "pk_..."}
    }
    ```
    """
    try:
        logger.info(f"Validating {request.crm_type} credentials for user {user_id}")

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
                logger.info(f"{request.crm_type} credentials validated successfully for merchant {user_id}")
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
            logger.warning(f"{request.crm_type} authentication failed for merchant {user_id}: {str(e)}")
            return error_response(
                message=str(e),
                error_code=ErrorCodes.CRM_INVALID_CREDENTIALS,
                details={
                    "crm_type": request.crm_type,
                    "field": "credentials"
                }
            ), 401

        except CRMAPIError as e:
            logger.error(f"{request.crm_type} API error for merchant {user_id}: {str(e)}")
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
            f"Unexpected error validating {request.crm_type} credentials for merchant {user_id}: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred while validating {request.crm_type} credentials"
        )


@router.post("/connect")
async def connect_crm(
    request: CRMConnectRequest,
    user_id: str = Depends(get_user_id),
    conn: Connection = Depends(get_conn)
):
    """
    Create a new CRM integration or reconnect a previously disconnected one.

    This endpoint handles both scenarios:
    1. **New Connection**: Creates a new integration if none exists
    2. **Reconnection**: If a disconnected integration exists, it will be reactivated
       with the new credentials and settings

    Validates credentials, encrypts and stores them securely, and configures
    integration settings. Field mapping is handled automatically by the backend.
    Returns 409 only if an active integration already exists.

    **Headers Required:**
    - X-User-Id: Firebase user ID

    **Request Body:**
    ```json
    {
      "crm_type": "klaviyo",
      "credentials": {"api_key": "pk_..."},
      "settings": {
        "enabled_events": ["order_created", "cart_abandoned"]
      }
    }
    ```

    **Response:**
    Returns the created/reactivated integration details including integration_id,
    settings, and sync status. Message will indicate "connected" for new integrations
    or "reconnected" for reactivated ones.

    **Note:** To update an existing active integration, use PATCH /crm/{crm_type}
    """
    try:
        logger.info(f"Connecting {request.crm_type} integration for merchant {user_id}")

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
            logger.warning(f"{request.crm_type} authentication failed for merchant {user_id}: {str(e)}")
            return error_response(
                message=str(e),
                error_code=ErrorCodes.CRM_INVALID_CREDENTIALS,
                details={"field": "credentials"}
            ), 401
        except CRMAPIError as e:
            logger.error(f"{request.crm_type} API error for merchant {user_id}: {str(e)}")
            return error_response(
                message=f"Failed to connect to {request.crm_type}. Please try again later.",
                error_code=ErrorCodes.CRM_CONNECTION_FAILED,
                details={"error": str(e)}
            ), 503

        # Step 2: Check if integration already exists
        check_query = """
            SELECT integration_id, is_active
            FROM crm.crm_integrations
            WHERE user_id = $1 AND crm_type = $2
        """
        existing = await conn.fetchrow(check_query, user_id, request.crm_type)

        if existing:
            # If integration exists (active or inactive), tell user to use PATCH
            status_str = "active" if existing["is_active"] else "inactive"
            return error_response(
                message=f"{request.crm_type.capitalize()} integration already exists and is {status_str}. Use PATCH /crm/{request.crm_type} to update or reconnect.",
                error_code=ErrorCodes.INVALID_INPUT,
                details={
                    "integration_id": str(existing["integration_id"]),
                    "is_active": existing["is_active"]
                }
            ), 409

        # Step 3: Validate selected_fields if provided
        valid_fields = ["first_name", "last_name", "email", "phone"]
        if request.selected_fields is not None:
            invalid_fields = [f for f in request.selected_fields if f not in valid_fields]
            if invalid_fields:
                return error_response(
                    message=f"Invalid fields in selected_fields: {', '.join(invalid_fields)}",
                    error_code=ErrorCodes.INVALID_INPUT,
                    details={
                        "field": "selected_fields",
                        "invalid_fields": invalid_fields,
                        "valid_fields": valid_fields
                    }
                ), 400

        # Step 4: Prepare data
        now = datetime.now(timezone.utc)
        credentials_json = json.dumps(request.credentials)

        # Automatically set sync_frequency to real-time
        merged_settings = request.settings.copy() if request.settings else {}

        # Warn if deprecated field_mapping is provided
        if "field_mapping" in merged_settings:
            logger.warning(
                f"Deprecated 'field_mapping' provided for {request.crm_type} integration by merchant {user_id}. "
                "This will be ignored. Please use standard contact schema with /sync/contact endpoint."
            )
            # Remove field_mapping from settings (it's deprecated)
            merged_settings.pop("field_mapping", None)

        merged_settings["sync_frequency"] = SyncFrequency.REAL_TIME.value

        # Store selected_fields and lead_quality in settings
        if request.selected_fields is not None:
            merged_settings["selected_fields"] = request.selected_fields
        if request.lead_quality is not None:
            merged_settings["lead_quality"] = request.lead_quality

        settings_json = json.dumps(merged_settings)

        # Step 5: Create new integration
        logger.info(f"Creating new {request.crm_type} integration for merchant {user_id}")

        insert_query = """
            INSERT INTO crm.crm_integrations (
                user_id, crm_type, encrypted_credentials, settings,
                is_active, created_at, updated_at, sync_status
            )
            VALUES (
                $1, $2,
                encrypt_credentials($3::jsonb, $4),
                $5::jsonb, TRUE, $6, $7, 'connected'
            )
            RETURNING integration_id, user_id, crm_type, settings, is_active,
                      created_at, updated_at, last_sync_at, sync_status
        """

        result = await conn.fetchrow(
            insert_query,
            user_id,
            request.crm_type,
            credentials_json,
            settings.CRM_ENCRYPTION_KEY,
            settings_json,
            now,
            now
        )

        # Step 6: Format and return response
        settings_data = result["settings"]
        # Parse settings if it's a JSON string
        if isinstance(settings_data, str):
            settings_data = json.loads(settings_data)

        integration_data = {
            "integration_id": str(result["integration_id"]),
            "user_id": str(result["user_id"]),
            "crm_type": result["crm_type"],
            "is_active": result["is_active"],
            "settings": settings_data,
            "created_at": result["created_at"].isoformat(),
            "updated_at": result["updated_at"].isoformat(),
            "last_sync_at": result["last_sync_at"].isoformat() if result["last_sync_at"] else None,
            "sync_status": result["sync_status"]
        }

        logger.info(f"{request.crm_type} integration connected successfully for merchant {user_id}")

        return success_response(
            message=f"{request.crm_type.capitalize()} integration connected successfully",
            data={"integration": integration_data}
        )

    except Exception as e:
        # Enhanced error logging for debugging
        error_msg = str(e)
        logger.error(
            f"Unexpected error connecting {request.crm_type} for merchant {user_id}: {error_msg}",
            exc_info=True
        )

        # Check for common error patterns
        if "encrypt_credentials" in error_msg or "function" in error_msg.lower():
            logger.error("Database encryption function may not exist. Run migrations to create it.")
            detail = f"Database configuration error while connecting {request.crm_type} integration. Please contact support."
        elif "pgcrypto" in error_msg.lower():
            logger.error("pgcrypto extension not installed in database")
            detail = f"Database encryption not configured for {request.crm_type} integration. Please contact support."
        else:
            detail = f"An unexpected error occurred while connecting {request.crm_type} integration"

        raise HTTPException(
            status_code=500,
            detail=detail
        )


@router.patch("/{crm_type}")
async def update_crm(
    crm_type: str,
    request: CRMUpdateRequest,
    user_id: str = Depends(get_user_id),
    conn: Connection = Depends(get_conn)
):
    """
    Update an existing CRM integration for the merchant.

    This endpoint handles:
    1. **Configuration Updates**: Updating settings or fields for an active integration.
    2. **Reconnection (Optional)**: If `reconnect: true` is provided, it reactivates a 
       previously disconnected integration.

    Allows updating credentials, settings, selected_fields, and lead_quality.
    All fields are optional - only provided fields will be updated.

    **Headers Required:**
    - X-User-Id: Firebase user ID

    **Request Body:**
    ```json
    {
      "credentials": {"api_key": "pk_new_key"},
      "selected_fields": ["first_name", "email"],
      "lead_quality": "Warm",
      "settings": {
        "enabled_events": ["order_created"]
      },
      "reconnect": true
    }
    ```

    **Response:**
    Returns the updated integration details.
    """
    try:
        logger.info(f"Updating {crm_type} integration for merchant {user_id}")

        # Validate CRM type
        try:
            crm_type_enum = CRMType(crm_type.lower())
        except ValueError:
            return error_response(
                message=f"Unsupported CRM type: {crm_type}",
                error_code=ErrorCodes.CRM_INVALID_TYPE
            ), 400

        # Step 1: Check if integration exists
        check_query = """
            SELECT integration_id, settings, encrypted_credentials
            FROM crm.crm_integrations
            WHERE user_id = $1 AND crm_type = $2
        """
        existing = await conn.fetchrow(check_query, user_id, crm_type.lower())

        if not existing:
            return error_response(
                message=f"No {crm_type} integration found. Use POST /crm/connect to create one.",
                error_code=ErrorCodes.CRM_INTEGRATION_NOT_FOUND
            ), 404

        # Step 2: Validate credentials if provided
        if request.credentials:
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
                return error_response(
                    message=str(e),
                    error_code=ErrorCodes.CRM_INVALID_CREDENTIALS,
                    details={"field": "credentials"}
                ), 401
            except CRMAPIError as e:
                return error_response(
                    message=f"Failed to validate {crm_type} credentials. Please try again later.",
                    error_code=ErrorCodes.CRM_CONNECTION_FAILED,
                    details={"error": str(e)}
                ), 503

        # Step 3: Validate selected_fields if provided
        if request.selected_fields is not None:
            valid_fields = ["first_name", "last_name", "email", "phone"]
            invalid_fields = [f for f in request.selected_fields if f not in valid_fields]
            if invalid_fields:
                return error_response(
                    message=f"Invalid fields in selected_fields: {', '.join(invalid_fields)}",
                    error_code=ErrorCodes.INVALID_INPUT,
                    details={
                        "field": "selected_fields",
                        "invalid_fields": invalid_fields,
                        "valid_fields": valid_fields
                    }
                ), 400

        # Step 4: Prepare updated settings
        current_settings = existing["settings"]
        if isinstance(current_settings, str):
            current_settings = json.loads(current_settings)

        # Merge settings
        if request.settings is not None:
            updated_settings = {**current_settings, **request.settings}
        else:
            updated_settings = current_settings.copy()

        # Update selected_fields and lead_quality in settings
        if request.selected_fields is not None:
            updated_settings["selected_fields"] = request.selected_fields
        if request.lead_quality is not None:
            updated_settings["lead_quality"] = request.lead_quality

        # Ensure sync_frequency remains real-time
        updated_settings["sync_frequency"] = SyncFrequency.REAL_TIME.value

        settings_json = json.dumps(updated_settings)

        # Step 5: Build update query dynamically based on provided fields
        now = datetime.now(timezone.utc)
        update_parts = [
            "updated_at = $1", 
            "settings = $2::jsonb"
        ]
        params = [now, settings_json]
        param_index = 3

        # If reconnect is requested, reactivate the integration
        if request.reconnect:
            logger.info(f"Reactivating {crm_type} integration for merchant {user_id}")
            update_parts.extend([
                "is_active = TRUE",
                "sync_status = 'connected'",
                "sync_error = NULL"
            ])

        if request.credentials:
            credentials_json = json.dumps(request.credentials)
            update_parts.append(f"encrypted_credentials = encrypt_credentials(${param_index}::jsonb, ${param_index + 1})")
            params.extend([credentials_json, settings.CRM_ENCRYPTION_KEY])
            param_index += 2

        update_query = f"""
            UPDATE crm.crm_integrations
            SET {', '.join(update_parts)}
            WHERE user_id = ${param_index} AND crm_type = ${param_index + 1}
            RETURNING integration_id, user_id, crm_type, settings, is_active,
                      created_at, updated_at, last_sync_at, sync_status
        """
        params.extend([user_id, crm_type.lower()])

        result = await conn.fetchrow(update_query, *params)

        # Step 6: Format and return response
        settings_data = result["settings"]
        if isinstance(settings_data, str):
            settings_data = json.loads(settings_data)

        integration_data = {
            "integration_id": str(result["integration_id"]),
            "user_id": str(result["user_id"]),
            "crm_type": result["crm_type"],
            "is_active": result["is_active"],
            "settings": settings_data,
            "created_at": result["created_at"].isoformat(),
            "updated_at": result["updated_at"].isoformat(),
            "last_sync_at": result["last_sync_at"].isoformat() if result["last_sync_at"] else None,
            "sync_status": result["sync_status"]
        }

        logger.info(f"{crm_type} integration updated successfully for merchant {user_id}")

        return success_response(
            message=f"{crm_type.capitalize()} integration updated successfully",
            data={"integration": integration_data}
        )

    except Exception as e:
        logger.error(
            f"Unexpected error updating {crm_type} for merchant {user_id}: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred while updating {crm_type} integration"
        )


@router.get("/{crm_type}/status")
async def get_crm_status(
    crm_type: str,
    user_id: str = Depends(get_user_id),
    conn: Connection = Depends(get_conn)
):
    """
    Get the current CRM integration status for the merchant.

    Returns integration details if connected, or null if not connected.

    **Headers Required:**
    - X-User-Id: Firebase user ID
    """
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
            SELECT integration_id, user_id, crm_type, settings, is_active,
                   created_at, updated_at, last_sync_at, sync_status, sync_error
            FROM crm.crm_integrations
            WHERE user_id = $1 AND crm_type = $2
        """

        result = await conn.fetchrow(query, user_id, crm_type.lower())

        if not result:
            return success_response(
                message=f"No {crm_type} integration found",
                data={"integration": None}
            )

        settings_data = result["settings"]
        # Parse settings if it's a JSON string
        if isinstance(settings_data, str):
            settings_data = json.loads(settings_data)

        integration_data = {
            "integration_id": str(result["integration_id"]),
            "user_id": str(result["user_id"]),
            "crm_type": result["crm_type"],
            "is_active": result["is_active"],
            "settings": settings_data,
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
        logger.error(f"Error retrieving {crm_type} status for merchant {user_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve {crm_type} integration status"
        )


@router.delete("/{crm_type}/disconnect")
async def disconnect_crm(
    crm_type: str,
    user_id: str = Depends(get_user_id),
    conn: Connection = Depends(get_conn)
):
    """
    Disconnect a CRM integration for the merchant.

    This marks the integration as inactive but does not delete the record.

    **Headers Required:**
    - X-User-Id: Firebase user ID
    """
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
            UPDATE crm.crm_integrations
            SET
                is_active = FALSE,
                sync_status = 'disconnected',
                updated_at = $1
            WHERE user_id = $2 AND crm_type = $3 AND is_active = TRUE
            RETURNING integration_id
        """

        result = await conn.fetchrow(query, datetime.now(timezone.utc), user_id, crm_type.lower())

        if not result:
            return error_response(
                message=f"No active {crm_type} integration found",
                error_code=ErrorCodes.CRM_INTEGRATION_NOT_FOUND
            ), 404

        logger.info(f"{crm_type} integration disconnected for merchant {user_id}")

        return success_response(
            message=f"{crm_type.capitalize()} integration disconnected successfully",
            data={
                "integration_id": str(result["integration_id"]),
                "disconnected_at": datetime.now(timezone.utc).isoformat()
            }
        )

    except Exception as e:
        logger.error(f"Error disconnecting {crm_type} for merchant {user_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to disconnect {crm_type} integration"
        )


@router.get("/list")
async def list_integrations(
    user_id: str = Depends(get_user_id),
    conn: Connection = Depends(get_conn)
):
    """
    List all CRM integrations for the merchant.

    Returns a list of all connected CRMs with their status, including
    the last 4 characters of the primary credential for identification.

    **Headers Required:**
    - X-User-Id: Firebase user ID
    """
    try:
        query = """
            SELECT integration_id, user_id, crm_type, settings, is_active,
                   created_at, updated_at, last_sync_at, sync_status, sync_error,
                   decrypt_credentials(encrypted_credentials, $2) as credentials
            FROM crm.crm_integrations
            WHERE user_id = $1
            ORDER BY created_at DESC
        """

        results = await conn.fetch(query, user_id, settings.CRM_ENCRYPTION_KEY)

        integrations = []
        for row in results:
            settings_data = row["settings"]
            # Parse settings if it's a JSON string
            if isinstance(settings_data, str):
                settings_data = json.loads(settings_data)

            # Decrypt and mask credentials
            credentials = row["credentials"]
            if isinstance(credentials, str):
                credentials = json.loads(credentials)

            # Get last 4 characters of the primary credential field
            credential_last_four = _get_credential_last_four(credentials, row["crm_type"])

            integrations.append({
                "integration_id": str(row["integration_id"]),
                "user_id": str(row["user_id"]),
                "crm_type": row["crm_type"],
                "is_active": row["is_active"],
                "settings": settings_data,
                "credential_last_four": credential_last_four,
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
        logger.error(f"Error listing integrations for merchant {user_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to list integrations"
        )

@router.post("/sync/contact")
async def sync_contact(
    contact_data: StandardContactData,
    user_id: str = Depends(get_user_id),
    crm_types: Optional[List[str]] = None,
    conn: Connection = Depends(get_conn)
):
    """
    Sync contact data to configured CRM systems in real-time.

    Accepts a standard contact schema and automatically transforms it to match
    each CRM's requirements. Syncs to all active integrations or specific CRMs.

    **Headers Required:**
    - X-User-Id: Firebase user ID

    **Request Body:**
    ```json
    {
      "email": "customer@example.com",
      "first_name": "John",
      "last_name": "Doe",
      "phone": "+1234567890",
      "company": "Acme Corp",
      "job_title": "CEO",
      "city": "New York",
      "state": "NY",
      "country": "US",
      "custom_properties": {
        "lead_score": 85,
        "source": "website",
        "tags": ["enterprise", "hot_lead"]
      }
    }
    ```

    **Query Parameters:**
    - crm_types: Optional comma-separated list (e.g., ?crm_types=klaviyo,salesforce)

    **Response:**
    Returns sync results for each CRM including success status and any errors.
    """
    try:
        logger.info(f"Syncing contact {contact_data.email} for merchant {user_id}")

        # Build query to get active integrations
        if crm_types:
            query = """
                SELECT integration_id, crm_type,
                       decrypt_credentials(encrypted_credentials, $1) as credentials,
                       settings
                FROM crm.crm_integrations
                WHERE user_id = $2 AND is_active = TRUE AND crm_type = ANY($3)
            """
            integrations = await conn.fetch(query, settings.CRM_ENCRYPTION_KEY, user_id, crm_types)
        else:
            query = """
                SELECT integration_id, crm_type,
                       decrypt_credentials(encrypted_credentials, $1) as credentials,
                       settings
                FROM crm.crm_integrations
                WHERE user_id = $2 AND is_active = TRUE
            """
            integrations = await conn.fetch(query, settings.CRM_ENCRYPTION_KEY, user_id)

        if not integrations:
            return error_response(
                message="No active CRM integrations found",
                error_code=ErrorCodes.CRM_INTEGRATION_NOT_FOUND
            ), 404

        # Sync to each CRM
        results = {}
        contact_dict = contact_data.dict(exclude_none=True)

        for integration in integrations:
            crm_type = integration["crm_type"]
            integration_id = integration["integration_id"]
            credentials = integration["credentials"]
            crm_settings = integration["settings"]

            # Parse credentials if it's a string
            if isinstance(credentials, str):
                credentials = json.loads(credentials)

            # Parse settings if it's a string
            if isinstance(crm_settings, str):
                crm_settings = json.loads(crm_settings)

            # Verify sync_frequency is real-time (all integrations should have this)
            sync_frequency = crm_settings.get("sync_frequency", SyncFrequency.REAL_TIME.value)
            if sync_frequency != SyncFrequency.REAL_TIME.value:
                logger.warning(f"Integration {integration_id} has non-real-time sync frequency: {sync_frequency}. Syncing anyway.")

            try:
                # Use backend field mapping service
                # Validates and transforms standard schema to CRM-specific format
                transformed_data = field_mapping_service.transform_contact(
                    contact_dict.copy(),  # Don't mutate original
                    crm_type
                )

                logger.debug(f"Transformed contact for {crm_type}: {transformed_data}")

            except FieldMappingError as e:
                # Validation or transformation error
                results[crm_type] = {"success": False, "error": f"Field mapping error: {str(e)}"}
                logger.error(f"Field mapping failed for {crm_type}: {str(e)}")
                continue

            # Create sync log (pending)
            log_id = await _create_sync_log(
                conn, integration_id, user_id, crm_type,
                "create_contact", "contact", None, transformed_data
            )

            try:
                # Call CRM API
                result = await crm_manager.create_or_update_contact(
                    CRMType(crm_type),
                    credentials,
                    transformed_data
                )

                # Update sync log (success)
                await _update_sync_log(conn, log_id, "success", 200, result)

                # Update integration last_sync_at
                await conn.execute(
                    "UPDATE crm.crm_integrations SET last_sync_at = $1 WHERE integration_id = $2",
                    datetime.now(timezone.utc), integration_id
                )

                results[crm_type] = {"success": True, "data": result}
                logger.info(f"Contact synced successfully to {crm_type}")

            except (CRMAuthError, CRMAPIError) as e:
                # Update sync log (failed)
                await _update_sync_log(conn, log_id, "failed", None, None, str(e))
                results[crm_type] = {"success": False, "error": str(e)}
                logger.error(f"Failed to sync contact to {crm_type}: {str(e)}")

        return success_response(
            message="Contact sync completed",
            data={"results": results}
        )

    except Exception as e:
        logger.error(f"Error syncing contact for merchant {user_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to sync contact")


@router.get("/field-mappings/{crm_type}")
async def get_field_mappings(
    crm_type: str,
    user_id: str = Depends(get_user_id)
):
    """
    Get field mapping information for a specific CRM type.

    Returns:
    - Supported standard fields
    - Required fields
    - CRM-specific field names
    - Example contact data

    This helps clients understand what fields are available and how they map to CRMs.
    """
    try:
        # Validate CRM type
        if not field_mapping_service.get_supported_crms():
            supported = field_mapping_service.get_supported_crms()
        else:
            supported = []

        crm_lower = crm_type.lower()

        if crm_lower not in field_mapping_service.get_supported_crms():
            return error_response(
                message=f"CRM type '{crm_type}' is not supported",
                error_code=ErrorCodes.CRM_INVALID_TYPE,
                details={
                    "supported_crms": field_mapping_service.get_supported_crms()
                }
            ), 400

        # Get mapping information
        field_mapping = field_mapping_service.get_field_mapping(crm_lower)
        supported_fields = field_mapping_service.get_supported_fields(crm_lower)
        required_fields = field_mapping_service.get_required_fields(crm_lower)

        return success_response(
            message=f"Field mapping information for {crm_type}",
            data={
                "crm_type": crm_lower,
                "supported_fields": supported_fields,
                "required_fields": required_fields,
                "field_mapping": field_mapping,
                "example_standard_contact": {
                    "email": "john.doe@example.com",
                    "first_name": "John",
                    "last_name": "Doe",
                    "phone": "+1234567890",
                    "company": "Acme Corp",
                    "job_title": "CEO",
                    "custom_properties": {
                        "lead_score": 85,
                        "source": "website"
                    }
                }
            }
        )

    except Exception as e:
        logger.error(f"Error getting field mappings for {crm_type}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get field mapping information")


@router.get("/field-mappings")
async def list_all_field_mappings(
    user_id: str = Depends(get_user_id)
):
    """
    List all supported CRM types and their field mapping capabilities.

    Returns overview of all supported CRMs with their required fields.
    """
    try:
        supported_crms = field_mapping_service.get_supported_crms()

        crm_info = []
        for crm_type in supported_crms:
            crm_info.append({
                "crm_type": crm_type,
                "required_fields": field_mapping_service.get_required_fields(crm_type),
                "supported_fields_count": len(field_mapping_service.get_supported_fields(crm_type))
            })

        return success_response(
            message="All supported CRM field mappings",
            data={
                "supported_crms": supported_crms,
                "total_crms": len(supported_crms),
                "crm_details": crm_info,
                "standard_schema_fields": [
                    "email", "first_name", "last_name", "phone", "company",
                    "job_title", "department", "street_address", "city", "state",
                    "postal_code", "country", "website", "timezone", "language",
                    "custom_properties"
                ]
            }
        )

    except Exception as e:
        logger.error(f"Error listing field mappings: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list field mappings")


@router.post("/sync/event")
async def sync_event(
    request: SyncEventRequest,
    contact_email: str = Query(..., description="Email of the contact"),
    user_id: str = Depends(get_user_id),
    crm_types: Optional[List[str]] = None,
    conn: Connection = Depends(get_conn)
):
    """
    Send event/activity data to configured CRM systems in real-time.

    **Note:** This endpoint performs real-time event sync. All integrations are configured with real-time sync frequency.

    **Headers Required:**
    - X-User-Id: Firebase user ID

    **Request Body:**
    ```json
    {
      "event_name": "order_created",
      "properties": {
        "order_id": "ORD-123",
        "total_amount": 99.99,
        "currency": "USD"
      },
      "timestamp": "2025-11-26T10:00:00Z"
    }
    ```

    **Query Parameters:**
    - contact_email: Email of the contact (required)
    - crm_types: Comma-separated list (optional)
    """
    try:
        # Convert request to EventData
        event_data = EventData(**request.dict())

        logger.info(f"Syncing event {event_data.event_name} for {contact_email}, merchant {user_id}")

        # Get active integrations
        if crm_types:
            query = """
                SELECT integration_id, crm_type,
                       decrypt_credentials(encrypted_credentials, $1) as credentials,
                       settings
                FROM crm.crm_integrations
                WHERE user_id = $2 AND is_active = TRUE AND crm_type = ANY($3)
            """
            integrations = await conn.fetch(query, settings.CRM_ENCRYPTION_KEY, user_id, crm_types)
        else:
            query = """
                SELECT integration_id, crm_type,
                       decrypt_credentials(encrypted_credentials, $1) as credentials,
                       settings
                FROM crm.crm_integrations
                WHERE user_id = $2 AND is_active = TRUE
            """
            integrations = await conn.fetch(query, settings.CRM_ENCRYPTION_KEY, user_id)

        if not integrations:
            return error_response(
                message="No active CRM integrations found",
                error_code=ErrorCodes.CRM_INTEGRATION_NOT_FOUND
            ), 404

        # Check if event is enabled in settings
        results = {}
        for integration in integrations:
            crm_type = integration["crm_type"]
            integration_id = integration["integration_id"]
            credentials = integration["credentials"]
            crm_settings = integration["settings"]

            # Parse credentials if it's a string
            if isinstance(credentials, str):
                credentials = json.loads(credentials)

            # Parse settings if it's a string
            if isinstance(crm_settings, str):
                crm_settings = json.loads(crm_settings)

            # Verify sync_frequency is real-time (all integrations should have this)
            sync_frequency = crm_settings.get("sync_frequency", SyncFrequency.REAL_TIME.value)
            if sync_frequency != SyncFrequency.REAL_TIME.value:
                logger.warning(f"Integration {integration_id} has non-real-time sync frequency: {sync_frequency}. Syncing anyway.")

            # Check if this event is enabled
            enabled_events = crm_settings.get("enabled_events", [])
            if enabled_events and event_data.event_name not in enabled_events:
                logger.info(f"Event {event_data.event_name} not enabled for {crm_type}, skipping")
                continue

            # Create sync log
            log_id = await _create_sync_log(
                conn, integration_id, user_id, crm_type,
                "send_event", "event", None, event_data.dict()
            )

            try:
                # Call CRM API
                result = await crm_manager.send_event(
                    CRMType(crm_type),
                    credentials,
                    {"email": contact_email},
                    event_data.dict()
                )

                # Update sync log (success)
                await _update_sync_log(conn, log_id, "success", 200, result)

                results[crm_type] = {"success": True, "data": result}
                logger.info(f"Event synced successfully to {crm_type}")

            except (CRMAuthError, CRMAPIError) as e:
                # Update sync log (failed)
                await _update_sync_log(conn, log_id, "failed", None, None, str(e))
                results[crm_type] = {"success": False, "error": str(e)}
                logger.error(f"Failed to sync event to {crm_type}: {str(e)}")

        return success_response(
            message="Event sync completed",
            data={"results": results}
        )

    except Exception as e:
        logger.error(f"Error syncing event for merchant {user_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to sync event")


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

async def _create_sync_log(
    conn: Connection,
    integration_id: UUID,
    user_id: str,
    crm_type: str,
    operation_type: str,
    entity_type: str,
    entity_id: Optional[str],
    request_payload: Dict[str, Any]
) -> UUID:
    """Create a sync log entry."""
    query = """
        INSERT INTO crm.crm_sync_logs (
            integration_id, user_id, crm_type,
            operation_type, entity_type, entity_id,
            request_payload, status, source, triggered_by
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, 'pending', 'api', $8)
        RETURNING log_id
    """
    result = await conn.fetchrow(
        query,
        integration_id, user_id, crm_type,
        operation_type, entity_type, entity_id,
        json.dumps(request_payload), str(user_id)
    )
    return result["log_id"]


async def _update_sync_log(
    conn: Connection,
    log_id: UUID,
    status: str,
    status_code: Optional[int],
    response_payload: Optional[Dict[str, Any]],
    error_message: Optional[str] = None
):
    """Update sync log with result."""
    query = """
        UPDATE crm.crm_sync_logs
        SET
            status = $1,
            status_code = $2,
            response_payload = $3,
            error_message = $4,
            request_completed_at = NOW()
        WHERE log_id = $5
    """
    await conn.execute(
        query,
        status,
        status_code,
        json.dumps(response_payload) if response_payload else None,
        error_message,
        log_id
    )


def _get_credential_last_four(credentials: Dict[str, Any], crm_type: str) -> str:
    """
    Extract the last 4 characters of the primary credential field for a CRM type.

    Returns a masked string or the last 4 characters for identification purposes.

    Args:
        credentials: Decrypted credentials dictionary
        crm_type: Type of CRM (klaviyo, salesforce, creatio, etc.)

    Returns:
        Last 4 characters of the primary credential field, or "****" if not found
    """
    try:
        # Map CRM types to their primary credential field
        credential_field_map = {
            "klaviyo": "api_key",
            "salesforce": "access_token",
            "creatio": "username",
            "hubspot": "api_key",
        }

        # Get the primary credential field for this CRM type
        primary_field = credential_field_map.get(crm_type.lower())

        if not primary_field:
            logger.warning(f"Unknown CRM type for credential masking: {crm_type}")
            return "****"

        # Get the credential value
        credential_value = credentials.get(primary_field)

        if not credential_value or not isinstance(credential_value, str):
            logger.warning(f"No valid credential found for {crm_type} field {primary_field}")
            return "****"

        # Return last 4 characters
        if len(credential_value) >= 4:
            return credential_value[-4:]
        else:
            # If credential is shorter than 4 chars, return masked version
            return "*" * len(credential_value)

    except Exception as e:
        logger.error(f"Error extracting credential last four for {crm_type}: {str(e)}")
        return "****"


