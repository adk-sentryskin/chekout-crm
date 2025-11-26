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
- **No merchant authentication**: Merchant ID is provided via `X-Merchant-Id` header by the parent service
- **No Firebase dependencies**: Pure microservice without external auth dependencies
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

Run the migration to create the schema:

```bash
psql $DB_DSN -f migrations/001_simplified_crm_schema.sql
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

All endpoints require `X-Merchant-Id` header with a valid UUID.

### CRM Integration Management

#### `POST /crm/validate`
Validate CRM credentials without saving

#### `POST /crm/connect`
Connect a CRM integration with credentials and settings

#### `GET /crm/{crm_type}/status`
Get integration status

#### `DELETE /crm/{crm_type}/disconnect`
Disconnect CRM integration

#### `GET /crm/list`
List all CRM integrations for merchant

### Data Synchronization

#### `POST /crm/sync/contact`
Sync contact to configured CRMs

#### `POST /crm/sync/event`
Send event to configured CRMs

See full API documentation at `/docs` when service is running.

## Supported CRM Types

| CRM | Type ID | Status |
|-----|---------|--------|
| Klaviyo | `klaviyo` | ✅ Implemented |
| Salesforce | `salesforce` | ✅ Implemented |
| Creatio | `creatio` | ✅ Implemented |
| HubSpot | `hubspot` | 🔜 Coming Soon |

## License

Proprietary - All rights reserved
