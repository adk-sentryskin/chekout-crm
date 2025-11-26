import asyncpg
from .config import settings

pool: asyncpg.pool.Pool | None = None

async def init_db():
    """Initialize database connection pool with CRM schema"""
    global pool
    # Set search_path to crm schema by default
    pool = await asyncpg.create_pool(
        dsn=settings.DB_DSN,
        min_size=1,
        max_size=10,
        server_settings={'search_path': 'crm,public'}
    )

async def get_conn():
    """Get database connection from pool"""
    if pool is None:
        raise RuntimeError("DB pool not initialized")
    async with pool.acquire() as conn:
        yield conn
