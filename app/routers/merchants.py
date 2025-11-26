"""Merchant authentication and profile management endpoints"""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr
from asyncpg import Connection
from ..deps import get_current_merchant, get_request_metadata
from ..db import get_conn
from ..services.request_logger import log_login_attempt, log_audit_event
from ..response_models import success_response, error_response, ErrorCodes
from ..exceptions import NotFoundError
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


class MerchantBootstrapRequest(BaseModel):
    """Request for bootstrapping merchant on first login"""
    name: str | None = None
    company_name: str | None = None
    phone: str | None = None


@router.post("/bootstrap")
async def bootstrap_merchant(
    req: MerchantBootstrapRequest,
    request: Request,
    merchant=Depends(get_current_merchant),
    conn: Connection = Depends(get_conn),
    request_metadata: dict = Depends(get_request_metadata)
):
    """
    Bootstrap merchant on first login. Creates/updates merchant in database.
    Also logs the login attempt with full request metadata.
    """
    try:
        merchant_id = merchant["merchant_id"]
        email = merchant.get("email")

        # Check if merchant already exists
        check_query = "SELECT merchant_id FROM merchants WHERE merchant_id = $1"
        existing = await conn.fetchrow(check_query, merchant_id)

        if existing:
            # Update existing merchant
            update_query = """
                UPDATE merchants
                SET
                    email = $1,
                    name = COALESCE($2, name),
                    company_name = COALESCE($3, company_name),
                    phone = COALESCE($4, phone),
                    email_verified = $5,
                    last_login_at = NOW(),
                    updated_at = NOW()
                WHERE merchant_id = $6
                RETURNING merchant_id, email, name, company_name, phone, email_verified, status, plan_id, created_at, updated_at
            """
            result = await conn.fetchrow(
                update_query,
                email,
                req.name,
                req.company_name,
                req.phone,
                merchant.get("email_verified", False),
                merchant_id
            )
        else:
            # Create new merchant
            insert_query = """
                INSERT INTO merchants (
                    merchant_id, email, name, company_name, phone, email_verified,
                    status, plan_id, created_at, updated_at, last_login_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, 'active', 'free', NOW(), NOW(), NOW())
                RETURNING merchant_id, email, name, company_name, phone, email_verified, status, plan_id, created_at, updated_at
            """
            result = await conn.fetchrow(
                insert_query,
                merchant_id,
                email,
                req.name,
                req.company_name,
                req.phone,
                merchant.get("email_verified", False)
            )

        # Log successful login
        await log_login_attempt(
            conn=conn,
            merchant_id=merchant_id,
            email=email,
            auth_provider=merchant.get("provider"),
            success=True,
            request_metadata=request_metadata
        )

        # Log audit event
        await log_audit_event(
            conn=conn,
            action="login",
            merchant_id=merchant_id,
            resource_type="merchant",
            resource_id=merchant_id,
            details={
                "provider": merchant.get("provider"),
                "email_verified": merchant.get("email_verified")
            },
            request_metadata=request_metadata
        )

        merchant_data = {
            "merchant_id": str(result["merchant_id"]),
            "email": result["email"],
            "name": result["name"],
            "company_name": result["company_name"],
            "phone": result["phone"],
            "email_verified": result["email_verified"],
            "status": result["status"],
            "plan_id": result["plan_id"],
            "created_at": result["created_at"].isoformat(),
            "updated_at": result["updated_at"].isoformat()
        }

        return success_response(
            message="Merchant bootstrapped successfully",
            data={"merchant": merchant_data}
        )

    except Exception as e:
        logger.error(f"Error bootstrapping merchant: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to bootstrap merchant")


@router.get("/me")
async def get_current_merchant_profile(
    merchant=Depends(get_current_merchant),
    conn: Connection = Depends(get_conn)
):
    """
    Get the current merchant's profile information.
    """
    try:
        merchant_id = merchant["merchant_id"]

        query = """
            SELECT merchant_id, email, name, company_name, phone, email_verified,
                   status, plan_id, trial_ends_at, created_at, updated_at, last_login_at
            FROM merchants
            WHERE merchant_id = $1
        """

        result = await conn.fetchrow(query, merchant_id)

        if not result:
            raise NotFoundError("Merchant not found", error_code=ErrorCodes.MERCHANT_NOT_FOUND)

        merchant_data = {
            "merchant_id": str(result["merchant_id"]),
            "email": result["email"],
            "name": result["name"],
            "company_name": result["company_name"],
            "phone": result["phone"],
            "email_verified": result["email_verified"],
            "status": result["status"],
            "plan_id": result["plan_id"],
            "trial_ends_at": result["trial_ends_at"].isoformat() if result["trial_ends_at"] else None,
            "created_at": result["created_at"].isoformat(),
            "updated_at": result["updated_at"].isoformat(),
            "last_login_at": result["last_login_at"].isoformat() if result["last_login_at"] else None
        }

        return success_response(
            message="Merchant profile retrieved successfully",
            data={"merchant": merchant_data}
        )

    except NotFoundError as e:
        return error_response(
            message=str(e),
            error_code=e.error_code
        ), 404
    except Exception as e:
        logger.error(f"Error retrieving merchant profile: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve merchant profile")


@router.patch("/profile")
async def update_merchant_profile(
    updates: MerchantBootstrapRequest,
    merchant=Depends(get_current_merchant),
    conn: Connection = Depends(get_conn)
):
    """
    Update the current merchant's profile information.
    """
    try:
        merchant_id = merchant["merchant_id"]

        # Build dynamic update query
        update_fields = []
        params = []
        param_idx = 1

        if updates.name is not None:
            update_fields.append(f"name = ${param_idx}")
            params.append(updates.name)
            param_idx += 1

        if updates.company_name is not None:
            update_fields.append(f"company_name = ${param_idx}")
            params.append(updates.company_name)
            param_idx += 1

        if updates.phone is not None:
            update_fields.append(f"phone = ${param_idx}")
            params.append(updates.phone)
            param_idx += 1

        if not update_fields:
            return error_response(
                message="No fields to update",
                error_code=ErrorCodes.INVALID_INPUT
            ), 400

        # Add updated_at
        update_fields.append(f"updated_at = NOW()")

        # Add merchant_id parameter
        params.append(merchant_id)

        query = f"""
            UPDATE merchants
            SET {', '.join(update_fields)}
            WHERE merchant_id = ${param_idx}
            RETURNING merchant_id, email, name, company_name, phone, email_verified, status, plan_id, created_at, updated_at
        """

        result = await conn.fetchrow(query, *params)

        if not result:
            raise NotFoundError("Merchant not found", error_code=ErrorCodes.MERCHANT_NOT_FOUND)

        merchant_data = {
            "merchant_id": str(result["merchant_id"]),
            "email": result["email"],
            "name": result["name"],
            "company_name": result["company_name"],
            "phone": result["phone"],
            "email_verified": result["email_verified"],
            "status": result["status"],
            "plan_id": result["plan_id"],
            "created_at": result["created_at"].isoformat(),
            "updated_at": result["updated_at"].isoformat()
        }

        # Log audit event
        await log_audit_event(
            conn=conn,
            action="profile_update",
            merchant_id=merchant_id,
            resource_type="merchant",
            resource_id=merchant_id,
            details={"updated_fields": list(updates.model_dump(exclude_unset=True).keys())}
        )

        return success_response(
            message="Merchant profile updated successfully",
            data={"merchant": merchant_data}
        )

    except NotFoundError as e:
        return error_response(
            message=str(e),
            error_code=e.error_code
        ), 404
    except Exception as e:
        logger.error(f"Error updating merchant profile: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update merchant profile")
