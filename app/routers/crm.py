"""CRM Integration API - Generic CRM Integration Endpoints"""

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from asyncpg import Connection
from datetime import datetime, timezone
from uuid import UUID
from typing import List, Optional, Dict, Any
import logging
import json

from ..deps import get_merchant_id
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
    ContactData,
    EventData,
    SyncEventRequest,
    SyncFrequency
)
from ..config import settings
from ..response_models import success_response, error_response, ErrorCodes

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/crm", tags=["crm"])


@router.post("/validate")
async def validate_crm_credentials(
    request: CRMValidateRequest,
    merchant_id: UUID = Depends(get_merchant_id)
):
    """
    Validate CRM credentials without saving them.

    This endpoint allows testing CRM credentials before connecting.
    Works with all supported CRM types (Klaviyo, Salesforce, Creatio, etc.)

    **Headers Required:**
    - X-Merchant-Id: UUID of the merchant

    **Request Body:**
    ```json
    {
      "crm_type": "klaviyo",
      "credentials": {"api_key": "pk_..."}
    }
    ```
    """
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
    merchant_id: UUID = Depends(get_merchant_id),
    conn: Connection = Depends(get_conn)
):
    """
    Connect a CRM integration for the merchant.

    This endpoint:
    1. Validates the CRM credentials
    2. Encrypts and saves the credentials to the database
    3. Stores optional settings (sync_frequency, field_mapping, etc.)
    4. Returns the integration details

    **Headers Required:**
    - X-Merchant-Id: UUID of the merchant

    **Request Body:**
    ```json
    {
      "crm_type": "klaviyo",
      "credentials": {"api_key": "pk_..."},
      "settings": {
        "field_mapping": {"customer_name": "firstName"},
        "enabled_events": ["order_created"]
      }
    }
    ```

    **Note:** sync_frequency is automatically set to "real-time". Daily and monthly sync options are placeholders for future implementation.
    """
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

        # Automatically set sync_frequency to real-time
        merged_settings = request.settings.copy() if request.settings else {}
        merged_settings["sync_frequency"] = SyncFrequency.REAL_TIME.value
        settings_json = json.dumps(merged_settings)

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
    merchant_id: UUID = Depends(get_merchant_id),
    conn: Connection = Depends(get_conn)
):
    """
    Get the current CRM integration status for the merchant.

    Returns integration details if connected, or null if not connected.

    **Headers Required:**
    - X-Merchant-Id: UUID of the merchant
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
    merchant_id: UUID = Depends(get_merchant_id),
    conn: Connection = Depends(get_conn)
):
    """
    Disconnect a CRM integration for the merchant.

    This marks the integration as inactive but does not delete the record.

    **Headers Required:**
    - X-Merchant-Id: UUID of the merchant
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
    merchant_id: UUID = Depends(get_merchant_id),
    conn: Connection = Depends(get_conn)
):
    """
    List all CRM integrations for the merchant.

    Returns a list of all connected CRMs with their status.

    **Headers Required:**
    - X-Merchant-Id: UUID of the merchant
    """
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

