# Backend Field Mapping - Usage Examples

## 🎯 Overview

The CRM microservice now uses **backend-controlled field mapping**. Clients send data in a **standard schema**, and the backend automatically transforms it to CRM-specific formats.

**Benefits:**
- ✅ ONE schema for ALL CRMs
- ✅ No CRM-specific knowledge needed
- ✅ Backend handles all transformations
- ✅ Easy to maintain and update
- ✅ Centralized control

---

## 📋 Table of Contents

1. [Quick Start](#quick-start)
2. [API Endpoints](#api-endpoints)
3. [Standard Contact Schema](#standard-contact-schema)
4. [Examples by CRM Type](#examples-by-crm-type)
5. [Migration Guide](#migration-guide)
6. [Field Mapping Reference](#field-mapping-reference)

---

## 🚀 Quick Start

### Step 1: Connect CRM (No field_mapping needed!)

```http
POST /crm/connect
X-Merchant-Id: 550e8400-e29b-41d4-a716-446655440000
Content-Type: application/json

{
  "crm_type": "klaviyo",
  "credentials": {
    "api_key": "pk_1234567890abcdef..."
  },
  "settings": {
    "enabled_events": ["order_created", "cart_abandoned"]
  }
}
```

**✅ No `field_mapping` needed!** Backend handles everything.

### Step 2: Sync Contact (Standard Schema)

```http
POST /crm/sync/contact
X-Merchant-Id: 550e8400-e29b-41d4-a716-446655440000
Content-Type: application/json

{
  "email": "john.doe@example.com",
  "first_name": "John",
  "last_name": "Doe",
  "phone": "+1234567890",
  "company": "Acme Corp",
  "job_title": "CEO",
  "city": "New York",
  "state": "NY",
  "country": "US",
  "custom_properties": {
    "lead_score": 85,
    "source": "website",
    "tags": ["enterprise", "hot_lead"]
  }
}
```

**Backend automatically:**
1. Validates the data
2. Maps to Klaviyo format: `phone` → `phone_number`, `company` → `organization`
3. Wraps in Klaviyo structure: `{attributes: {...}, properties: {...}}`
4. Sends to Klaviyo API

**Done!** 🎉

---

## 📡 API Endpoints

### 1. Connect CRM

```http
POST /crm/connect
```

**Changes:**
- ❌ `field_mapping` in settings is **deprecated** and ignored
- ✅ Just provide credentials and enabled_events
- ✅ Backend handles field transformations

### 2. Sync Contact (New - Standard Schema)

```http
POST /crm/sync/contact
```

**Uses:** `StandardContactData` schema
**Backend:** Automatically transforms to CRM-specific format

### 3. Sync Contact Legacy (Backward Compatible)

```http
POST /crm/sync/contact/legacy
```

**Uses:** Old `ContactData` schema
**Deprecated:** Migrate to `/sync/contact`

### 4. Get Field Mappings (New - Helper)

```http
GET /crm/field-mappings/{crm_type}
```

**Returns:**
- Supported standard fields
- Required fields
- CRM-specific field names
- Example contact data

**Example:**
```http
GET /crm/field-mappings/klaviyo
X-Merchant-Id: 550e8400-e29b-41d4-a716-446655440000
```

**Response:**
```json
{
  "success": true,
  "data": {
    "crm_type": "klaviyo",
    "supported_fields": ["email", "first_name", "last_name", "phone", "company", ...],
    "required_fields": ["email"],
    "field_mapping": {
      "phone": "phone_number",
      "company": "organization",
      "state": "region",
      "postal_code": "zip"
    },
    "example_standard_contact": { ... }
  }
}
```

### 5. List All Field Mappings (New - Helper)

```http
GET /crm/field-mappings
X-Merchant-Id: 550e8400-e29b-41d4-a716-446655440000
```

**Returns:** All supported CRMs and their capabilities

---

## 📝 Standard Contact Schema

### Required Fields

- ✅ **email** (required by all CRMs)

### Optional Standard Fields

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `first_name` | string | First name | "John" |
| `last_name` | string | Last name | "Doe" |
| `phone` | string | Phone (E.164 format) | "+1234567890" |
| `company` | string | Company name | "Acme Corp" |
| `job_title` | string | Job title | "CEO" |
| `department` | string | Department | "Engineering" |
| `street_address` | string | Street address line 1 | "123 Main St" |
| `street_address_2` | string | Street address line 2 | "Apt 4B" |
| `city` | string | City | "New York" |
| `state` | string | State/Province | "NY" |
| `postal_code` | string | ZIP/Postal code | "10001" |
| `country` | string | Country (ISO code) | "US" |
| `website` | string | Website URL | "https://example.com" |
| `timezone` | string | Timezone (IANA) | "America/New_York" |
| `language` | string | Language (ISO code) | "en" |
| `custom_properties` | object | Custom data | `{"lead_score": 85}` |

### Full Example

```json
{
  "email": "john.doe@example.com",
  "first_name": "John",
  "last_name": "Doe",
  "phone": "+1234567890",
  "company": "Acme Corp",
  "job_title": "Chief Executive Officer",
  "department": "Executive",
  "street_address": "123 Main Street",
  "street_address_2": "Suite 400",
  "city": "New York",
  "state": "NY",
  "postal_code": "10001",
  "country": "US",
  "website": "https://acme.example.com",
  "timezone": "America/New_York",
  "language": "en",
  "custom_properties": {
    "lead_score": 85,
    "source": "website",
    "campaign": "enterprise-2025",
    "tags": ["enterprise", "hot_lead", "decision_maker"],
    "lifetime_value": 50000,
    "last_activity": "2025-12-18T10:30:00Z"
  }
}
```

---

## 🎬 Examples by CRM Type

### Example 1: Klaviyo

**Input (Standard Schema):**
```json
{
  "email": "jane@example.com",
  "first_name": "Jane",
  "last_name": "Smith",
  "phone": "+19876543210",
  "company": "Tech Startup Inc",
  "custom_properties": {
    "lead_score": 92,
    "source": "referral"
  }
}
```

**Backend Transformation:**
```json
{
  "attributes": {
    "email": "jane@example.com",
    "first_name": "Jane",
    "last_name": "Smith",
    "phone_number": "+19876543210",
    "organization": "Tech Startup Inc"
  },
  "properties": {
    "lead_score": 92,
    "source": "referral"
  }
}
```

**Field Mapping Applied:**
- `phone` → `phone_number` ✅
- `company` → `organization` ✅
- Wrapped in `attributes` and `properties` ✅

---

### Example 2: Salesforce

**Input (Standard Schema):**
```json
{
  "email": "bob@example.com",
  "first_name": "Bob",
  "last_name": "Johnson",
  "phone": "+15551234567",
  "company": "Enterprise Corp",
  "job_title": "VP of Sales",
  "street_address": "456 Oak Avenue",
  "city": "San Francisco",
  "state": "CA",
  "postal_code": "94102",
  "country": "US",
  "custom_properties": {
    "territory": "West Coast",
    "account_type": "Enterprise"
  }
}
```

**Backend Transformation:**
```json
{
  "Email": "bob@example.com",
  "FirstName": "Bob",
  "LastName": "Johnson",
  "Phone": "+15551234567",
  "Company": "Enterprise Corp",
  "Title": "VP of Sales",
  "MailingStreet": "456 Oak Avenue",
  "MailingCity": "San Francisco",
  "MailingState": "CA",
  "MailingPostalCode": "94102",
  "MailingCountry": "US",
  "territory__c": "West Coast",
  "account_type__c": "Enterprise"
}
```

**Field Mapping Applied:**
- All fields capitalized (Salesforce convention) ✅
- Address fields prefixed with `Mailing` ✅
- Custom properties get `__c` suffix ✅

---

### Example 3: HubSpot

**Input (Standard Schema):**
```json
{
  "email": "alice@example.com",
  "first_name": "Alice",
  "last_name": "Williams",
  "phone": "+14155551234",
  "company": "Marketing Agency",
  "job_title": "Marketing Director"
}
```

**Backend Transformation:**
```json
{
  "properties": {
    "email": {"value": "alice@example.com"},
    "firstname": {"value": "Alice"},
    "lastname": {"value": "Williams"},
    "phone": {"value": "+14155551234"},
    "company": {"value": "Marketing Agency"},
    "jobtitle": {"value": "Marketing Director"}
  }
}
```

**Field Mapping Applied:**
- Wrapped in `properties` object ✅
- Each field wrapped in `{value: ...}` ✅
- Field names lowercased ✅

---

## 🔄 Migration Guide

### Before (Old Approach) ❌

#### Step 1: Connect with field_mapping
```json
POST /crm/connect
{
  "crm_type": "klaviyo",
  "credentials": {"api_key": "pk_..."},
  "settings": {
    "field_mapping": {
      "customer_name": "first_name",
      "customer_surname": "last_name",
      "mobile": "phone",
      "org": "company"
    }
  }
}
```

#### Step 2: Sync with custom field names
```json
POST /crm/sync/contact
{
  "email": "john@example.com",
  "customer_name": "John",
  "customer_surname": "Doe",
  "mobile": "+1234567890",
  "org": "Acme Corp",
  "properties": {
    "lead_score": 85
  }
}
```

**Problems:**
- ❌ Client needs CRM knowledge
- ❌ Different mappings per merchant
- ❌ Hard to maintain
- ❌ Inconsistent data

---

### After (New Approach) ✅

#### Step 1: Connect (no field_mapping)
```json
POST /crm/connect
{
  "crm_type": "klaviyo",
  "credentials": {"api_key": "pk_..."},
  "settings": {
    "enabled_events": ["order_created"]
  }
}
```

#### Step 2: Sync with standard schema
```json
POST /crm/sync/contact
{
  "email": "john@example.com",
  "first_name": "John",
  "last_name": "Doe",
  "phone": "+1234567890",
  "company": "Acme Corp",
  "custom_properties": {
    "lead_score": 85
  }
}
```

**Benefits:**
- ✅ No CRM knowledge needed
- ✅ Consistent across all merchants
- ✅ Easy to maintain
- ✅ Backend handles everything

---

## 📚 Field Mapping Reference

### Klaviyo

| Standard Field | Klaviyo Field | Notes |
|----------------|---------------|-------|
| `phone` | `phone_number` | Auto-converted |
| `company` | `organization` | Auto-converted |
| `state` | `region` | Auto-converted |
| `postal_code` | `zip` | Auto-converted |
| `street_address` | `address1` | Auto-converted |
| `custom_properties` | `properties` | Separate object |

### Salesforce

| Standard Field | Salesforce Field | Notes |
|----------------|------------------|-------|
| `email` | `Email` | Capitalized |
| `first_name` | `FirstName` | Capitalized |
| `last_name` | `LastName` | Capitalized |
| `street_address` | `MailingStreet` | Mailing prefix |
| `custom_properties.*` | `{field}__c` | Custom suffix |

### HubSpot

| Standard Field | HubSpot Field | Notes |
|----------------|---------------|-------|
| `first_name` | `firstname` | Lowercase |
| `last_name` | `lastname` | Lowercase |
| `job_title` | `jobtitle` | Lowercase |
| All fields | `{value: ...}` | Wrapped |

---

## 🧪 Testing

### Test Field Mapping for a CRM

```http
GET /crm/field-mappings/klaviyo
X-Merchant-Id: 550e8400-e29b-41d4-a716-446655440000
```

Returns exactly how your standard fields will be mapped.

### Test Full Flow

1. Connect CRM (no field_mapping)
2. Get field mappings to see how data will transform
3. Sync contact with standard schema
4. Check CRM to verify data arrived correctly

---

## ❓ FAQ

### Q: Do I need to provide field_mapping anymore?
**A:** No! Backend handles all field mapping automatically.

### Q: What if I already have field_mapping in my integration?
**A:** It will be ignored. Migrate to standard schema for best results.

### Q: Can I customize field mappings per merchant?
**A:** Not in the current implementation. All merchants use the same standard schema, ensuring consistency.

### Q: What about custom properties?
**A:** Use the `custom_properties` object. Backend will handle CRM-specific formatting.

### Q: How do I migrate from old approach?
**A:**
1. Update code to use standard field names
2. Remove `field_mapping` from connect call
3. Use `/sync/contact` instead of `/sync/contact/legacy`

### Q: Is backward compatibility supported?
**A:** Yes! Use `/sync/contact/legacy` for old ContactData schema (deprecated).

---

## 🎉 Summary

**Old Way (Client-Controlled):**
```
Client → Provides field_mapping → Syncs custom fields → CRM
         ❌ CRM knowledge required
         ❌ Inconsistent
         ❌ Hard to maintain
```

**New Way (Backend-Controlled):**
```
Client → Standard schema → Backend transforms → CRM
         ✅ No CRM knowledge needed
         ✅ Consistent
         ✅ Easy to maintain
```

**Enjoy the simplified CRM integration! 🚀**
