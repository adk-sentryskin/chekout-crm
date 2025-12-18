"""Standard Contact Schema - Universal contact format for all CRM integrations"""

from pydantic import BaseModel, Field, EmailStr, field_validator
from typing import Optional, Dict, Any
from datetime import datetime


class StandardContactData(BaseModel):
    """
    Universal standard contact schema.

    All clients should send contact data in this format.
    Backend handles transformation to CRM-specific formats.

    Benefits:
    - One schema for all CRMs
    - No CRM-specific knowledge needed by clients
    - Backend controls all field mappings
    - Easy to maintain and update
    """

    # ==========================================
    # REQUIRED FIELDS
    # ==========================================
    email: EmailStr = Field(
        ...,
        description="Contact email address (required)"
    )

    # ==========================================
    # PERSONAL INFORMATION (Optional)
    # ==========================================
    first_name: Optional[str] = Field(
        None,
        max_length=100,
        description="Contact's first name"
    )

    last_name: Optional[str] = Field(
        None,
        max_length=100,
        description="Contact's last name"
    )

    phone: Optional[str] = Field(
        None,
        max_length=20,
        description="Contact's phone number (E.164 format recommended: +1234567890)"
    )

    # ==========================================
    # COMPANY INFORMATION (Optional)
    # ==========================================
    company: Optional[str] = Field(
        None,
        max_length=200,
        description="Company or organization name"
    )

    job_title: Optional[str] = Field(
        None,
        max_length=100,
        description="Job title or position"
    )

    department: Optional[str] = Field(
        None,
        max_length=100,
        description="Department within organization"
    )

    # ==========================================
    # ADDRESS FIELDS (Optional)
    # ==========================================
    street_address: Optional[str] = Field(
        None,
        max_length=255,
        description="Street address (line 1)"
    )

    street_address_2: Optional[str] = Field(
        None,
        max_length=255,
        description="Street address (line 2)"
    )

    city: Optional[str] = Field(
        None,
        max_length=100,
        description="City"
    )

    state: Optional[str] = Field(
        None,
        max_length=100,
        description="State, province, or region"
    )

    postal_code: Optional[str] = Field(
        None,
        max_length=20,
        description="Postal code or ZIP code"
    )

    country: Optional[str] = Field(
        None,
        max_length=100,
        description="Country (ISO 3166-1 alpha-2 code recommended: US, CA, GB, etc.)"
    )

    # ==========================================
    # ADDITIONAL FIELDS (Optional)
    # ==========================================
    website: Optional[str] = Field(
        None,
        max_length=255,
        description="Website URL"
    )

    timezone: Optional[str] = Field(
        None,
        max_length=50,
        description="Timezone (IANA timezone identifier: America/New_York, etc.)"
    )

    language: Optional[str] = Field(
        None,
        max_length=10,
        description="Preferred language (ISO 639-1 code: en, es, fr, etc.)"
    )

    # ==========================================
    # CUSTOM PROPERTIES (Flexible)
    # ==========================================
    custom_properties: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Custom properties for additional data (lead_score, source, tags, etc.)"
    )

    # ==========================================
    # VALIDATORS
    # ==========================================
    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        """Validate and normalize phone number"""
        if v is None:
            return v

        # Remove common formatting characters
        cleaned = v.replace(' ', '').replace('-', '').replace('(', '').replace(')', '').replace('.', '')

        # Basic validation - should start with + for international format
        if not cleaned.startswith('+') and len(cleaned) > 0:
            # If no country code, could add default or raise error
            # For now, just return cleaned version
            pass

        return cleaned

    @field_validator('email')
    @classmethod
    def lowercase_email(cls, v: str) -> str:
        """Normalize email to lowercase"""
        return v.lower().strip()

    @field_validator('country')
    @classmethod
    def validate_country(cls, v: Optional[str]) -> Optional[str]:
        """Normalize country code to uppercase"""
        if v is None:
            return v
        return v.upper().strip()

    class Config:
        json_schema_extra = {
            "example": {
                "email": "john.doe@example.com",
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
        }


class StandardEventData(BaseModel):
    """
    Universal standard event schema.

    All clients should send event data in this format.
    Backend handles transformation to CRM-specific formats.
    """

    event_name: str = Field(
        ...,
        max_length=100,
        description="Event name (e.g., 'order_created', 'page_viewed', 'cart_abandoned')"
    )

    properties: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Event properties/attributes"
    )

    timestamp: Optional[datetime] = Field(
        default=None,
        description="Event timestamp (defaults to current time if not provided)"
    )

    value: Optional[float] = Field(
        None,
        description="Monetary value associated with event"
    )

    @field_validator('timestamp', mode='before')
    @classmethod
    def set_default_timestamp(cls, v):
        """Set default timestamp if not provided"""
        if v is None:
            return datetime.utcnow()
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "event_name": "order_created",
                "properties": {
                    "order_id": "ORD-12345",
                    "total_amount": 99.99,
                    "currency": "USD",
                    "items_count": 3
                },
                "value": 99.99,
                "timestamp": "2025-12-18T10:30:00Z"
            }
        }
