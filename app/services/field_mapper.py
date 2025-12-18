"""
Field Mapping Service - Backend-controlled field transformations

This service handles all field mapping transformations from standard contact schema
to CRM-specific formats. Clients never need to know about CRM-specific field names.

Architecture:
    Standard Contact Data → FieldMappingService → CRM-Specific Format

Benefits:
- Centralized field transformation logic
- No client-side CRM knowledge required
- Easy to update when CRM APIs change
- Consistent transformations across all integrations
- Validation and type checking built-in
"""

import logging
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime

from .field_mappings import (
    FIELD_MAPPINGS,
    CRM_TRANSFORMERS,
    REQUIRED_FIELDS,
    get_supported_crms,
    get_crm_required_fields,
    get_crm_supported_fields,
    is_crm_supported,
)

logger = logging.getLogger(__name__)


class FieldMappingError(Exception):
    """Raised when field mapping fails"""
    pass


class FieldMappingService:
    """
    Service for transforming standard contact data to CRM-specific formats.

    This is the central service that handles all field mapping logic.
    """

    def __init__(self):
        self.field_mappings = FIELD_MAPPINGS
        self.transformers = CRM_TRANSFORMERS
        self.required_fields = REQUIRED_FIELDS

    # ========================================================================
    # MAIN TRANSFORMATION METHOD
    # ========================================================================

    def transform_contact(
        self,
        standard_contact: Dict[str, Any],
        crm_type: str
    ) -> Dict[str, Any]:
        """
        Transform standard contact format to CRM-specific format.

        This is the main entry point for field mapping transformations.

        Args:
            standard_contact: Contact data in standard schema format
            crm_type: Target CRM type (klaviyo, salesforce, etc.)

        Returns:
            CRM-specific formatted data ready to send to CRM API

        Raises:
            FieldMappingError: If transformation fails

        Example:
            >>> service = FieldMappingService()
            >>> standard = {
            ...     "email": "john@example.com",
            ...     "first_name": "John",
            ...     "phone": "+1234567890",
            ...     "company": "Acme Corp"
            ... }
            >>> klaviyo_data = service.transform_contact(standard, "klaviyo")
            >>> # Returns: {"attributes": {"email": "john@example.com", "first_name": "John", ...}}
        """
        try:
            # Validate CRM type
            if not is_crm_supported(crm_type):
                raise FieldMappingError(f"CRM type '{crm_type}' is not supported")

            # Validate required fields
            is_valid, error_msg = self.validate_contact_data(standard_contact, crm_type)
            if not is_valid:
                raise FieldMappingError(f"Validation failed: {error_msg}")

            # Make a copy to avoid mutating original
            contact_copy = standard_contact.copy()

            # Extract custom properties (handled separately)
            custom_properties = contact_copy.pop("custom_properties", {})

            # Step 1: Map standard fields to CRM-specific field names
            mapped_data = self._map_standard_fields(contact_copy, crm_type)

            # Step 2: Apply CRM-specific structure transformation
            transformed_data = self._apply_crm_structure(
                mapped_data,
                custom_properties,
                crm_type
            )

            logger.debug(f"Transformed contact for {crm_type}: {len(mapped_data)} fields mapped")
            return transformed_data

        except FieldMappingError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error transforming contact for {crm_type}: {str(e)}", exc_info=True)
            raise FieldMappingError(f"Failed to transform contact data: {str(e)}")

    # ========================================================================
    # FIELD MAPPING LOGIC
    # ========================================================================

    def _map_standard_fields(
        self,
        standard_data: Dict[str, Any],
        crm_type: str
    ) -> Dict[str, Any]:
        """
        Map standard field names to CRM-specific field names.

        Args:
            standard_data: Standard contact fields
            crm_type: Target CRM type

        Returns:
            Mapped data with CRM-specific field names
        """
        field_mapping = self.field_mappings[crm_type]
        mapped_data = {}

        for standard_field, value in standard_data.items():
            # Skip None values
            if value is None:
                continue

            # Skip empty strings
            if isinstance(value, str) and not value.strip():
                continue

            # Get CRM-specific field name
            crm_field = field_mapping.get(standard_field)

            if crm_field:
                # Apply any field-specific transformations
                transformed_value = self._transform_field_value(
                    standard_field,
                    value,
                    crm_type
                )
                mapped_data[crm_field] = transformed_value
            else:
                # Field not in mapping - log warning but don't fail
                logger.warning(
                    f"Standard field '{standard_field}' has no mapping for {crm_type}. "
                    f"Field will be ignored."
                )

        return mapped_data

    def _transform_field_value(
        self,
        field_name: str,
        value: Any,
        crm_type: str
    ) -> Any:
        """
        Apply field-specific value transformations if needed.

        Args:
            field_name: Standard field name
            value: Field value
            crm_type: Target CRM type

        Returns:
            Transformed value
        """
        # Email normalization
        if field_name == "email" and isinstance(value, str):
            return value.lower().strip()

        # Phone normalization
        if field_name == "phone" and isinstance(value, str):
            # Some CRMs prefer specific phone formats
            if crm_type in ["salesforce", "zoho"]:
                # Remove formatting for these CRMs
                return value.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")

        # Country code normalization
        if field_name == "country" and isinstance(value, str):
            return value.upper().strip()

        # Default: return as-is
        return value

    # ========================================================================
    # CRM-SPECIFIC STRUCTURE TRANSFORMATIONS
    # ========================================================================

    def _apply_crm_structure(
        self,
        mapped_data: Dict[str, Any],
        custom_properties: Dict[str, Any],
        crm_type: str
    ) -> Dict[str, Any]:
        """
        Apply CRM-specific data structure transformations.

        Different CRMs expect data in different formats (flat, nested, wrapped, etc.)

        Args:
            mapped_data: Data with CRM-specific field names
            custom_properties: Custom properties to include
            crm_type: Target CRM type

        Returns:
            Structured data ready for CRM API
        """
        transformer_config = self.transformers.get(crm_type, {})
        structure_type = transformer_config.get("structure", "flat")

        # ====================================================================
        # KLAVIYO: {attributes: {...}, properties: {...}}
        # ====================================================================
        if structure_type == "attributes_properties":
            result = {"attributes": mapped_data}

            # Add custom properties to separate properties object
            if custom_properties:
                result["properties"] = custom_properties

            return result

        # ====================================================================
        # HUBSPOT: {properties: {field: {value: ...}}}
        # ====================================================================
        elif structure_type == "properties":
            properties = {}

            # Wrap each field in value object
            for field, value in mapped_data.items():
                properties[field] = {"value": value}

            # Add custom properties
            if custom_properties:
                for field, value in custom_properties.items():
                    properties[field] = {"value": value}

            return {"properties": properties}

        # ====================================================================
        # MAILCHIMP: merge_fields structure
        # ====================================================================
        elif structure_type == "merge_fields":
            result = {
                "email_address": mapped_data.pop("email_address", ""),
                "merge_fields": {}
            }

            # Move fields to merge_fields
            for field, value in mapped_data.items():
                result["merge_fields"][field] = value

            # Handle nested address if present
            if transformer_config.get("nested_address"):
                address_fields = {}
                for key in ["addr1", "addr2", "city", "state", "zip", "country"]:
                    address_key = f"ADDRESS.{key}"
                    if address_key in result["merge_fields"]:
                        address_fields[key] = result["merge_fields"].pop(address_key)

                if address_fields:
                    result["merge_fields"]["ADDRESS"] = address_fields

            return result

        # ====================================================================
        # SALESFORCE: Flat with custom field suffix
        # ====================================================================
        elif structure_type == "flat" and transformer_config.get("prefix_custom_fields"):
            result = mapped_data.copy()

            # Add custom properties with __c suffix
            if custom_properties:
                suffix = transformer_config.get("custom_field_suffix", "__c")
                for field, value in custom_properties.items():
                    # Convert field name to Salesforce API format
                    sf_field_name = f"{field}{suffix}"
                    result[sf_field_name] = value

            return result

        # ====================================================================
        # ACTIVECAMPAIGN: fieldValues array for custom fields
        # ====================================================================
        elif crm_type == "activecampaign":
            result = mapped_data.copy()

            # Convert custom properties to fieldValues array
            if custom_properties:
                field_values = []
                for field, value in custom_properties.items():
                    field_values.append({
                        "field": field,
                        "value": value
                    })
                result["fieldValues"] = field_values

            return result

        # ====================================================================
        # INTERCOM: custom_attributes for custom fields
        # ====================================================================
        elif crm_type == "intercom":
            result = mapped_data.copy()

            # Add custom properties to custom_attributes
            if custom_properties:
                result["custom_attributes"] = custom_properties

            return result

        # ====================================================================
        # DEFAULT: Flat structure (Creatio, Zoho, Pipedrive, etc.)
        # ====================================================================
        else:
            result = mapped_data.copy()

            # Add custom properties at root level
            if custom_properties:
                result.update(custom_properties)

            return result

    # ========================================================================
    # EVENT TRANSFORMATION
    # ========================================================================

    def transform_event(
        self,
        standard_event: Dict[str, Any],
        contact_identifier: Dict[str, str],
        crm_type: str
    ) -> Dict[str, Any]:
        """
        Transform standard event format to CRM-specific format.

        Args:
            standard_event: Event data in standard schema
            contact_identifier: Contact identifier (email, id, etc.)
            crm_type: Target CRM type

        Returns:
            CRM-specific formatted event data
        """
        if not is_crm_supported(crm_type):
            raise FieldMappingError(f"CRM type '{crm_type}' is not supported")

        # For now, return a basic transformation
        # TODO: Add CRM-specific event transformations
        event_name = standard_event.get("event_name", "Custom Event")
        properties = standard_event.get("properties", {})
        timestamp = standard_event.get("timestamp")
        value = standard_event.get("value")

        result = {
            "event_name": event_name,
            "contact": contact_identifier,
            "properties": properties,
        }

        if timestamp:
            result["timestamp"] = timestamp
        if value is not None:
            result["value"] = value

        return result

    # ========================================================================
    # VALIDATION
    # ========================================================================

    def validate_contact_data(
        self,
        contact_data: Dict[str, Any],
        crm_type: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate that contact data meets CRM requirements.

        Args:
            contact_data: Standard contact data
            crm_type: Target CRM type

        Returns:
            (is_valid, error_message)
        """
        # Check if CRM is supported
        if not is_crm_supported(crm_type):
            return False, f"CRM type '{crm_type}' is not supported"

        # Check required fields
        required = get_crm_required_fields(crm_type)
        for field in required:
            if field not in contact_data or not contact_data[field]:
                return False, f"Required field '{field}' is missing or empty for {crm_type}"

        # Email validation (required by all CRMs)
        email = contact_data.get("email")
        if not email or not isinstance(email, str):
            return False, "Email is required and must be a string"

        if "@" not in email:
            return False, "Email must be a valid email address"

        return True, None

    # ========================================================================
    # UTILITY METHODS
    # ========================================================================

    def get_supported_fields(self, crm_type: str) -> List[str]:
        """Get list of standard fields supported for a CRM type"""
        return get_crm_supported_fields(crm_type)

    def get_required_fields(self, crm_type: str) -> List[str]:
        """Get list of required fields for a CRM type"""
        return get_crm_required_fields(crm_type)

    def get_supported_crms(self) -> List[str]:
        """Get list of all supported CRM types"""
        return get_supported_crms()

    def get_field_mapping(self, crm_type: str) -> Dict[str, str]:
        """Get complete field mapping for a CRM type"""
        if crm_type not in self.field_mappings:
            raise FieldMappingError(f"CRM type '{crm_type}' is not supported")
        return self.field_mappings[crm_type].copy()


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

field_mapping_service = FieldMappingService()
