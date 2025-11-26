"""
Template for creating new CRM provider implementations.

INSTRUCTIONS:
1. Copy this file and rename it (e.g., hubspot.py, salesforce.py)
2. Update the class name and CRM-specific constants
3. Implement all methods from BaseCRMService
4. Add the CRM type to CRMType enum in ../base.py
5. Register in ../manager.py _register_services()
6. Export in __init__.py

QUICK START:
    from ..base import BaseCRMService, CRMType, CRMAuthError, CRMAPIError

    class YourCRMService(BaseCRMService):
        def __init__(self):
            super().__init__(CRMType.YOUR_CRM)
            # Initialize your CRM-specific config
"""

import httpx
from typing import Dict, Any, Optional
import logging

from ..base import BaseCRMService, CRMType, CRMAuthError, CRMAPIError

logger = logging.getLogger(__name__)

# TODO: Update these constants
YOUR_CRM_API_BASE = "https://api.yourcrm.com"
YOUR_CRM_API_VERSION = "v1"


class YourCRMService(BaseCRMService):
    """Service for interacting with Your CRM API"""

    def __init__(self):
        # TODO: Update CRMType enum value
        super().__init__(CRMType.HUBSPOT)  # Change this to your CRM
        self.base_url = YOUR_CRM_API_BASE
        self.api_version = YOUR_CRM_API_VERSION

    def _get_headers(self, credentials: Dict[str, Any]) -> Dict[str, str]:
        """Generate headers for API requests"""
        # TODO: Customize based on your CRM's auth (API key, Bearer token, etc.)
        api_key = credentials.get("api_key", "")
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    async def validate_credentials(self, credentials: Dict[str, Any]) -> bool:
        """
        Validate CRM credentials.

        TODO: Call a lightweight endpoint to verify credentials.
        """
        url = f"{self.base_url}/account"  # Or similar validation endpoint
        headers = self._get_headers(credentials)

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, headers=headers)

                if response.status_code in [401, 403]:
                    raise CRMAuthError("Invalid credentials")

                if response.status_code >= 400:
                    raise CRMAPIError(f"API validation failed: {response.status_code}")

                return True

        except httpx.TimeoutException:
            raise CRMAPIError("Request timed out")
        except httpx.RequestError as e:
            raise CRMAPIError(f"Failed to connect: {str(e)}")

    async def create_or_update_contact(
        self,
        credentials: Dict[str, Any],
        contact_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create or update a contact.

        TODO: Map contact_data to your CRM's format.
        Common fields: email, first_name, last_name, phone_number, custom_fields
        """
        url = f"{self.base_url}/contacts"
        headers = self._get_headers(credentials)

        # TODO: Transform contact_data to match your CRM's API format
        payload = {
            "email": contact_data.get("email"),
            "firstName": contact_data.get("first_name"),
            "lastName": contact_data.get("last_name"),
            # Add more fields as needed
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, headers=headers, json=payload)

                if response.status_code in [401, 403]:
                    raise CRMAuthError("Invalid credentials")

                if response.status_code >= 400:
                    raise CRMAPIError(f"Contact creation failed: {response.status_code}")

                return response.json()

        except httpx.TimeoutException:
            raise CRMAPIError("Request timed out")
        except httpx.RequestError as e:
            raise CRMAPIError(f"Failed to connect: {str(e)}")

    async def send_event(
        self,
        credentials: Dict[str, Any],
        contact_identifier: Dict[str, str],
        event_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Send an event/activity.

        TODO: Map event_data to your CRM's format.
        Common fields: event_name, properties, timestamp
        """
        url = f"{self.base_url}/events"
        headers = self._get_headers(credentials)

        # TODO: Transform event_data to match your CRM's API format
        payload = {
            "contactId": contact_identifier.get("id"),
            "eventName": event_data.get("event_name"),
            "properties": event_data.get("properties", {}),
            # Add more fields as needed
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, headers=headers, json=payload)

                if response.status_code in [401, 403]:
                    raise CRMAuthError("Invalid credentials")

                if response.status_code >= 400:
                    raise CRMAPIError(f"Event creation failed: {response.status_code}")

                return response.json()

        except httpx.TimeoutException:
            raise CRMAPIError("Request timed out")
        except httpx.RequestError as e:
            raise CRMAPIError(f"Failed to connect: {str(e)}")

    async def get_contact(
        self,
        credentials: Dict[str, Any],
        contact_identifier: Dict[str, str]
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve a contact.

        TODO: Support lookup by id, email, or phone_number.
        """
        headers = self._get_headers(credentials)

        # TODO: Build URL based on identifier type
        if "id" in contact_identifier:
            url = f"{self.base_url}/contacts/{contact_identifier['id']}"
        else:
            url = f"{self.base_url}/contacts/search"
            # Add query params for search

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, headers=headers)

                if response.status_code in [401, 403]:
                    raise CRMAuthError("Invalid credentials")

                if response.status_code == 404:
                    return None

                if response.status_code >= 400:
                    raise CRMAPIError(f"Contact retrieval failed: {response.status_code}")

                return response.json()

        except httpx.TimeoutException:
            raise CRMAPIError("Request timed out")
        except httpx.RequestError as e:
            raise CRMAPIError(f"Failed to connect: {str(e)}")


# Singleton instance
your_crm_service = YourCRMService()
