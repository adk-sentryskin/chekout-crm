"""Creatio (formerly bpm'online) CRM Service Implementation

Uses Creatio OData 4 API (RESTful)
API Version: 8.x
Documentation: https://academy.creatio.com/docs/developer/integrations_and_api/web_services
"""

import httpx
from typing import Dict, Any, Optional
import logging
import base64

from ..base import BaseCRMService, CRMType, CRMAuthError, CRMAPIError

logger = logging.getLogger(__name__)


class CreatioService(BaseCRMService):
    """
    Service for interacting with Creatio API.

    Uses Basic Authentication with username/password.
    Supports OData 4.0 protocol for CRUD operations.
    """

    def __init__(self):
        super().__init__(CRMType.CREATIO)
        self.api_path = "/0/odata"  # OData endpoint

    def _get_base_url(self, instance_url: str) -> str:
        """Get base URL for Creatio instance"""
        # Remove trailing slash
        return instance_url.rstrip("/")

    def _get_headers(self, credentials: Dict[str, Any]) -> Dict[str, str]:
        """Generate headers for Creatio API requests with Basic Auth"""
        username = credentials.get("username")
        password = credentials.get("password")

        if not username or not password:
            raise CRMAuthError("Username and password are required")

        # Create Basic Auth token
        auth_string = f"{username}:{password}"
        auth_bytes = auth_string.encode("utf-8")
        auth_b64 = base64.b64encode(auth_bytes).decode("utf-8")

        return {
            "Authorization": f"Basic {auth_b64}",
            "Content-Type": "application/json;odata=verbose",
            "Accept": "application/json;odata=verbose"
        }

    async def validate_credentials(self, credentials: Dict[str, Any]) -> bool:
        """
        Validate Creatio credentials by querying system info.

        Args:
            credentials: Dict with:
                - instance_url: Your Creatio instance URL (e.g., https://mycompany.creatio.com)
                - username: Creatio username
                - password: Creatio password

        Returns:
            True if credentials are valid
        """
        instance_url = credentials.get("instance_url")
        if not instance_url:
            raise CRMAuthError("instance_url is required")

        base_url = self._get_base_url(instance_url)
        headers = self._get_headers(credentials)

        # Test with lightweight query - get system settings
        url = f"{base_url}{self.api_path}/SysSettings?$top=1"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, headers=headers)

                if response.status_code == 401:
                    raise CRMAuthError("Invalid username or password")

                if response.status_code == 403:
                    raise CRMAuthError("Access denied - check user permissions")

                if response.status_code >= 400:
                    raise CRMAPIError(f"Validation failed: {response.status_code}")

                logger.info("Creatio credentials validated successfully")
                return True

        except httpx.TimeoutException:
            raise CRMAPIError("Request to Creatio timed out")
        except httpx.RequestError as e:
            raise CRMAPIError(f"Failed to connect to Creatio: {str(e)}")

    async def create_or_update_contact(
        self,
        credentials: Dict[str, Any],
        contact_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create or update a Contact in Creatio.

        Uses email as unique identifier for upsert.

        Args:
            credentials: Authentication credentials
            contact_data: Dict with fields like:
                - Name (required)
                - Email (recommended for upsert)
                - MobilePhone, HomePhone, Phone
                - BirthDate (YYYY-MM-DD)
                - Notes
                - AccountId (GUID if linking to Account)

        Returns:
            Created/updated contact data with Id
        """
        instance_url = credentials.get("instance_url")
        base_url = self._get_base_url(instance_url)
        headers = self._get_headers(credentials)

        email = contact_data.get("Email")
        name = contact_data.get("Name")

        if not name:
            raise CRMAPIError("Name is required for Creatio Contact")

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                # Check if contact exists by email
                contact_id = None
                if email:
                    search_url = f"{base_url}{self.api_path}/Contact"
                    search_params = {
                        "$filter": f"Email eq '{email}'",
                        "$select": "Id",
                        "$top": 1
                    }

                    response = await client.get(
                        search_url,
                        headers=headers,
                        params=search_params
                    )

                    if response.status_code == 401:
                        raise CRMAuthError("Invalid credentials")

                    if response.status_code >= 400:
                        raise CRMAPIError(f"Search failed: {response.status_code}")

                    result = response.json()
                    existing = result.get("value", [])

                    if existing:
                        contact_id = existing[0]["Id"]

                if contact_id:
                    # Update existing contact
                    url = f"{base_url}{self.api_path}/Contact(guid'{contact_id}')"

                    response = await client.patch(url, headers=headers, json=contact_data)

                    if response.status_code == 401:
                        raise CRMAuthError("Invalid credentials")

                    if response.status_code >= 400:
                        error_text = response.text
                        raise CRMAPIError(f"Update failed: {error_text}")

                    logger.info(f"Creatio Contact updated: {contact_id}")
                    return {"Id": contact_id, "created": False, **contact_data}

                else:
                    # Create new contact
                    url = f"{base_url}{self.api_path}/Contact"

                    response = await client.post(url, headers=headers, json=contact_data)

                    if response.status_code == 401:
                        raise CRMAuthError("Invalid credentials")

                    if response.status_code >= 400:
                        error_text = response.text
                        raise CRMAPIError(f"Creation failed: {error_text}")

                    result = response.json()
                    contact_id = result.get("Id")
                    logger.info(f"Creatio Contact created: {contact_id}")
                    return {"Id": contact_id, "created": True, **contact_data}

        except httpx.TimeoutException:
            raise CRMAPIError("Request to Creatio timed out")
        except httpx.RequestError as e:
            raise CRMAPIError(f"Failed to connect to Creatio: {str(e)}")

    async def send_event(
        self,
        credentials: Dict[str, Any],
        contact_identifier: Dict[str, str],
        event_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create an Activity in Creatio for a Contact.

        Args:
            credentials: Authentication credentials
            contact_identifier: Dict with 'id' or 'email'
            event_data: Dict with:
                - Title (required) - e.g., "Purchase Completed"
                - Notes - Description
                - ActivityCategoryId (GUID) - Optional: type of activity
                - StartDate (ISO format) - Default: now
                - Status (optional)

        Returns:
            Created Activity data with Id
        """
        instance_url = credentials.get("instance_url")
        base_url = self._get_base_url(instance_url)
        headers = self._get_headers(credentials)

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                # Get contact ID if email provided
                contact_id = contact_identifier.get("id")

                if not contact_id and "email" in contact_identifier:
                    email = contact_identifier["email"]
                    search_url = f"{base_url}{self.api_path}/Contact"
                    search_params = {
                        "$filter": f"Email eq '{email}'",
                        "$select": "Id",
                        "$top": 1
                    }

                    response = await client.get(
                        search_url,
                        headers=headers,
                        params=search_params
                    )

                    if response.status_code >= 400:
                        raise CRMAPIError(f"Contact search failed: {response.status_code}")

                    result = response.json()
                    contacts = result.get("value", [])

                    if not contacts:
                        raise CRMAPIError(f"Contact not found: {email}")

                    contact_id = contacts[0]["Id"]

                if not contact_id:
                    raise CRMAPIError("Contact ID or email is required")

                # Create Activity
                activity_data = {
                    "ContactId": contact_id,
                    "Title": event_data.get("Title", "Activity"),
                    "Notes": event_data.get("Notes", ""),
                    "StartDate": event_data.get("StartDate"),
                }

                # Add optional fields if provided
                if "ActivityCategoryId" in event_data:
                    activity_data["ActivityCategoryId"] = event_data["ActivityCategoryId"]

                url = f"{base_url}{self.api_path}/Activity"

                response = await client.post(url, headers=headers, json=activity_data)

                if response.status_code == 401:
                    raise CRMAuthError("Invalid credentials")

                if response.status_code >= 400:
                    error_text = response.text
                    raise CRMAPIError(f"Activity creation failed: {error_text}")

                result = response.json()
                activity_id = result.get("Id")
                logger.info(f"Creatio Activity created: {activity_id}")
                return {"Id": activity_id, "success": True, **activity_data}

        except httpx.TimeoutException:
            raise CRMAPIError("Request to Creatio timed out")
        except httpx.RequestError as e:
            raise CRMAPIError(f"Failed to connect to Creatio: {str(e)}")

    async def get_contact(
        self,
        credentials: Dict[str, Any],
        contact_identifier: Dict[str, str]
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve a Contact from Creatio.

        Args:
            credentials: Authentication credentials
            contact_identifier: Dict with 'id' or 'email'

        Returns:
            Contact data if found, None otherwise
        """
        instance_url = credentials.get("instance_url")
        base_url = self._get_base_url(instance_url)
        headers = self._get_headers(credentials)

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                if "id" in contact_identifier:
                    # Direct lookup by ID
                    contact_id = contact_identifier["id"]
                    url = f"{base_url}{self.api_path}/Contact(guid'{contact_id}')"

                    response = await client.get(url, headers=headers)

                    if response.status_code == 404:
                        return None

                    if response.status_code == 401:
                        raise CRMAuthError("Invalid credentials")

                    if response.status_code >= 400:
                        raise CRMAPIError(f"Contact retrieval failed: {response.status_code}")

                    return response.json()

                elif "email" in contact_identifier:
                    # Search by email
                    email = contact_identifier["email"]
                    url = f"{base_url}{self.api_path}/Contact"
                    params = {
                        "$filter": f"Email eq '{email}'",
                        "$top": 1
                    }

                    response = await client.get(url, headers=headers, params=params)

                    if response.status_code == 401:
                        raise CRMAuthError("Invalid credentials")

                    if response.status_code >= 400:
                        raise CRMAPIError(f"Contact search failed: {response.status_code}")

                    result = response.json()
                    contacts = result.get("value", [])

                    return contacts[0] if contacts else None

                else:
                    raise CRMAPIError("Contact ID or email is required")

        except httpx.TimeoutException:
            raise CRMAPIError("Request to Creatio timed out")
        except httpx.RequestError as e:
            raise CRMAPIError(f"Failed to connect to Creatio: {str(e)}")


# Singleton instance
creatio_service = CreatioService()
