"""
Field Mapping Configurations for CRM Integrations

This file contains predefined field mappings from standard contact schema
to CRM-specific field names. This is the SINGLE SOURCE OF TRUTH for all
field transformations.

Benefits:
- Centralized control of all field mappings
- Easy to update when CRM APIs change
- No client-side CRM knowledge required
- Consistent mappings across all integrations
"""

from typing import Dict, Any, Literal


# ============================================================================
# STANDARD FIELD TO CRM-SPECIFIC FIELD MAPPINGS
# ============================================================================

FIELD_MAPPINGS: Dict[str, Dict[str, str]] = {
    # ========================================
    # KLAVIYO FIELD MAPPINGS
    # ========================================
    "klaviyo": {
        # Personal information
        "email": "email",
        "first_name": "first_name",
        "last_name": "last_name",
        "phone": "phone_number",  # Klaviyo uses phone_number

        # Company information
        "company": "organization",  # Klaviyo uses organization
        "job_title": "title",

        # Address fields
        "street_address": "address1",
        "street_address_2": "address2",
        "city": "city",
        "state": "region",  # Klaviyo uses region
        "postal_code": "zip",  # Klaviyo uses zip
        "country": "country",

        # Additional fields
        "timezone": "timezone",
        # Custom properties go to separate properties object
    },

    # ========================================
    # SALESFORCE FIELD MAPPINGS
    # ========================================
    "salesforce": {
        # Personal information (Contact/Lead object)
        "email": "Email",
        "first_name": "FirstName",
        "last_name": "LastName",
        "phone": "Phone",

        # Company information
        "company": "Company",  # For Lead object
        "job_title": "Title",
        "department": "Department",

        # Address fields (Mailing Address)
        "street_address": "MailingStreet",
        "city": "MailingCity",
        "state": "MailingState",
        "postal_code": "MailingPostalCode",
        "country": "MailingCountry",

        # Additional fields
        "website": "Website",
        # Custom fields will have __c suffix added automatically
    },

    # ========================================
    # CREATIO FIELD MAPPINGS
    # ========================================
    "creatio": {
        # Personal information
        "email": "Email",
        "first_name": "GivenName",
        "last_name": "Surname",
        "phone": "MobilePhone",

        # Company information
        "company": "Account",
        "job_title": "JobTitle",
        "department": "Department",

        # Address fields
        "street_address": "Address",
        "city": "City",
        "state": "Region",
        "postal_code": "Zip",
        "country": "Country",

        # Additional fields
        "website": "Web",
    },

    # ========================================
    # HUBSPOT FIELD MAPPINGS
    # ========================================
    "hubspot": {
        # Personal information
        "email": "email",
        "first_name": "firstname",
        "last_name": "lastname",
        "phone": "phone",

        # Company information
        "company": "company",
        "job_title": "jobtitle",

        # Address fields
        "street_address": "address",
        "city": "city",
        "state": "state",
        "postal_code": "zip",
        "country": "country",

        # Additional fields
        "website": "website",
        # Custom properties are handled as regular fields in HubSpot
    },

    # ========================================
    # MAILCHIMP FIELD MAPPINGS
    # ========================================
    "mailchimp": {
        # Personal information
        "email": "email_address",
        "first_name": "FNAME",
        "last_name": "LNAME",
        "phone": "PHONE",

        # Company information
        "company": "COMPANY",

        # Address fields
        "street_address": "ADDRESS.addr1",
        "street_address_2": "ADDRESS.addr2",
        "city": "ADDRESS.city",
        "state": "ADDRESS.state",
        "postal_code": "ADDRESS.zip",
        "country": "ADDRESS.country",
    },

    # ========================================
    # ACTIVECAMPAIGN FIELD MAPPINGS
    # ========================================
    "activecampaign": {
        # Personal information
        "email": "email",
        "first_name": "firstName",
        "last_name": "lastName",
        "phone": "phone",

        # Company information (via Account object)
        "company": "account",
        "job_title": "jobTitle",

        # Custom fields use fieldValues array
    },

    # ========================================
    # SENDINBLUE (Brevo) FIELD MAPPINGS
    # ========================================
    "sendinblue": {
        # Personal information
        "email": "email",
        "first_name": "FIRSTNAME",
        "last_name": "LASTNAME",
        "phone": "SMS",

        # Company information
        "company": "COMPANY",

        # Custom attributes are handled separately
    },

    # ========================================
    # ZOHO CRM FIELD MAPPINGS
    # ========================================
    "zoho": {
        # Personal information
        "email": "Email",
        "first_name": "First_Name",
        "last_name": "Last_Name",
        "phone": "Phone",

        # Company information
        "company": "Company",
        "job_title": "Designation",
        "department": "Department",

        # Address fields
        "street_address": "Mailing_Street",
        "city": "Mailing_City",
        "state": "Mailing_State",
        "postal_code": "Mailing_Zip",
        "country": "Mailing_Country",

        # Additional fields
        "website": "Website",
    },

    # ========================================
    # PIPEDRIVE FIELD MAPPINGS
    # ========================================
    "pipedrive": {
        # Personal information
        "email": "email",
        "first_name": "first_name",
        "last_name": "last_name",
        "phone": "phone",

        # Company information (via Organization object)
        "company": "org_name",

        # Custom fields use field keys
    },

    # ========================================
    # INTERCOM FIELD MAPPINGS
    # ========================================
    "intercom": {
        # Personal information
        "email": "email",
        "first_name": "name",  # Intercom uses single name field
        "phone": "phone",

        # Company information (via Company object)
        "company": "company.name",

        # Custom attributes
        "job_title": "custom_attributes.job_title",
        "city": "custom_attributes.city",
        "country": "custom_attributes.country",
    },

    # ========================================
    # CUSTOMER.IO FIELD MAPPINGS
    # ========================================
    "customerio": {
        # Personal information (all go to attributes)
        "email": "email",
        "first_name": "first_name",
        "last_name": "last_name",
        "phone": "phone",

        # Company information
        "company": "company",
        "job_title": "job_title",

        # All fields go to attributes object
    },
}