@router.post("/sync/contact")
async def sync_contact(
    contact_data: ContactData,
    merchant_id: UUID = Depends(get_merchant_id),
    crm_types: Optional[List[str]] = None,
    conn: Connection = Depends(get_conn)
):
    """
    Sync contact data to configured CRM systems in real-time.

    Sends the contact to all active CRMs (or specific CRMs if crm_types provided).
    Applies field mapping from integration settings.

    **Note:** This endpoint performs real-time sync. All integrations are configured with real-time sync frequency.

    **Headers Required:**
    - X-Merchant-Id: UUID of the merchant

    **Request Body:**
    ```json
    {
      "email": "customer@example.com",
      "first_name": "John",
      "last_name": "Doe",
      "phone": "+1234567890",
      "company": "Acme Corp",
      "properties": {
        "source": "checkout",
        "order_count": 5
      }
    }
    ```

    **Query Parameters:**
    - crm_types: Comma-separated list (e.g., ?crm_types=klaviyo,salesforce)
    """
    try:
        logger.info(f"Syncing contact {contact_data.email} for merchant {merchant_id}")

        # Build query to get active integrations
        if crm_types:
            query = """
                SELECT integration_id, crm_type,
                       decrypt_credentials(encrypted_credentials, $1) as credentials,
                       settings
                FROM crm_integrations
                WHERE merchant_id = $2 AND is_active = TRUE AND crm_type = ANY($3)
            """
            integrations = await conn.fetch(query, settings.CRM_ENCRYPTION_KEY, merchant_id, crm_types)
        else:
            query = """
                SELECT integration_id, crm_type,
                       decrypt_credentials(encrypted_credentials, $1) as credentials,
                       settings
                FROM crm_integrations
                WHERE merchant_id = $2 AND is_active = TRUE
            """
            integrations = await conn.fetch(query, settings.CRM_ENCRYPTION_KEY, merchant_id)

        if not integrations:
            return error_response(
                message="No active CRM integrations found",
                error_code=ErrorCodes.CRM_INTEGRATION_NOT_FOUND
            ), 404

        # Sync to each CRM
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

            # Prepare contact data for CRM
            contact_dict = contact_data.dict()

            # Apply field mapping if configured
            mapped_data = _apply_field_mapping(contact_dict, crm_settings.get("field_mapping", {}))

            # Transform data to match CRM-specific format
            transformed_data = _transform_contact_data(mapped_data, crm_type)

            # Create sync log (pending)
            log_id = await _create_sync_log(
                conn, integration_id, merchant_id, crm_type,
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
                    "UPDATE crm_integrations SET last_sync_at = $1 WHERE integration_id = $2",
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
        logger.error(f"Error syncing contact for merchant {merchant_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to sync contact")


@router.post("/sync/event")
async def sync_event(
    request: SyncEventRequest,
    contact_email: str = Query(..., description="Email of the contact"),
    merchant_id: UUID = Depends(get_merchant_id),
    crm_types: Optional[List[str]] = None,
    conn: Connection = Depends(get_conn)
):
    """
    Send event/activity data to configured CRM systems in real-time.

    **Note:** This endpoint performs real-time event sync. All integrations are configured with real-time sync frequency.

    **Headers Required:**
    - X-Merchant-Id: UUID of the merchant

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

        logger.info(f"Syncing event {event_data.event_name} for {contact_email}, merchant {merchant_id}")

        # Get active integrations
        if crm_types:
            query = """
                SELECT integration_id, crm_type,
                       decrypt_credentials(encrypted_credentials, $1) as credentials,
                       settings
                FROM crm_integrations
                WHERE merchant_id = $2 AND is_active = TRUE AND crm_type = ANY($3)
            """
            integrations = await conn.fetch(query, settings.CRM_ENCRYPTION_KEY, merchant_id, crm_types)
        else:
            query = """
                SELECT integration_id, crm_type,
                       decrypt_credentials(encrypted_credentials, $1) as credentials,
                       settings
                FROM crm_integrations
                WHERE merchant_id = $2 AND is_active = TRUE
            """
            integrations = await conn.fetch(query, settings.CRM_ENCRYPTION_KEY, merchant_id)

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
                conn, integration_id, merchant_id, crm_type,
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
        logger.error(f"Error syncing event for merchant {merchant_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to sync event")


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _apply_field_mapping(data: Dict[str, Any], field_mapping: Dict[str, str]) -> Dict[str, Any]:
    """
    Apply field mapping from integration settings.

    Args:
        data: Original contact data
        field_mapping: Mapping dict (e.g., {"customer_name": "firstName"})

    Returns:
        Mapped data dict
    """
    if not field_mapping:
        return data

    mapped = data.copy()
    for source_field, target_field in field_mapping.items():
        if source_field in mapped:
            mapped[target_field] = mapped.pop(source_field)

    return mapped


def _transform_contact_data(data: Dict[str, Any], crm_type: str) -> Dict[str, Any]:
    """
    Transform contact data to match CRM-specific API format.

    Args:
        data: Mapped contact data
        crm_type: Type of CRM (klaviyo, salesforce, etc.)

    Returns:
        Transformed data dict matching CRM API requirements
    """
    if crm_type == "klaviyo":
        # Klaviyo expects: {"attributes": {...}, "properties": {...}}
        properties = data.pop("properties", None)

        # Build attributes dict with Klaviyo field names
        attributes = {}

        # Map standard fields to Klaviyo attribute names
        field_mappings = {
            "email": "email",
            "first_name": "first_name",
            "last_name": "last_name",
            "phone": "phone_number",  # Klaviyo uses phone_number
            "company": "organization"  # Klaviyo uses organization
        }

        for source_field, klaviyo_field in field_mappings.items():
            if source_field in data and data[source_field]:
                attributes[klaviyo_field] = data[source_field]

        # Add any remaining fields to attributes
        for key, value in data.items():
            if key not in field_mappings and value is not None:
                attributes[key] = value

        result = {"attributes": attributes}
        if properties:
            result["properties"] = properties

        return result

    # For other CRM types, return data as-is for now
    return data


async def _create_sync_log(
    conn: Connection,
    integration_id: UUID,
    merchant_id: UUID,
    crm_type: str,
    operation_type: str,
    entity_type: str,
    entity_id: Optional[str],
    request_payload: Dict[str, Any]
) -> UUID:
    """Create a sync log entry."""
    query = """
        INSERT INTO crm_sync_logs (
            integration_id, merchant_id, crm_type,
            operation_type, entity_type, entity_id,
            request_payload, status, source, triggered_by
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, 'pending', 'api', $8)
        RETURNING log_id
    """
    result = await conn.fetchrow(
        query,
        integration_id, merchant_id, crm_type,
        operation_type, entity_type, entity_id,
        json.dumps(request_payload), str(merchant_id)
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
        UPDATE crm_sync_logs
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
