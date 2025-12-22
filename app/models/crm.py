"""Pydantic models for CRM integration operations"""
from pydantic import BaseModel, Field, UUID4
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum


class SyncFrequency(str, Enum):
    """Enum for sync frequency options"""
    REAL_TIME = "real-time"
    DAILY = "daily"  # Placeholder for future implementation
    MONTHLY = "monthly"  # Placeholder for future implementation


class CRMCredentials(BaseModel):
    """Base model for CRM credentials (varies by CRM type)"""
    # Klaviyo
    api_key: Optional[str] = None

    # Salesforce
    access_token: Optional[str] = None
    instance_url: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    security_token: Optional[str] = None

    # Creatio
    # (uses instance_url, username, password from above)


class CRMValidateRequest(BaseModel):
    """Request model for validating CRM credentials"""
    crm_type: str = Field(..., description="Type of CRM (klaviyo, salesforce, creatio)")
    credentials: Dict[str, Any] = Field(..., description="CRM-specific credentials")


class CRMConnectRequest(BaseModel):
    """Request model for connecting a CRM integration"""
    crm_type: str = Field(..., description="Type of CRM (klaviyo, salesforce, creatio)")
    credentials: Dict[str, Any] = Field(..., description="CRM-specific credentials")
    selected_fields: Optional[List[str]] = Field(
        None,
        description="List of fields to sync (e.g., ['first_name', 'last_name', 'email', 'phone'])"
    )
    lead_quality: Optional[str] = Field(
        None,
        description="Lead quality category (placeholder for future implementation)"
    )
    settings: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Optional CRM settings (field_mapping, enabled_events, etc.). Note: sync_frequency is automatically set to 'real-time'"
    )


class CRMUpdateRequest(BaseModel):
    """Request model for updating a CRM integration"""
    credentials: Optional[Dict[str, Any]] = Field(
        None,
        description="CRM-specific credentials (if updating credentials)"
    )
    selected_fields: Optional[List[str]] = Field(
        None,
        description="List of fields to sync (e.g., ['first_name', 'last_name', 'email', 'phone'])"
    )
    lead_quality: Optional[str] = Field(
        None,
        description="Lead quality category"
    )
    settings: Optional[Dict[str, Any]] = Field(
        None,
        description="CRM settings (enabled_events, etc.). Note: sync_frequency is always 'real-time'"
    )


class CRMIntegrationResponse(BaseModel):
    """Response model for CRM integration"""
    integration_id: UUID4
    user_id: UUID4
    crm_type: str
    is_active: bool
    sync_status: str
    sync_error: Optional[str] = None
    settings: Dict[str, Any] = {}
    selected_fields: Optional[List[str]] = None
    lead_quality: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    last_sync_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CRMSyncLogResponse(BaseModel):
    """Response model for CRM sync log"""
    log_id: UUID4
    integration_id: UUID4
    user_id: UUID4
    crm_type: str
    operation_type: str
    entity_type: str
    entity_id: Optional[str] = None
    status: str
    status_code: Optional[int] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    duration_ms: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class EventData(BaseModel):
    """Model for event data to send to CRM"""
    event_name: str
    properties: Optional[Dict[str, Any]] = None
    timestamp: Optional[datetime] = None


class SyncEventRequest(BaseModel):
    """Request model for syncing events to CRM"""
    event_name: str
    properties: Optional[Dict[str, Any]] = None
    timestamp: Optional[datetime] = None
