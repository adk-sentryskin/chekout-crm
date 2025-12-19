"""
Service for logging requests, tracking merchant activity, and extracting metadata
"""
from asyncpg import Connection
from fastapi import Request
from user_agents import parse as parse_user_agent
import httpx
import logging
from typing import Optional, Dict, Any
import json

logger = logging.getLogger(__name__)


def get_client_ip(request: Request) -> str:
    """Extract the real client IP address from request"""
    # Check for proxy headers first
    x_forwarded_for = request.headers.get("x-forwarded-for")
    if x_forwarded_for:
        # X-Forwarded-For can contain multiple IPs, take the first one
        return x_forwarded_for.split(",")[0].strip()

    x_real_ip = request.headers.get("x-real-ip")
    if x_real_ip:
        return x_real_ip.strip()

    # Fallback to direct client
    if request.client:
        return request.client.host

    return "unknown"


async def get_geo_location(ip_address: str) -> Dict[str, Optional[str]]:
    """
    Get geographical location from IP address using a free geolocation service.
    Returns country, city, region info.
    """
    # Skip geolocation for local/private IPs
    if ip_address in ["unknown", "127.0.0.1", "localhost"] or ip_address.startswith("192.168.") or ip_address.startswith("10."):
        return {
            "country_code": None,
            "country_name": None,
            "city": None,
            "region": None
        }

    try:
        # Using ipapi.co (free tier: 1000 requests/day, no API key needed)
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(f"https://ipapi.co/{ip_address}/json/")

            if response.status_code == 200:
                data = response.json()
                return {
                    "country_code": data.get("country_code"),
                    "country_name": data.get("country_name"),
                    "city": data.get("city"),
                    "region": data.get("region")
                }
    except Exception as e:
        logger.warning(f"Failed to get geolocation for IP {ip_address}: {e}")

    return {
        "country_code": None,
        "country_name": None,
        "city": None,
        "region": None
    }


def parse_device_info(user_agent_string: str) -> Dict[str, Any]:
    """
    Parse user agent string to extract device and browser information
    """
    if not user_agent_string:
        return {
            "browser_name": None,
            "browser_version": None,
            "os_name": None,
            "os_version": None,
            "device_type": None,
            "device_brand": None,
            "device_model": None,
            "is_mobile": False,
            "is_tablet": False,
            "is_desktop": False,
            "is_bot": False
        }

    ua = parse_user_agent(user_agent_string)

    # Determine device type
    device_type = "desktop"
    if ua.is_mobile:
        device_type = "mobile"
    elif ua.is_tablet:
        device_type = "tablet"
    elif ua.is_bot:
        device_type = "bot"

    return {
        "browser_name": ua.browser.family,
        "browser_version": ua.browser.version_string,
        "os_name": ua.os.family,
        "os_version": ua.os.version_string,
        "device_type": device_type,
        "device_brand": ua.device.brand,
        "device_model": ua.device.model,
        "is_mobile": ua.is_mobile,
        "is_tablet": ua.is_tablet,
        "is_desktop": not (ua.is_mobile or ua.is_tablet or ua.is_bot),
        "is_bot": ua.is_bot
    }


async def extract_request_metadata(request: Request) -> Dict[str, Any]:
    """
    Extract all metadata from the request including IP, geolocation, device info, etc.
    """
    ip_address = get_client_ip(request)
    user_agent = request.headers.get("user-agent", "")

    # Get geolocation
    geo = await get_geo_location(ip_address)

    # Parse device info
    device_info = parse_device_info(user_agent)

    return {
        "ip_address": ip_address,
        "user_agent": user_agent,
        "referer": request.headers.get("referer"),
        "origin": request.headers.get("origin"),
        "endpoint": str(request.url.path),
        "method": request.method,
        **geo,
        **device_info
    }


