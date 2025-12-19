# CRM Microservice

A standalone microservice for managing CRM integrations and synchronizing customer data across multiple CRM platforms.

## Overview

This service handles:
- **CRM Integration Management**: Connect/disconnect CRM systems (Klaviyo, Salesforce, Creatio, etc.)
- **Data Synchronization**: Send contacts and events to configured CRMs
- **Field Mapping**: Transform data based on CRM-specific requirements
- **Audit Logging**: Track all sync operations for debugging and analytics

## Architecture

### Microservice Pattern
- **No user authentication**: User ID is provided via `X-User-Id` header by the parent service
- **Firebase user IDs**: Supports Firebase user IDs (e.g., p9uOHM8ABHgwBYGT0dRpZmfyUWn1)
- **Database isolation**: Uses `crm` schema separate from other services
- **Encrypted credentials**: All CRM credentials encrypted using pgcrypto

### Database Schema (2 Tables)

```
crm schema
├── crm_integrations     (CRM configs + encrypted credentials)
└── crm_sync_logs        (Audit trail of all sync operations)
```

## Setup

### 1. Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
# Database (required)
DB_DSN=postgresql://user:pass@localhost:5432/db?options=-c%20search_path=crm

# Environment
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=INFO

# CRM Encryption (required - exactly 32 characters)
CRM_ENCRYPTION_KEY=your-32-character-key-here-1234

# Service Port
PORT=8001

# Optional: API Key for service-to-service auth
# API_KEY=your-internal-api-key

# Optional: CORS
CORS_ALLOWED_ORIGINS=*
```

### 2. Database Migration

Run the migrations to create/update the schema:

```bash
# Initial schema (if new installation)
psql $DB_DSN -f app/models.sql

# Migration from merchant_id to user_id (if upgrading)
psql $DB_DSN -f migrations/001_rename_merchant_id_to_user_id.sql
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the Service

```bash
python run.py
```

Or with uvicorn directly:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

## API Endpoints

All endpoints require `X-User-Id` header with a valid Firebase user ID (UUID format).

### CRM Integration Management

#### `POST /crm/validate`
Validate CRM credentials without saving

#### `POST /crm/connect`
Connect a CRM integration with credentials and settings

**Note:** The `field_mapping` setting is deprecated. Use the standard contact schema instead.

#### `GET /crm/{crm_type}/status`
Get integration status

#### `DELETE /crm/{crm_type}/disconnect`
Disconnect CRM integration

#### `GET /crm/list`
List all CRM integrations for user

### Data Synchronization

#### `POST /crm/sync/contact`
Sync contact to configured CRMs using standard contact schema

**Request Body Example:**
```json
{
  "email": "user@example.com",
  "first_name": "John",
  "last_name": "Doe",
  "phone": "+1234567890",
  "custom_properties": {
    "lead_source": "website",
    "company": "Acme Inc"
  }
}
```

#### `POST /crm/sync/event`
Send event to configured CRMs

#### `GET /crm/field-mappings/{crm_type}`
Get field mapping information for a specific CRM type

#### `GET /crm/field-mappings`
List field mappings for all supported CRM types

See full API documentation at `/docs` when service is running.

## Supported CRM Types

| CRM | Type ID | Status |
|-----|---------|--------|
| Klaviyo | `klaviyo` | Implemented |
| Salesforce | `salesforce` | Implemented |
| Creatio | `creatio` | Implemented |
| HubSpot | `hubspot` | Coming Soon |

## License

Proprietary - All rights reserved
