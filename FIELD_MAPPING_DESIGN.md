# Backend-Driven Field Mapping Design

## Problem Statement

Current implementation requires clients to provide field mappings during `/crm/connect`, which:
- Puts CRM knowledge burden on clients
- Creates inconsistent mappings across integrations
- Makes maintenance difficult when CRMs change APIs
- Poses security and data quality risks

## Proposed Solution: Backend-Controlled Field Mapping

### Architecture Overview

```
Standard Schema (Backend) → Field Mapping Service → CRM-Specific Format
```

---

## Design Option 1: Predefined Mapping Templates (RECOMMENDED)

### 1. Define Standard Contact Schema

Create a universal contact schema that all clients use:

```python
# app/schemas/standard_contact.py

class StandardContactSchema:
    """
    Universal contact schema - clients ONLY send this format.
    Backend handles all CRM-specific transformations.
    """
    # Required fields
    email: str

    # Optional standard fields
    first_name: Optional[str]
    last_name: Optional[str]
    phone: Optional[str]
    company: Optional[str]

    # Address fields
    street_address: Optional[str]
    city: Optional[str]
    state: Optional[str]
    postal_code: Optional[str]
    country: Optional[str]

    # Business fields
    job_title: Optional[str]
    department: Optional[str]

    # Custom properties (flexible)
    custom_properties: Optional[Dict[str, Any]]
```

### 2. Backend Mapping Configuration

Store CRM-specific mappings in backend configuration:

```python
# app/services/field_mappings.py

FIELD_MAPPINGS = {
    "klaviyo": {
        "email": "email",
        "first_name": "first_name",
        "last_name": "last_name",
        "phone": "phone_number",          # Klaviyo uses phone_number
        "company": "organization",         # Klaviyo uses organization
        "street_address": "address1",
        "city": "city",
        "state": "region",
        "postal_code": "zip",
        "country": "country",
        "job_title": "title",
        # Custom properties go to properties object
    },

    "salesforce": {
        "email": "Email",
        "first_name": "FirstName",
        "last_name": "LastName",
        "phone": "Phone",
        "company": "Company",
        "street_address": "MailingStreet",
        "city": "MailingCity",
        "state": "MailingState",
        "postal_code": "MailingPostalCode",
        "country": "MailingCountry",
        "job_title": "Title",
        "department": "Department",
    },

    "creatio": {
        "email": "Email",
        "first_name": "GivenName",
        "last_name": "Surname",
        "phone": "MobilePhone",
        "company": "Account",
        "job_title": "JobTitle",
    },

    "hubspot": {
        "email": "email",
        "first_name": "firstname",
        "last_name": "lastname",
        "phone": "phone",
        "company": "company",
        "street_address": "address",
        "city": "city",
        "state": "state",
        "postal_code": "zip",
        "country": "country",
        "job_title": "jobtitle",
    }
}

# CRM-specific structure transformers
CRM_TRANSFORMERS = {
    "klaviyo": {
        "structure": "attributes_properties",  # {"attributes": {...}, "properties": {...}}
        "custom_field_location": "properties"
    },
    "salesforce": {
        "structure": "flat",  # Flat object
        "custom_field_location": "root",
        "prefix_custom_fields": True,  # Custom__c suffix
    },
    "hubspot": {
        "structure": "properties",  # {"properties": {...}}
        "custom_field_location": "properties"
    }
}
```

### 3. New API Flow

#### 3.1 Connect CRM (Simplified)

```http
POST /crm/connect

{
  "crm_type": "klaviyo",
  "credentials": {
    "api_key": "pk_..."
  },
  "settings": {
    "enabled_events": ["order_created"],
    "sync_frequency": "real-time"
  }
}
```

**NO field_mapping required!** Backend handles everything.

#### 3.2 Sync Contact (Standard Schema)

```http
POST /crm/sync/contact

{
  "email": "john@example.com",
  "first_name": "John",
  "last_name": "Doe",
  "phone": "+1234567890",
  "company": "Acme Corp",
  "job_title": "CEO",
  "custom_properties": {
    "lead_score": 85,
    "source": "website"
  }
}
```

Client sends **standard format only** - backend maps to CRM-specific format.

### 4. Backend Transformation Service

