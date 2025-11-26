"""Klaviyo CRM Service Implementation"""

import httpx
from typing import Dict, Any, Optional
import logging

from ..base import BaseCRMService, CRMType, CRMAuthError, CRMAPIError

logger = logging.getLogger(__name__)

KLAVIYO_API_BASE = "https://a.klaviyo.com/api"
KLAVIYO_API_VERSION = "2025-10-15"


class KlaviyoService(BaseCRMService):
    """Service for interacting with Klaviyo API"""

    def __init__(self):
        super().__init__(CRMType.KLAVIYO)
        self.base_url = KLAVIYO_API_BASE
        self.api_version = KLAVIYO_API_VERSION

    def _get_headers(self, api_key: str) -> Dict[str, str]:
        """Generate headers for Klaviyo API requests"""
        return {
            "Authorization": f"Klaviyo-API-Key {api_key}",
            "revision": self.api_version,
            "Content-Type": "application/json"
        }

    async def validate_credentials(self, credentials: Dict[str, Any]) -> bool:
        """
        Validate Klaviyo API key by attempting to fetch profiles.

        Args:
            credentials: Dict containing 'api_key'

        Returns:
            True if API key is valid

        Raises:
            CRMAuthError: If API key is invalid
            CRMAPIError: If API request fails
        """
        api_key = credentials.get("api_key", "")
        if not api_key or not api_key.strip():
            raise CRMAuthError("API key is required")

        url = f"{self.base_url}/profiles"
        headers = self._get_headers(api_key)

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    url,
                    headers=headers,
                    params={"page[size]": 1}
                )

                if response.status_code == 401:
                    raise CRMAuthError("Invalid API key")

                if response.status_code == 403:
                    raise CRMAuthError("API key lacks required permissions")

                if response.status_code >= 400:
                    raise CRMAPIError(f"API validation failed: {response.status_code}")

                return True

        except httpx.TimeoutException:
            raise CRMAPIError("Request to Klaviyo API timed out")
        except httpx.RequestError as e:
            raise CRMAPIError(f"Failed to connect to Klaviyo API: {str(e)}")

    async def create_or_update_contact(
        self,
        credentials: Dict[str, Any],
        contact_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create or update a customer profile in Klaviyo.

        Args:
            credentials: Dict containing 'api_key'
            contact_data: Contact data dict with 'attributes' (email, first_name, last_name, phone_number)
                         and optionally 'properties' for custom fields

        Returns:
            Created/updated profile data from Klaviyo

        Raises:
            CRMAuthError: If API key is invalid
            CRMAPIError: If API request fails
        """
        api_key = credentials.get("api_key", "")
        url = f"{self.base_url}/profile-import"
        headers = self._get_headers(api_key)

        # Format profile data according to Klaviyo API spec
        attributes = contact_data.get("attributes", {})
        properties = contact_data.get("properties", {})

        payload = {
            "data": {
                "type": "profile",
                "attributes": attributes
            }
        }

        if properties:
            payload["data"]["properties"] = properties

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    url,
                    headers=headers,
                    json=payload
                )

                if response.status_code == 401:
                    raise CRMAuthError("Invalid API key")

                if response.status_code == 403:
                    raise CRMAuthError("API key lacks required permissions")

                if response.status_code >= 400:
                    error_detail = response.text
                    raise CRMAPIError(f"Profile creation failed: {error_detail}")

                return response.json()

        except httpx.TimeoutException:
            raise CRMAPIError("Request to Klaviyo API timed out")
        except httpx.RequestError as e:
            raise CRMAPIError(f"Failed to connect to Klaviyo API: {str(e)}")

    async def send_event(
        self,
        credentials: Dict[str, Any],
        contact_identifier: Dict[str, str],
        event_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Send a custom event to Klaviyo for a specific profile.

        Args:
            credentials: Dict containing 'api_key'
            contact_identifier: Dict with at least one of: 'id', 'email', or 'phone_number'
            event_data: Event data with 'metric_name', 'properties', 'time', 'value'

        Returns:
            Event creation response from Klaviyo

        Raises:
            CRMAuthError: If API key is invalid
            CRMAPIError: If API request fails
        """
        api_key = credentials.get("api_key", "")
        url = f"{self.base_url}/events"
        headers = self._get_headers(api_key)

        # Build profile data
        profile_data = {"type": "profile"}

        if "id" in contact_identifier:
            profile_data["id"] = contact_identifier["id"]
        else:
            profile_data["attributes"] = {}
            if "email" in contact_identifier:
                profile_data["attributes"]["email"] = contact_identifier["email"]
            if "phone_number" in contact_identifier:
                profile_data["attributes"]["phone_number"] = contact_identifier["phone_number"]

        # Format event data
        payload = {
            "data": {
                "type": "event",
                "attributes": {
                    "metric": {
                        "data": {
                            "type": "metric",
                            "attributes": {
                                "name": event_data.get("metric_name", "Custom Event")
                            }
                        }
                    },
                    "profile": {
                        "data": profile_data
                    }
                }
            }
        }

        # Add optional fields
        if "properties" in event_data:
            payload["data"]["attributes"]["properties"] = event_data["properties"]
        if "time" in event_data:
            payload["data"]["attributes"]["time"] = event_data["time"]
        if "value" in event_data:
            payload["data"]["attributes"]["value"] = event_data["value"]

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    url,
                    headers=headers,
                    json=payload
                )

                if response.status_code == 401:
                    raise CRMAuthError("Invalid API key")

                if response.status_code == 403:
                    raise CRMAuthError("API key lacks required permissions")

                if response.status_code >= 400:
                    error_detail = response.text
                    raise CRMAPIError(f"Event creation failed: {error_detail}")

                return response.json()

        except httpx.TimeoutException:
            raise CRMAPIError("Request to Klaviyo API timed out")
        except httpx.RequestError as e:
            raise CRMAPIError(f"Failed to connect to Klaviyo API: {str(e)}")

    async def get_contact(
        self,
        credentials: Dict[str, Any],
        contact_identifier: Dict[str, str]
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve contact information from Klaviyo.

        Args:
            credentials: Dict containing 'api_key'
            contact_identifier: Dict with at least one of: 'id', 'email', or 'phone_number'

        Returns:
            Contact data if found, None otherwise

        Raises:
            CRMAuthError: If API key is invalid
            CRMAPIError: If API request fails
        """
        api_key = credentials.get("api_key", "")
        headers = self._get_headers(api_key)

        # Build query parameters based on identifier
        if "id" in contact_identifier:
            url = f"{self.base_url}/profiles/{contact_identifier['id']}"
            params = {}
        else:
            url = f"{self.base_url}/profiles"
            params = {}
            if "email" in contact_identifier:
                params["filter"] = f"equals(email,\"{contact_identifier['email']}\")"
            elif "phone_number" in contact_identifier:
                params["filter"] = f"equals(phone_number,\"{contact_identifier['phone_number']}\")"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    url,
                    headers=headers,
                    params=params
                )

                if response.status_code == 401:
                    raise CRMAuthError("Invalid API key")

                if response.status_code == 403:
                    raise CRMAuthError("API key lacks required permissions")

                if response.status_code == 404:
                    return None

                if response.status_code >= 400:
                    error_detail = response.text
                    raise CRMAPIError(f"Get contact failed: {error_detail}")

                result = response.json()

                # If searching by email/phone, extract first result
                if "data" in result and isinstance(result["data"], list):
                    return result["data"][0] if result["data"] else None

                return result

        except httpx.TimeoutException:
            raise CRMAPIError("Request to Klaviyo API timed out")
        except httpx.RequestError as e:
            raise CRMAPIError(f"Failed to connect to Klaviyo API: {str(e)}")

    # Backwards-compatible helper methods
    async def validate_api_key(self, api_key: str) -> bool:
        """Backwards-compatible wrapper for validate_credentials"""
        return await self.validate_credentials({"api_key": api_key})

    async def create_or_update_profile(
        self,
        api_key: str,
        profile_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Backwards-compatible wrapper for create_or_update_contact"""
        return await self.create_or_update_contact(
            {"api_key": api_key},
            profile_data
        )


# Singleton instance
klaviyo_service = KlaviyoService()
