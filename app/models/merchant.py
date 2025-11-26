"""Pydantic models for merchant-related operations"""
from pydantic import BaseModel, EmailStr, Field, UUID4
from typing import Optional
from datetime import datetime


class MerchantBase(BaseModel):
    """Base merchant model"""
    email: EmailStr
    name: Optional[str] = None
    company_name: Optional[str] = None
    phone: Optional[str] = None


class MerchantCreate(MerchantBase):
    """Model for creating a merchant"""
    pass


class MerchantUpdate(BaseModel):
    """Model for updating merchant profile"""
    name: Optional[str] = None
    company_name: Optional[str] = None
    phone: Optional[str] = None


class MerchantResponse(MerchantBase):
    """Merchant response model"""
    merchant_id: UUID4
    email_verified: bool = False
    status: str
    plan_id: Optional[str] = None
    trial_ends_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    last_login_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class MerchantBootstrapRequest(BaseModel):
    """Request model for merchant bootstrap (first login)"""
    name: Optional[str] = None
    company_name: Optional[str] = None
    phone: Optional[str] = None
