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

settings = Settings()
