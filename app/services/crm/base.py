"""Base CRM service interface for all CRM integrations"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from enum import Enum


class CRMType(str, Enum):
    """Supported CRM types"""
    KLAVIYO = "klaviyo"
    SALESFORCE = "salesforce"
    CREATIO = "creatio"
    HUBSPOT = "hubspot"
    MAILCHIMP = "mailchimp"
    ACTIVECAMPAIGN = "activecampaign"
    SENDINBLUE = "sendinblue"
    ZOHO = "zoho"
    PIPEDRIVE = "pipedrive"
    INTERCOM = "intercom"
    CUSTOMERIO = "customerio"


class CRMServiceError(Exception):
    """Base exception for CRM service errors"""
    pass


class CRMAuthError(CRMServiceError):
    """Raised when CRM authentication fails"""
    pass


class CRMAPIError(CRMServiceError):
    """Raised when CRM API returns an error"""
    pass


class BaseCRMService(ABC):
    """
    Abstract base class for all CRM integrations.

    All CRM services should extend this class and implement the required methods.
    This ensures a consistent interface across all CRM integrations.
    """

    def __init__(self, crm_type: CRMType):
        self.crm_type = crm_type

    @abstractmethod
    async def validate_credentials(self, credentials: Dict[str, Any]) -> bool:
        """
        Validate CRM credentials (API key, OAuth token, etc.).

        Args:
            credentials: Dict containing authentication credentials
                         Format varies by CRM (api_key, access_token, etc.)

        Returns:
            True if credentials are valid

        Raises:
            CRMAuthError: If credentials are invalid
            CRMAPIError: If API request fails
        """
        pass

    @abstractmethod
    async def create_or_update_contact(
        self,
        credentials: Dict[str, Any],
        contact_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create or update a contact/profile in the CRM.

        Args:
            credentials: Authentication credentials for the CRM
            contact_data: Contact information (email, name, phone, custom fields)

        Returns:
            Created/updated contact data from the CRM

        Raises:
            CRMAuthError: If credentials are invalid
            CRMAPIError: If API request fails
        """
        pass

    @abstractmethod
    async def send_event(
        self,
        credentials: Dict[str, Any],
        contact_identifier: Dict[str, str],
        event_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Send an event/activity to the CRM for a specific contact.

        Args:
            credentials: Authentication credentials for the CRM
            contact_identifier: Identifier for the contact (email, id, etc.)
            event_data: Event details (event_name, properties, timestamp, etc.)

        Returns:
            Event creation response from the CRM

        Raises:
            CRMAuthError: If credentials are invalid
            CRMAPIError: If API request fails
        """
        pass

    @abstractmethod
    async def get_contact(
        self,
        credentials: Dict[str, Any],
        contact_identifier: Dict[str, str]
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve contact information from the CRM.

        Args:
            credentials: Authentication credentials for the CRM
            contact_identifier: Identifier for the contact (email, id, etc.)

        Returns:
            Contact data if found, None otherwise

        Raises:
            CRMAuthError: If credentials are invalid
            CRMAPIError: If API request fails
        """
        pass
