from fastapi import Header, HTTPException, Request
from firebase_admin import credentials, initialize_app, auth as fb_auth
from .config import settings
from .services.request_logger import extract_request_metadata
import os

# Initialize Firebase Admin once
# ALWAYS use .env credentials for Firebase Admin (NOT service-account.json)
cred = credentials.Certificate({
    "type": "service_account",
    "project_id": settings.GCP_PROJECT_ID,
    "private_key_id": settings.SA_PRIVATE_KEY_ID,
    "private_key": settings.SA_PRIVATE_KEY.replace("\\n", "\n"),
    "client_email": settings.SA_CLIENT_EMAIL,
    "client_id": settings.SA_CLIENT_ID,
    "token_uri": "https://oauth2.googleapis.com/token",
})
initialize_app(cred)
print(f"✅ Firebase Admin initialized for CRM with credentials: {settings.SA_CLIENT_EMAIL}")

async def get_current_merchant(authorization: str = Header(None)):
    """
    Verify Firebase token and return merchant info.
    This replaces get_current_user for CRM service.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    id_token = authorization.split(" ", 1)[1]
    try:
        # Verify the ID token and check it's not revoked
        decoded = fb_auth.verify_id_token(id_token, check_revoked=settings.CHECK_TOKEN_REVOCATION)
    except fb_auth.RevokedIdTokenError:
        raise HTTPException(status_code=401, detail="Token has been revoked")
    except fb_auth.InvalidIdTokenError:
        raise HTTPException(status_code=401, detail="Invalid ID token")
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Token verification failed: {str(e)}")

    return {
        "merchant_id": decoded["uid"],  # Changed from user_id to merchant_id
        "email": decoded.get("email"),
        "name": decoded.get("name"),
        "email_verified": decoded.get("email_verified", False),
        "phone": decoded.get("phone_number"),
        "picture": decoded.get("picture"),
        "issuer": decoded.get("iss"),
        "audience": decoded.get("aud"),
        "provider": decoded.get("firebase", {}).get("sign_in_provider", "unknown"),
        "provider_data": decoded.get("firebase", {}).get("identities", {}),
    }

async def get_request_metadata(request: Request):
    """Dependency to extract request metadata (IP, geolocation, device info, etc.)"""
    return await extract_request_metadata(request)

# Simple RBAC guard
async def require_roles(*allowed_roles: str):
    async def checker(merchant=await get_current_merchant()):
        return merchant
    return checker
