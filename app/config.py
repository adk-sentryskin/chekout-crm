from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

# Get the project root directory (parent of app directory)
PROJECT_ROOT = Path(__file__).parent.parent
ENV_FILE = PROJECT_ROOT / ".env"

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding='utf-8'
    )

    # Database
    DB_DSN: str

    # Cloud SQL Proxy (optional - set to enable secure connection via Cloud SQL Auth Proxy)
    # Format: project:region:instance (e.g., shopify-473015:us-central1:chekoutai-db)
    INSTANCE_CONNECTION_NAME: str | None = None

    # Environment and security settings
    ENVIRONMENT: str  # Required: development, staging, or production
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # CRM Integration Settings
    CRM_ENCRYPTION_KEY: str  # Required: 32-character key for encrypting CRM credentials

    # CRM Service Port
    PORT: int = 8000

    # Optional: API Key for service-to-service authentication
    API_KEY: str | None = None

    # Optional: CORS (if needed for direct frontend access)
    CORS_ALLOWED_ORIGINS: str = "*"

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    # Validator to ensure key length
    from pydantic import field_validator

    @field_validator("CRM_ENCRYPTION_KEY")
    @classmethod
    def validate_encryption_key(cls, v: str) -> str:
        if len(v) != 32:
            raise ValueError(
                f"CRM_ENCRYPTION_KEY must be exactly 32 characters long. Current length: {len(v)}"
            )
        return v

settings = Settings()
