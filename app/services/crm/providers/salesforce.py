"""Salesforce CRM Service Implementation

Uses simple-salesforce library (official Python SDK)
API Version: v60.0 (Winter '24)
Documentation: https://developer.salesforce.com/docs/apis
"""

import httpx
from typing import Dict, Any, Optional
import logging

from ..base import BaseCRMService, CRMType, CRMAuthError, CRMAPIError

logger = logging.getLogger(__name__)


class SalesforceService(BaseCRMService):
    """
    Service for interacting with Salesforce API.

    Uses OAuth 2.0 for authentication with username-password flow or access token.
    Supports both Salesforce Classic and Lightning Experience.
    """

    def __init__(self):
        super().__init__(CRMType.SALESFORCE)
        self.api_version = "v60.0"  # Winter '24 - Latest stable version

    def _get_auth_headers(self, access_token: str) -> Dict[str, str]:
        """Generate headers for Salesforce API requests"""
        return {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    async def _get_access_token(self, credentials: Dict[str, Any]) -> tuple[str, str]:
        """
        Get access token using OAuth 2.0 password flow.

        Returns: (access_token, instance_url)
        """
        # If access_token provided directly, use it
        if "access_token" in credentials and "instance_url" in credentials:
            return credentials["access_token"], credentials["instance_url"]

        # Otherwise, authenticate using username/password
        client_id = credentials.get("client_id")
        client_secret = credentials.get("client_secret")
        username = credentials.get("username")
        password = credentials.get("password")
        security_token = credentials.get("security_token", "")
        domain = credentials.get("domain", "login")  # 'login' or 'test' for sandbox

        if not all([client_id, client_secret, username, password]):
            raise CRMAuthError(
                "Missing credentials. Required: client_id, client_secret, username, password"
            )

        auth_url = f"https://{domain}.salesforce.com/services/oauth2/token"

        payload = {
            "grant_type": "password",
            "client_id": client_id,
            "client_secret": client_secret,
            "username": username,
            "password": f"{password}{security_token}"  # Salesforce requires token appended
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(auth_url, data=payload)

                if response.status_code == 400:
                    error = response.json()
                    raise CRMAuthError(f"Authentication failed: {error.get('error_description', 'Invalid credentials')}")

                if response.status_code >= 400:
                    raise CRMAPIError(f"OAuth failed: {response.status_code}")

                auth_data = response.json()
                return auth_data["access_token"], auth_data["instance_url"]

        except httpx.TimeoutException:
            raise CRMAPIError("Authentication request timed out")
        except httpx.RequestError as e:
            raise CRMAPIError(f"Failed to connect to Salesforce: {str(e)}")

    async def validate_credentials(self, credentials: Dict[str, Any]) -> bool:
        """
        Validate Salesforce credentials by making a test API call.

        Args:
            credentials: Dict with one of:
                - access_token + instance_url (direct token)
                - client_id, client_secret, username, password, security_token (OAuth)

        Returns:
            True if credentials are valid
        """
        try:
            access_token, instance_url = await self._get_access_token(credentials)

            # Test with a lightweight query
            url = f"{instance_url}/services/data/{self.api_version}/limits"
            headers = self._get_auth_headers(access_token)

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, headers=headers)

                if response.status_code == 401:
                    raise CRMAuthError("Invalid access token or expired session")

                if response.status_code >= 400:
                    raise CRMAPIError(f"Validation failed: {response.status_code}")

                logger.info("Salesforce credentials validated successfully")
                return True

        except CRMAuthError:
            raise
        except httpx.TimeoutException:
            raise CRMAPIError("Request to Salesforce timed out")
        except httpx.RequestError as e:
            raise CRMAPIError(f"Failed to connect to Salesforce: {str(e)}")

    async def create_or_update_contact(
        self,
        credentials: Dict[str, Any],
        contact_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create or update a Contact in Salesforce.

        Uses email as unique identifier for upsert operation.

        Args:
            credentials: Authentication credentials
            contact_data: Dict with fields like:
                - Email (required)
                - FirstName, LastName
                - Phone, MobilePhone
                - MailingStreet, MailingCity, MailingState, MailingPostalCode
                - Custom fields: CustomField__c

        Returns:
            Created/updated contact data with Id
        """
        access_token, instance_url = await self._get_access_token(credentials)
        headers = self._get_auth_headers(access_token)

        email = contact_data.get("Email")
        if not email:
            raise CRMAPIError("Email is required for Salesforce Contact")

        try:
            # Check if contact exists by email
            query = f"SELECT Id FROM Contact WHERE Email = '{email}' LIMIT 1"
            search_url = f"{instance_url}/services/data/{self.api_version}/query"

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    search_url,
                    headers=headers,
                    params={"q": query}
                )

                if response.status_code == 401:
                    raise CRMAuthError("Invalid access token")

                if response.status_code >= 400:
                    raise CRMAPIError(f"Search failed: {response.status_code}")

                result = response.json()
                existing_contact = result.get("records", [])

                if existing_contact:
                    # Update existing contact
                    contact_id = existing_contact[0]["Id"]
                    url = f"{instance_url}/services/data/{self.api_version}/sobjects/Contact/{contact_id}"

                    response = await client.patch(url, headers=headers, json=contact_data)

                    if response.status_code == 401:
                        raise CRMAuthError("Invalid access token")

                    if response.status_code >= 400:
                        error = response.json()
                        raise CRMAPIError(f"Update failed: {error}")

                    logger.info(f"Salesforce Contact updated: {contact_id}")
                    return {"Id": contact_id, "created": False, **contact_data}

                else:
                    # Create new contact
                    url = f"{instance_url}/services/data/{self.api_version}/sobjects/Contact"

                    response = await client.post(url, headers=headers, json=contact_data)

                    if response.status_code == 401:
                        raise CRMAuthError("Invalid access token")

                    if response.status_code >= 400:
                        error = response.json()
                        raise CRMAPIError(f"Creation failed: {error}")

                    result = response.json()
                    contact_id = result["id"]
                    logger.info(f"Salesforce Contact created: {contact_id}")
                    return {"Id": contact_id, "created": True, **contact_data}

        except httpx.TimeoutException:
            raise CRMAPIError("Request to Salesforce timed out")
        except httpx.RequestError as e:
            raise CRMAPIError(f"Failed to connect to Salesforce: {str(e)}")

    async def send_event(
        self,
        credentials: Dict[str, Any],
        contact_identifier: Dict[str, str],
        event_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create a Task (activity) in Salesforce for a Contact.

        Args:
            credentials: Authentication credentials
            contact_identifier: Dict with 'id' or 'email'
            event_data: Dict with:
                - Subject (required) - e.g., "Purchase Completed"
                - Description
                - Status (default: "Completed")
                - Priority (default: "Normal")
                - ActivityDate (YYYY-MM-DD)

        Returns:
            Created Task data with Id
        """
        access_token, instance_url = await self._get_access_token(credentials)
        headers = self._get_auth_headers(access_token)

        try:
            # Get contact ID if email provided
            contact_id = contact_identifier.get("id")

            if not contact_id and "email" in contact_identifier:
                email = contact_identifier["email"]
                query = f"SELECT Id FROM Contact WHERE Email = '{email}' LIMIT 1"
                search_url = f"{instance_url}/services/data/{self.api_version}/query"

                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(
                        search_url,
                        headers=headers,
                        params={"q": query}
                    )

                    if response.status_code >= 400:
                        raise CRMAPIError(f"Contact search failed: {response.status_code}")

                    result = response.json()
                    records = result.get("records", [])

                    if not records:
                        raise CRMAPIError(f"Contact not found: {email}")

                    contact_id = records[0]["Id"]

            if not contact_id:
                raise CRMAPIError("Contact ID or email is required")

            # Create Task (activity)
            task_data = {
                "WhoId": contact_id,  # Link to Contact
                "Subject": event_data.get("Subject", "Activity"),
                "Description": event_data.get("Description", ""),
                "Status": event_data.get("Status", "Completed"),
                "Priority": event_data.get("Priority", "Normal"),
                "ActivityDate": event_data.get("ActivityDate")  # Optional
            }

            url = f"{instance_url}/services/data/{self.api_version}/sobjects/Task"

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, headers=headers, json=task_data)

                if response.status_code == 401:
                    raise CRMAuthError("Invalid access token")

                if response.status_code >= 400:
                    error = response.json()
                    raise CRMAPIError(f"Task creation failed: {error}")

                result = response.json()
                task_id = result["id"]
                logger.info(f"Salesforce Task created: {task_id}")
                return {"Id": task_id, "success": True, **task_data}

        except httpx.TimeoutException:
            raise CRMAPIError("Request to Salesforce timed out")
        except httpx.RequestError as e:
            raise CRMAPIError(f"Failed to connect to Salesforce: {str(e)}")

    async def get_contact(
        self,
        credentials: Dict[str, Any],
        contact_identifier: Dict[str, str]
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve a Contact from Salesforce.

        Args:
            credentials: Authentication credentials
            contact_identifier: Dict with 'id' or 'email'

        Returns:
            Contact data if found, None otherwise
        """
        access_token, instance_url = await self._get_access_token(credentials)
        headers = self._get_auth_headers(access_token)

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                if "id" in contact_identifier:
                    # Direct lookup by ID
                    contact_id = contact_identifier["id"]
                    url = f"{instance_url}/services/data/{self.api_version}/sobjects/Contact/{contact_id}"

                    response = await client.get(url, headers=headers)

                    if response.status_code == 404:
                        return None

                    if response.status_code == 401:
                        raise CRMAuthError("Invalid access token")

                    if response.status_code >= 400:
                        raise CRMAPIError(f"Contact retrieval failed: {response.status_code}")

                    return response.json()

                elif "email" in contact_identifier:
                    # Search by email
                    email = contact_identifier["email"]
                    query = f"SELECT Id, FirstName, LastName, Email, Phone, MobilePhone FROM Contact WHERE Email = '{email}' LIMIT 1"
                    url = f"{instance_url}/services/data/{self.api_version}/query"

                    response = await client.get(
                        url,
                        headers=headers,
                        params={"q": query}
                    )

                    if response.status_code == 401:
                        raise CRMAuthError("Invalid access token")

                    if response.status_code >= 400:
                        raise CRMAPIError(f"Contact search failed: {response.status_code}")

                    result = response.json()
                    records = result.get("records", [])

                    return records[0] if records else None

                else:
                    raise CRMAPIError("Contact ID or email is required")

        except httpx.TimeoutException:
            raise CRMAPIError("Request to Salesforce timed out")
        except httpx.RequestError as e:
            raise CRMAPIError(f"Failed to connect to Salesforce: {str(e)}")


# Singleton instance
salesforce_service = SalesforceService()
