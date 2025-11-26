# CRM Service

Standalone CRM integration service for managing merchant CRM connections (Klaviyo, Salesforce, Creatio, etc.).

## Features

- **Merchant Authentication**: Firebase-based authentication for merchant users
- **CRM Integrations**: Support for multiple CRM platforms
  - Klaviyo
  - Salesforce
  - Creatio
  - (Extensible for more CRM providers)
- **Secure Credential Storage**: PostgreSQL pgcrypto encryption for CRM credentials
- **Sync Logging**: Complete audit trail of all CRM synchronization operations
- **RESTful API**: FastAPI-based REST API with automatic documentation

## Architecture

- **Framework**: FastAPI 0.115.4
- **Database**: PostgreSQL (asyncpg for async connections)
- **Authentication**: Firebase Admin SDK
- **Schema**: `crm` schema (separate from checkout system)
- **Entity Model**: `merchant_id` (UUID) as primary identifier

## Project Structure

```
chekout-crm/
├── app/
│   ├── main.py                 # FastAPI application
│   ├── config.py               # Configuration management
│   ├── db.py                   # Database connection pool
│   ├── deps.py                 # Authentication dependencies
│   ├── exceptions.py           # Error handlers
│   ├── response_models.py      # Standardized responses
│   ├── models/                 # Pydantic models
│   │   ├── merchant.py
│   │   └── crm.py
│   ├── routers/                # API endpoints
│   │   ├── merchants.py        # Merchant auth & profile
│   │   └── crm.py              # CRM integrations
│   ├── services/               # Business logic
│   │   ├── request_logger.py
│   │   └── crm/                # CRM services
│   │       ├── base.py
│   │       ├── manager.py
│   │       └── providers/
│   └── models.sql              # Database schema
├── requirements.txt
├── run.py
├── .env.example
└── README.md
```

## Setup

### 1. Install Dependencies

```bash
cd chekout-crm
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your actual values
```

Required environment variables:
- `DB_DSN`: PostgreSQL connection string (with `search_path=crm`)
- `GCP_PROJECT_ID`, `SA_PRIVATE_KEY`, etc.: Firebase credentials
- `CRM_ENCRYPTION_KEY`: 32-character key for encrypting CRM credentials
- `PORT`: Service port (default: 8001)

### 3. Initialize Database

```bash
# Connect to your PostgreSQL database
psql $DB_DSN

# Run the schema creation
\i app/models.sql
```

### 4. Run the Service

**Development mode (with auto-reload):**
```bash
uvicorn app.main:app --reload --port 8001
```

**Production mode:**
```bash
python run.py
```

The service will be available at: `http://localhost:8001`

## API Documentation

Once running, visit:
- **Interactive API docs**: http://localhost:8001/docs
- **Alternative docs**: http://localhost:8001/redoc
- **Health check**: http://localhost:8001/healthz

## API Endpoints

### Authentication

- `POST /auth/bootstrap` - Initialize merchant account on first login
- `GET /auth/me` - Get current merchant profile
- `PATCH /auth/profile` - Update merchant profile

### CRM Integrations

- `POST /crm/validate` - Validate CRM credentials (test before saving)
- `POST /crm/connect` - Connect a CRM integration
- `GET /crm/{crm_type}/status` - Get integration status
- `DELETE /crm/{crm_type}/disconnect` - Disconnect integration
- `GET /crm/list` - List all merchant's integrations

## Database Schema

The service uses the `crm` schema in PostgreSQL:

**Main Tables:**
- `crm.merchants` - Merchant accounts (using merchant_id UUID)
- `crm.crm_integrations` - CRM connection configurations
- `crm.crm_sync_logs` - Complete sync operation history
- `crm.login_logs` - Authentication audit trail
- `crm.audit_logs` - General action logging

## CRM Providers

### Klaviyo
```json
{
  "crm_type": "klaviyo",
  "credentials": {
    "api_key": "pk_..."
  }
}
```

### Salesforce
```json
{
  "crm_type": "salesforce",
  "credentials": {
    "username": "user@example.com",
    "password": "password",
    "security_token": "token"
  }
}
```

### Creatio
```json
{
  "crm_type": "creatio",
  "credentials": {
    "instance_url": "https://yourinstance.creatio.com",
    "username": "user@example.com",
    "password": "password"
  }
}
```

## Development

### Adding a New CRM Provider

1. Create provider class in `app/services/crm/providers/your_crm.py`
2. Extend `BaseCRMService`
3. Implement required methods:
   - `validate_credentials()`
   - `create_or_update_contact()`
   - `send_event()`
   - `get_contact()`
4. Register in `app/services/crm/manager.py`
5. Add CRM type to `CRMType` enum in `base.py`

## Security

- **Credential Encryption**: All CRM credentials encrypted at rest using PostgreSQL pgcrypto
- **Firebase Authentication**: All endpoints protected by Firebase ID token verification
- **Audit Logging**: Complete activity tracking for compliance
- **CORS Protection**: Configurable allowed origins
- **Rate Limiting**: SlowAPI integration for DDoS protection

## Monitoring

Health check endpoint:

```bash
curl http://localhost:8001/healthz
```

## License

Proprietary - All Rights Reserved