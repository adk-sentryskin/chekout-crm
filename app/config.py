from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Database
    DB_DSN: str

    # Identity Platform service account fields
    GCP_PROJECT_ID: str
    SA_PRIVATE_KEY_ID: str
    SA_PRIVATE_KEY: str  # keep \n escaped in env; we'll unescape
    SA_CLIENT_EMAIL: str
    SA_CLIENT_ID: str

    # Firebase Web API Key (for REST API calls)
    FIREBASE_API_KEY: str  # Required: Get from Firebase Console

    # Frontend URL (for redirects in email links)
    FRONTEND_URL: str  # Required: http://localhost:3000 or https://yourdomain.com

    # CORS
    CORS_ALLOWED_ORIGINS: str = "*"  # comma-separated in prod

    # Environment and security settings
    ENVIRONMENT: str  # Required: development, staging, or production
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # Optional: Rate limiting
    RATE_LIMIT_PER_MINUTE: int = 100

    # Optional: Token validation settings
    CHECK_TOKEN_REVOCATION: bool = True
    TOKEN_CACHE_TTL: int = 300  # 5 minutes

    # CRM Integration Settings
    CRM_ENCRYPTION_KEY: str  # Required: 32-character key for encrypting CRM credentials

    # CRM Service Port
    PORT: int = 8001

    class Config:
        env_file = ".env"  # for local dev only

settings = Settings()
