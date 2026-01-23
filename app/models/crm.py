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
    reconnect: Optional[bool] = Field(
        False, 
        description="Whether to reactivate the integration if it is currently inactive (reconnection logic)"
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


# ============================================================================
# TRANSCRIPT SYNC MODELS
# ============================================================================

class TranscriptSyncSettings(BaseModel):
    """
    Settings for chat transcript sync to CRM.
    Stored in crm_integrations.settings['transcript_sync']
    """
    enabled: bool = Field(default=True, description="Enable transcript sync to this CRM")
    send_on_conversation_end: bool = Field(default=True, description="Send transcript when conversation ends")
    include_summary: bool = Field(default=True, description="Include AI-generated conversation summary")
    include_full_transcript: bool = Field(default=False, description="Include full message history")
    include_sentiment: bool = Field(default=False, description="Include sentiment analysis")


class ConversationMessage(BaseModel):
    """Individual message in a conversation"""
    role: str = Field(..., description="Message role: 'user' or 'assistant'")
    content: str = Field(..., description="Message content")
    timestamp: Optional[datetime] = Field(None, description="Message timestamp")


class LeadWithTranscriptRequest(BaseModel):
    """
    Request model for syncing a lead with conversation transcript to CRM.
    Called by Langflow SyncToCRM component when customer info is captured.
    """
    # Session & Merchant identification
    session_id: str = Field(..., description="Unique conversation session ID")
    merchant_id: str = Field(..., description="Merchant identifier (e.g., 'by-kind')")

    # Customer contact info (the lead)
    customer_email: Optional[str] = Field(None, description="Customer email address")
    first_name: Optional[str] = Field(None, description="Customer first name")
    last_name: Optional[str] = Field(None, description="Customer last name")
    phone: Optional[str] = Field(None, description="Customer phone number")

    # Conversation data
    conversation_summary: Optional[str] = Field(
        None,
        description="AI-generated summary of the conversation"
    )
    messages: Optional[List[ConversationMessage]] = Field(
        None,
        description="Full conversation message history"
    )

    # Context
    products_discussed: Optional[List[str]] = Field(
        None,
        description="Products mentioned or recommended in conversation"
    )
    conversation_started_at: Optional[datetime] = Field(None, description="When conversation started")
    conversation_ended_at: Optional[datetime] = Field(None, description="When conversation ended")

    # Additional metadata
    source: str = Field(default="chatbot", description="Lead source identifier")
    custom_properties: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional custom properties to sync"
    )


class LeadSyncResult(BaseModel):
    """Result of syncing to a single CRM"""
    crm_type: str
    success: bool
    crm_contact_id: Optional[str] = None
    crm_activity_id: Optional[str] = None
    error_message: Optional[str] = None


class LeadSyncResponse(BaseModel):
    """Response from lead sync operation"""
    session_id: str
    merchant_id: str
    total_crms: int
    successful_syncs: int
    failed_syncs: int
    results: List[LeadSyncResult]
    synced_at: datetime