```python
# app/services/field_mapper.py

class FieldMappingService:
    """Backend service for transforming standard contact data to CRM-specific format"""

    def __init__(self):
        self.mappings = FIELD_MAPPINGS
        self.transformers = CRM_TRANSFORMERS

    def transform_contact(
        self,
        standard_contact: Dict[str, Any],
        crm_type: str
    ) -> Dict[str, Any]:
        """
        Transform standard contact format to CRM-specific format.

        Args:
            standard_contact: Contact data in standard schema
            crm_type: Target CRM type

        Returns:
            CRM-specific formatted data
        """
        if crm_type not in self.mappings:
            raise ValueError(f"No mapping defined for CRM type: {crm_type}")

        field_mapping = self.mappings[crm_type]
        transformer_config = self.transformers.get(crm_type, {})

        # Step 1: Map standard fields to CRM fields
        mapped_data = {}
        custom_properties = standard_contact.pop("custom_properties", {})

        for standard_field, value in standard_contact.items():
            if value is None:
                continue

            crm_field = field_mapping.get(standard_field)
            if crm_field:
                mapped_data[crm_field] = value

        # Step 2: Handle custom properties
        if custom_properties:
            custom_location = transformer_config.get("custom_field_location", "root")

            if custom_location == "properties":
                # Separate properties object (Klaviyo, HubSpot)
                pass  # Handle in structure transformation
            elif custom_location == "root":
                # Add to root with prefix (Salesforce)
                if transformer_config.get("prefix_custom_fields"):
                    for key, value in custom_properties.items():
                        mapped_data[f"{key}__c"] = value
                else:
                    mapped_data.update(custom_properties)

        # Step 3: Apply CRM-specific structure
        structure_type = transformer_config.get("structure", "flat")

        if structure_type == "attributes_properties":
            # Klaviyo format
            result = {"attributes": mapped_data}
            if custom_properties:
                result["properties"] = custom_properties
            return result

        elif structure_type == "properties":
            # HubSpot format
            properties = {}
            for key, value in mapped_data.items():
                properties[key] = {"value": value}
            if custom_properties:
                for key, value in custom_properties.items():
                    properties[key] = {"value": value}
            return {"properties": properties}

        elif structure_type == "flat":
            # Salesforce, Creatio
            return mapped_data

        return mapped_data

    def get_supported_fields(self, crm_type: str) -> List[str]:
        """Get list of standard fields supported for a CRM type"""
        if crm_type not in self.mappings:
            raise ValueError(f"No mapping defined for CRM type: {crm_type}")
        return list(self.mappings[crm_type].keys())

    def validate_contact_data(
        self,
        contact_data: Dict[str, Any],
        crm_type: str
    ) -> tuple[bool, Optional[str]]:
        """
        Validate that contact data can be mapped to CRM.

        Returns:
            (is_valid, error_message)
        """
        # Required field check
        if "email" not in contact_data or not contact_data["email"]:
            return False, "Email is required"

        # Check if CRM type is supported
        if crm_type not in self.mappings:
            return False, f"CRM type {crm_type} not supported"

        # Validate standard fields
        supported_fields = set(self.mappings[crm_type].keys())
        supported_fields.add("custom_properties")

        for field in contact_data.keys():
            if field not in supported_fields:
                return False, f"Field '{field}' is not in standard schema"

        return True, None

# Singleton
field_mapping_service = FieldMappingService()
```

### 5. Updated Sync Endpoint

```python
# app/routers/crm.py - Updated sync_contact endpoint

from ..services.field_mapper import field_mapping_service

@router.post("/sync/contact")
async def sync_contact(
    contact_data: StandardContactData,  # ← Use standard schema
    merchant_id: UUID = Depends(get_merchant_id),
    crm_types: Optional[List[str]] = None,
    conn: Connection = Depends(get_conn)
):
    """
    Sync contact data to CRM using STANDARD contact schema.

    Backend automatically maps to CRM-specific format.
    """
    try:
        # Get active integrations
        integrations = await _get_active_integrations(conn, merchant_id, crm_types)

        if not integrations:
            return error_response(
                message="No active CRM integrations found",
                error_code=ErrorCodes.CRM_INTEGRATION_NOT_FOUND
            ), 404

        results = {}
        contact_dict = contact_data.dict(exclude_none=True)

        for integration in integrations:
            crm_type = integration["crm_type"]
            credentials = integration["credentials"]

            # ✅ BACKEND TRANSFORMS DATA - No client involvement
            try:
                # Validate contact data
                is_valid, error_msg = field_mapping_service.validate_contact_data(
                    contact_dict,
                    crm_type
                )
                if not is_valid:
                    results[crm_type] = {"success": False, "error": error_msg}
                    continue

                # Transform to CRM-specific format
                transformed_data = field_mapping_service.transform_contact(
                    contact_dict.copy(),  # Don't mutate original
                    crm_type
                )

                # Send to CRM
                result = await crm_manager.create_or_update_contact(
                    CRMType(crm_type),
                    credentials,
                    transformed_data
                )

                results[crm_type] = {"success": True, "data": result}

            except Exception as e:
                results[crm_type] = {"success": False, "error": str(e)}

        return success_response(
            message="Contact sync completed",
            data={"results": results}
        )

    except Exception as e:
        logger.error(f"Error syncing contact: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to sync contact")
```

