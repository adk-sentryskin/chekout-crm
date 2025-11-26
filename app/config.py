from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env"
    )

    # Database
    DB_DSN: str

    # Environment and security settings
    ENVIRONMENT: str  # Required: development, staging, or production
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # CRM Integration Settings
    CRM_ENCRYPTION_KEY: str  # Required: 32-character key for encrypting CRM credentials

    # CRM Service Port
    PORT: int = 8001

    # Optional: API Key for service-to-service authentication
    API_KEY: str | None = None

    # Optional: CORS (if needed for direct frontend access)
    CORS_ALLOWED_ORIGINS: str = "*"

settings = Settings()
