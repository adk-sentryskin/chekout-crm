"""CRM Manager for handling multiple CRM integrations"""

from typing import Dict, Any, Optional, List
import logging

from .base import BaseCRMService, CRMType, CRMServiceError, CRMAuthError, CRMAPIError
from .providers.klaviyo import KlaviyoService
from .providers.salesforce import SalesforceService
from .providers.creatio import CreatioService

logger = logging.getLogger(__name__)


class CRMManager:
    """
    Central manager for all CRM integrations.

    This class provides a unified interface to interact with multiple CRM services.
    It handles service registration, credential management, and data synchronization
    across different CRM platforms.
    """

    def __init__(self):
        self._services: Dict[CRMType, BaseCRMService] = {}
        self._register_services()

    def _register_services(self):
        """Register all available CRM services"""
        self._services[CRMType.KLAVIYO] = KlaviyoService()
        self._services[CRMType.SALESFORCE] = SalesforceService()
        self._services[CRMType.CREATIO] = CreatioService()
        # TODO: Add more CRM services as they are implemented
        # self._services[CRMType.HUBSPOT] = HubspotService()
        # self._services[CRMType.MAILCHIMP] = MailchimpService()

    def get_service(self, crm_type: CRMType) -> BaseCRMService:
        """
        Get a specific CRM service instance.

        Args:
            crm_type: The type of CRM service to retrieve

        Returns:
            CRM service instance

        Raises:
            ValueError: If CRM type is not registered
        """
        if crm_type not in self._services:
            raise ValueError(f"CRM service '{crm_type}' is not registered")
        return self._services[crm_type]

    def get_available_crms(self) -> List[str]:
        """
        Get list of available CRM types.

        Returns:
            List of CRM type names
        """
        return [crm.value for crm in self._services.keys()]

    async def validate_credentials(
        self,
        crm_type: CRMType,
        credentials: Dict[str, Any]
    ) -> bool:
        """
        Validate credentials for a specific CRM.

        Args:
            crm_type: Type of CRM
            credentials: Authentication credentials

        Returns:
            True if credentials are valid

        Raises:
            ValueError: If CRM type is not registered
            CRMAuthError: If credentials are invalid
            CRMAPIError: If API request fails
        """
        service = self.get_service(crm_type)
        return await service.validate_credentials(credentials)

    async def create_or_update_contact(
        self,
        crm_type: CRMType,
        credentials: Dict[str, Any],
        contact_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create or update a contact in a specific CRM.

        Args:
            crm_type: Type of CRM
            credentials: Authentication credentials
            contact_data: Contact information

        Returns:
            Created/updated contact data

        Raises:
            ValueError: If CRM type is not registered
            CRMAuthError: If credentials are invalid
            CRMAPIError: If API request fails
        """
        service = self.get_service(crm_type)
        return await service.create_or_update_contact(credentials, contact_data)

    async def send_event(
        self,
        crm_type: CRMType,
        credentials: Dict[str, Any],
        contact_identifier: Dict[str, str],
        event_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Send an event to a specific CRM.

        Args:
            crm_type: Type of CRM
            credentials: Authentication credentials
            contact_identifier: Contact identifier (email, id, etc.)
            event_data: Event details

        Returns:
            Event creation response

        Raises:
            ValueError: If CRM type is not registered
            CRMAuthError: If credentials are invalid
            CRMAPIError: If API request fails
        """
        service = self.get_service(crm_type)
        return await service.send_event(credentials, contact_identifier, event_data)

    async def get_contact(
        self,
        crm_type: CRMType,
        credentials: Dict[str, Any],
        contact_identifier: Dict[str, str]
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve contact information from a specific CRM.

        Args:
            crm_type: Type of CRM
            credentials: Authentication credentials
            contact_identifier: Contact identifier (email, id, etc.)

        Returns:
            Contact data if found, None otherwise

        Raises:
            ValueError: If CRM type is not registered
            CRMAuthError: If credentials are invalid
            CRMAPIError: If API request fails
        """
        service = self.get_service(crm_type)
        return await service.get_contact(credentials, contact_identifier)

    async def sync_contact_to_multiple_crms(
        self,
        crm_configs: List[Dict[str, Any]],
        contact_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Sync a contact to multiple CRM platforms.

        Args:
            crm_configs: List of dicts with 'crm_type' and 'credentials'
            contact_data: Contact information to sync

        Returns:
            Dict with results for each CRM (success/failure)
        """
        results = {}

        for config in crm_configs:
            crm_type = config.get("crm_type")
            credentials = config.get("credentials")

            if not crm_type or not credentials:
                logger.warning(f"Invalid CRM config: {config}")
                continue

            try:
                result = await self.create_or_update_contact(
                    CRMType(crm_type),
                    credentials,
                    contact_data
                )
                results[crm_type] = {
                    "success": True,
                    "data": result
                }
                logger.info(f"Successfully synced contact to {crm_type}")
            except (CRMAuthError, CRMAPIError) as e:
                results[crm_type] = {
                    "success": False,
                    "error": str(e)
                }
                logger.error(f"Failed to sync contact to {crm_type}: {str(e)}")
            except Exception as e:
                results[crm_type] = {
                    "success": False,
                    "error": f"Unexpected error: {str(e)}"
                }
                logger.error(f"Unexpected error syncing to {crm_type}: {str(e)}", exc_info=True)

        return results

    async def send_event_to_multiple_crms(
        self,
        crm_configs: List[Dict[str, Any]],
        contact_identifier: Dict[str, str],
        event_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Send an event to multiple CRM platforms.

        Args:
            crm_configs: List of dicts with 'crm_type' and 'credentials'
            contact_identifier: Contact identifier
            event_data: Event details

        Returns:
            Dict with results for each CRM (success/failure)
        """
        results = {}

        for config in crm_configs:
            crm_type = config.get("crm_type")
            credentials = config.get("credentials")

            if not crm_type or not credentials:
                logger.warning(f"Invalid CRM config: {config}")
                continue

            try:
                result = await self.send_event(
                    CRMType(crm_type),
                    credentials,
                    contact_identifier,
                    event_data
                )
                results[crm_type] = {
                    "success": True,
                    "data": result
                }
                logger.info(f"Successfully sent event to {crm_type}")
            except (CRMAuthError, CRMAPIError) as e:
                results[crm_type] = {
                    "success": False,
                    "error": str(e)
                }
                logger.error(f"Failed to send event to {crm_type}: {str(e)}")
            except Exception as e:
                results[crm_type] = {
                    "success": False,
                    "error": f"Unexpected error: {str(e)}"
                }
                logger.error(f"Unexpected error sending event to {crm_type}: {str(e)}", exc_info=True)

        return results

    # Database placeholder methods
    async def get_user_crm_integrations(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Placeholder: Get all active CRM integrations for a user from database.

        Args:
            user_id: User identifier

        Returns:
            List of CRM integration configs

        TODO: Implement database query
        Example query:
            SELECT crm_type, encrypted_credentials, settings, is_active
            FROM crm_integrations
            WHERE user_id = $1 AND is_active = TRUE
        """
        raise NotImplementedError("Database integration pending")

    async def save_crm_integration(
        self,
        user_id: str,
        crm_type: CRMType,
        credentials: Dict[str, Any],
        settings: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Placeholder: Save or update a CRM integration for a user in database.

        Args:
            user_id: User identifier
            crm_type: Type of CRM
            credentials: Authentication credentials (should be encrypted)
            settings: Optional integration settings

        Returns:
            Saved integration data with integration_id

        TODO: Implement database insertion/update with credential encryption
        Example query:
            INSERT INTO crm_integrations (user_id, crm_type, encrypted_credentials, settings)
            VALUES ($1, $2, encrypt($3), $4)
            ON CONFLICT (user_id, crm_type) DO UPDATE
            SET encrypted_credentials = encrypt($3), settings = $4, updated_at = NOW()
            RETURNING integration_id, created_at, updated_at
        """
        raise NotImplementedError("Database integration pending")

    async def delete_crm_integration(
        self,
        user_id: str,
        crm_type: CRMType
    ) -> bool:
        """
        Placeholder: Soft delete a CRM integration for a user in database.

        Args:
            user_id: User identifier
            crm_type: Type of CRM

        Returns:
            True if deleted successfully

        TODO: Implement database soft delete
        Example query:
            UPDATE crm_integrations
            SET is_active = FALSE, updated_at = NOW()
            WHERE user_id = $1 AND crm_type = $2
            RETURNING integration_id
        """
        raise NotImplementedError("Database integration pending")


# Singleton instance
crm_manager = CRMManager()