---

## Design Option 2: Database-Driven Field Mapping (Advanced)

For enterprise clients who need custom field mappings per merchant:

### 1. Database Schema

```sql
-- Table for merchant-specific custom field mappings
CREATE TABLE crm.custom_field_mappings (
  mapping_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  merchant_id UUID NOT NULL,
  standard_field TEXT NOT NULL,      -- Standard schema field name
  custom_field TEXT NOT NULL,        -- Merchant's custom field name
  data_type TEXT DEFAULT 'string',   -- string, number, boolean, date
  is_required BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  UNIQUE(merchant_id, custom_field)
);

-- Example data:
-- merchant_id | standard_field | custom_field
-- -----------|----------------|---------------
-- 550e8400...| first_name     | customer_fname
-- 550e8400...| phone          | mobile_number
-- 550e8400...| company        | organization_name
```

### 2. API for Managing Custom Mappings

```http
# Create custom field mapping
POST /crm/field-mappings

{
  "mappings": [
    {
      "standard_field": "first_name",
      "custom_field": "customer_fname"
    },
    {
      "standard_field": "phone",
      "custom_field": "mobile_number"
    }
  ]
}

# Get merchant's custom mappings
GET /crm/field-mappings
```

### 3. Three-Layer Mapping

```
Client Custom Fields → Standard Schema → CRM-Specific Format
(customer_fname)    →  (first_name)    → (FirstName for Salesforce)
                                         (first_name for Klaviyo)
```

---

## Benefits of Backend-Driven Approach

### ✅ **Centralized Control**
- Single source of truth for field mappings
- Easy to update when CRMs change APIs
- Consistent mappings across all clients

### ✅ **Security**
- No client manipulation of field mappings
- Validated transformations only
- Audit trail of what data is sent where

### ✅ **Maintainability**
- Update one place to fix all integrations
- Version control for mapping changes
- Easy to add new CRMs

### ✅ **Client Simplicity**
- Clients use standard schema only
- No CRM-specific knowledge needed
- One API contract for all CRMs

### ✅ **Data Quality**
- Validation at backend level
- Type checking and conversion
- Consistent data format

### ✅ **Flexibility**
- Support merchant-specific custom fields (Option 2)
- Easy to add field transformations (e.g., phone formatting)
- Can add field-level encryption if needed

---

## Migration Strategy

### Phase 1: Add Backend Mapping Service
1. Create `field_mappings.py` with predefined mappings
2. Create `FieldMappingService` class
3. Add validation logic

### Phase 2: Update API Models
1. Create `StandardContactData` Pydantic model
2. Update `/sync/contact` endpoint to use standard schema
3. Keep backward compatibility with old field_mapping

### Phase 3: Deprecate Client-Side Mapping
1. Mark `field_mapping` in settings as deprecated
2. Add migration endpoint to help clients transition
3. Eventually remove support for client-provided mappings

### Phase 4: Add Custom Field Mapping (Optional)
1. Add `custom_field_mappings` table
2. Create field mapping management endpoints
3. Update transformation service to support custom mappings

---

## Recommendation

**Use Option 1 (Predefined Templates)** for most use cases:
- Simpler to implement
- Covers 95% of use cases
- Easier to maintain
- Better performance

**Add Option 2 (Database-Driven)** only if you have:
- Enterprise clients with highly custom field names
- Different departments using different field conventions
- Need for merchant-level customization

---

## Example Usage (After Implementation)

### Before (Current - BAD):
```http
POST /crm/connect
{
  "crm_type": "klaviyo",
  "credentials": {...},
  "settings": {
    "field_mapping": {  ← Client provides this
      "customer_name": "first_name",
      "mobile": "phone"
    }
  }
}

POST /crm/sync/contact
{
  "email": "john@example.com",
  "customer_name": "John",  ← Custom field names
  "mobile": "+123..."
}
```

### After (Proposed - GOOD):
```http
POST /crm/connect
{
  "crm_type": "klaviyo",
  "credentials": {...},
  "settings": {
    "enabled_events": ["order_created"]
    // ✅ No field_mapping needed!
  }
}

POST /crm/sync/contact
{
  "email": "john@example.com",
  "first_name": "John",     ← Standard field names
  "phone": "+123..."
}
```

Backend automatically:
1. Validates standard schema
2. Maps to Klaviyo format: `phone` → `phone_number`
3. Wraps in Klaviyo structure: `{"attributes": {...}}`
4. Sends to Klaviyo API

---

This approach puts the complexity where it belongs - in the backend - and keeps clients simple and consistent!