# ============================================================================
# CRM-SPECIFIC STRUCTURE TRANSFORMERS
# ============================================================================

StructureType = Literal[
    "flat",                      # Flat object: {field: value, ...}
    "attributes_properties",     # Klaviyo style: {attributes: {...}, properties: {...}}
    "properties",                # HubSpot style: {properties: {field: {value: ...}}}
    "nested_address",            # Mailchimp style: nested address object
    "merge_fields",              # Mailchimp style: merge_fields object
]

CustomFieldLocation = Literal[
    "root",           # Add custom fields to root level
    "properties",     # Add to separate properties object
    "custom_fields",  # Add to custom_fields array/object
    "attributes",     # Add to attributes object
]

CRM_TRANSFORMERS: Dict[str, Dict[str, Any]] = {
    "klaviyo": {
        "structure": "attributes_properties",
        "custom_field_location": "properties",
        "api_wrapper": {
            "root": "data",
            "type": "profile",
        },
        "description": "Klaviyo uses {data: {type: 'profile', attributes: {...}, properties: {...}}}",
    },

    "salesforce": {
        "structure": "flat",
        "custom_field_location": "root",
        "prefix_custom_fields": True,
        "custom_field_suffix": "__c",
        "description": "Salesforce uses flat object with custom fields having __c suffix",
    },

    "creatio": {
        "structure": "flat",
        "custom_field_location": "root",
        "description": "Creatio uses flat object structure",
    },

    "hubspot": {
        "structure": "properties",
        "custom_field_location": "properties",
        "description": "HubSpot uses {properties: {field: {value: ...}}} structure",
    },

    "mailchimp": {
        "structure": "merge_fields",
        "custom_field_location": "merge_fields",
        "nested_address": True,
        "description": "Mailchimp uses merge_fields for custom fields and nested address",
    },

    "activecampaign": {
        "structure": "flat",
        "custom_field_location": "custom_fields",
        "description": "ActiveCampaign uses fieldValues array for custom fields",
    },

    "sendinblue": {
        "structure": "flat",
        "custom_field_location": "attributes",
        "description": "SendinBlue uses attributes object for all fields",
    },

    "zoho": {
        "structure": "flat",
        "custom_field_location": "root",
        "description": "Zoho CRM uses flat object structure",
    },

    "pipedrive": {
        "structure": "flat",
        "custom_field_location": "root",
        "description": "Pipedrive uses flat object with custom field keys",
    },

    "intercom": {
        "structure": "flat",
        "custom_field_location": "attributes",
        "nested_company": True,
        "description": "Intercom uses custom_attributes for custom fields",
    },

    "customerio": {
        "structure": "flat",
        "custom_field_location": "attributes",
        "description": "Customer.io puts all fields in attributes",
    },
}


# ============================================================================
# FIELD TYPE MAPPINGS (for validation and conversion)
# ============================================================================

FIELD_TYPES: Dict[str, str] = {
    # Personal information
    "email": "email",
    "first_name": "string",
    "last_name": "string",
    "phone": "phone",

    # Company information
    "company": "string",
    "job_title": "string",
    "department": "string",

    # Address fields
    "street_address": "string",
    "street_address_2": "string",
    "city": "string",
    "state": "string",
    "postal_code": "string",
    "country": "string",

    # Additional fields
    "website": "url",
    "timezone": "string",
    "language": "string",
}


# ============================================================================
# REQUIRED FIELDS BY CRM
# ============================================================================

REQUIRED_FIELDS: Dict[str, list[str]] = {
    "klaviyo": ["email"],
    "salesforce": ["email", "last_name"],  # Lead/Contact requires LastName
    "creatio": ["email"],
    "hubspot": ["email"],
    "mailchimp": ["email"],
    "activecampaign": ["email"],
    "sendinblue": ["email"],
    "zoho": ["email", "last_name"],
    "pipedrive": ["email"],
    "intercom": ["email"],
    "customerio": ["email"],
}


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_supported_crms() -> list[str]:
    """Get list of all supported CRM types"""
    return list(FIELD_MAPPINGS.keys())


def get_crm_required_fields(crm_type: str) -> list[str]:
    """Get required fields for a specific CRM"""
    return REQUIRED_FIELDS.get(crm_type, ["email"])


def get_crm_supported_fields(crm_type: str) -> list[str]:
    """Get list of standard fields supported by a CRM"""
    if crm_type not in FIELD_MAPPINGS:
        return []
    return list(FIELD_MAPPINGS[crm_type].keys())


def is_crm_supported(crm_type: str) -> bool:
    """Check if CRM type is supported"""
    return crm_type in FIELD_MAPPINGS
