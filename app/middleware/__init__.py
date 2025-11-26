"""
Middleware package for CRM microservice
"""
from .request_logger import (
    get_client_ip,
    get_geo_location,
    parse_device_info,
    extract_request_metadata,
    log_login_attempt,
    log_audit_event,
    get_merchant_login_history,
    get_suspicious_logins
)

__all__ = [
    "get_client_ip",
    "get_geo_location",
    "parse_device_info",
    "extract_request_metadata",
    "log_login_attempt",
    "log_audit_event",
    "get_merchant_login_history",
    "get_suspicious_logins"
]
