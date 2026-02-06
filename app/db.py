import asyncpg
import logging
from pathlib import Path
from urllib.parse import urlparse
from .config import settings

logger = logging.getLogger(__name__)
pool: asyncpg.pool.Pool | None = None


def _get_connection_kwargs() -> dict:
    """Build connection kwargs, using Cloud SQL Proxy Unix socket if configured."""
    if settings.INSTANCE_CONNECTION_NAME:
        # Parse credentials from DB_DSN
        try:
            parsed = urlparse(settings.DB_DSN)
            # When using Cloud SQL Proxy, we connect via Unix socket
            kwargs = {
                'host': f'/cloudsql/{settings.INSTANCE_CONNECTION_NAME}',
                'user': parsed.username,
                'password': parsed.password,
                'database': parsed.path.lstrip('/').split('?')[0],
            }
            logger.info(
                f"🔌 Database config: Using Cloud SQL Proxy ({settings.INSTANCE_CONNECTION_NAME}) with user '{parsed.username}'"
            )
            return kwargs
        except Exception as e:
            logger.error(f"❌ Failed to parse DB_DSN for Cloud SQL Proxy: {str(e)}")
            raise ValueError(f"Invalid DB_DSN for Cloud SQL Proxy connection: {str(e)}")
    else:
        # Direct connection using DSN (local development)
        logger.info("🔌 Database config: Using direct DSN connection")
        return {'dsn': settings.DB_DSN}


async def run_migrations():
    """Run database migrations from models.sql file"""
    try:
        # Get path to models.sql file
        migrations_file = Path(__file__).parent / "models.sql"

        if not migrations_file.exists():
            logger.error(f"Migration file not found: {migrations_file}")
            raise FileNotFoundError(f"Migration file not found: {migrations_file}")

        # Read SQL migration file
        sql_content = migrations_file.read_text(encoding='utf-8')

        logger.info("Running database migrations...")

        # Create a temporary connection to run migrations
        conn = await asyncpg.connect(**_get_connection_kwargs())

        try:
            # Execute the migration SQL
            await conn.execute(sql_content)
            logger.info("✅ Database migrations completed successfully")
        finally:
            await conn.close()

    except Exception as e:
        logger.error(f"❌ Migration failed: {str(e)}")
        raise

async def init_db():
    """Initialize database connection pool with CRM schema"""
    global pool

    # Run migrations first
    await run_migrations()

    # Set search_path to crm schema by default
    pool = await asyncpg.create_pool(
        **_get_connection_kwargs(),
        min_size=1,
        max_size=10,
        server_settings={'search_path': 'crm,public'}
    )

    logger.info("✅ Database connection pool initialized")

async def get_conn():
    """Get database connection from pool"""
    if pool is None:
        raise RuntimeError("DB pool not initialized")
    async with pool.acquire() as conn:
        yield conn