async def log_login_attempt(
    conn: Connection,
    user_id: Optional[str],
    email: Optional[str],
    auth_provider: Optional[str],
    success: bool,
    request_metadata: Dict[str, Any],
    failure_reason: Optional[str] = None
):
    """
    Log a login attempt (success or failure) to the database
    Using user_id for CRM service
    """
    try:
        await conn.execute("""
            INSERT INTO login_logs (
                user_id, email, auth_provider, success, failure_reason,
                ip_address, country_code, country_name, city, region,
                user_agent, browser_name, browser_version, os_name, os_version,
                device_type, device_brand, device_model,
                is_mobile, is_tablet, is_desktop, is_bot,
                referer, origin, endpoint, method
            ) VALUES (
                $1, $2, $3, $4, $5,
                $6, $7, $8, $9, $10,
                $11, $12, $13, $14, $15,
                $16, $17, $18,
                $19, $20, $21, $22,
                $23, $24, $25, $26
            )
        """,
            user_id, email, auth_provider, success, failure_reason,
            request_metadata.get("ip_address"),
            request_metadata.get("country_code"),
            request_metadata.get("country_name"),
            request_metadata.get("city"),
            request_metadata.get("region"),
            request_metadata.get("user_agent"),
            request_metadata.get("browser_name"),
            request_metadata.get("browser_version"),
            request_metadata.get("os_name"),
            request_metadata.get("os_version"),
            request_metadata.get("device_type"),
            request_metadata.get("device_brand"),
            request_metadata.get("device_model"),
            request_metadata.get("is_mobile", False),
            request_metadata.get("is_tablet", False),
            request_metadata.get("is_desktop", False),
            request_metadata.get("is_bot", False),
            request_metadata.get("referer"),
            request_metadata.get("origin"),
            request_metadata.get("endpoint"),
            request_metadata.get("method")
        )

        logger.info(
            f"Login attempt logged: merchant={user_id or email}, "
            f"success={success}, provider={auth_provider}, "
            f"ip={request_metadata.get('ip_address')}, "
            f"country={request_metadata.get('country_code')}, "
            f"device={request_metadata.get('device_type')}"
        )
    except Exception as e:
        logger.error(f"Failed to log login attempt: {e}")


async def log_audit_event(
    conn: Connection,
    action: str,
    user_id: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    request_metadata: Optional[Dict[str, Any]] = None
):
    """
    Log an audit event (any important action in the system)
    Using user_id for CRM service
    """
    try:
        details_json = json.dumps(details) if details else None

        await conn.execute("""
            INSERT INTO audit_logs (
                user_id, action, resource_type, resource_id, details,
                ip_address, user_agent, referer, origin, endpoint, method
            ) VALUES (
                $1, $2, $3, $4, $5,
                $6, $7, $8, $9, $10, $11
            )
        """,
            user_id, action, resource_type, resource_id, details_json,
            request_metadata.get("ip_address") if request_metadata else None,
            request_metadata.get("user_agent") if request_metadata else None,
            request_metadata.get("referer") if request_metadata else None,
            request_metadata.get("origin") if request_metadata else None,
            request_metadata.get("endpoint") if request_metadata else None,
            request_metadata.get("method") if request_metadata else None
        )

        logger.info(
            f"Audit event logged: action={action}, merchant={user_id}, "
            f"resource={resource_type}:{resource_id}"
        )
    except Exception as e:
        logger.error(f"Failed to log audit event: {e}")


async def get_merchant_login_history(
    conn: Connection,
    user_id: str,
    limit: int = 50
) -> list:
    """
    Get login history for a specific merchant
    """
    rows = await conn.fetch("""
        SELECT
            log_id, email, auth_provider, success, failure_reason,
            ip_address, country_code, country_name, city,
            browser_name, os_name, device_type,
            is_mobile, is_tablet, is_desktop,
            created_at
        FROM login_logs
        WHERE user_id = $1
        ORDER BY created_at DESC
        LIMIT $2
    """, user_id, limit)

    return [dict(row) for row in rows]


async def get_suspicious_logins(
    conn: Connection,
    user_id: str,
    days: int = 30
) -> list:
    """
    Get potentially suspicious login attempts (e.g., from new locations/devices)
    """
    rows = await conn.fetch("""
        SELECT
            log_id, ip_address, country_code, city,
            browser_name, os_name, device_type,
            success, created_at
        FROM login_logs
        WHERE user_id = $1
          AND created_at > NOW() - INTERVAL '%s days'
        ORDER BY created_at DESC
    """ % days, user_id)

    return [dict(row) for row in rows]
