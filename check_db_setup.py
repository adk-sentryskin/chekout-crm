#!/usr/bin/env python3
"""
Database Setup Diagnostic Script
Run this to check if the database is properly configured for the CRM service.
"""

import asyncio
import asyncpg
import sys
from app.config import settings


async def check_database_setup():
    """Check if database is properly set up with all required components"""

    print("=" * 70)
    print("CRM Microservice Database Diagnostic")
    print("=" * 70)
    print()

    # Check if environment variables are set
    print("1. Checking Environment Variables...")
    print(f"   ✓ DB_DSN: {'Set' if settings.DB_DSN else 'NOT SET ❌'}")
    print(f"   ✓ CRM_ENCRYPTION_KEY: {'Set ({} chars)'.format(len(settings.CRM_ENCRYPTION_KEY)) if settings.CRM_ENCRYPTION_KEY else 'NOT SET ❌'}")
    print(f"   ✓ ENVIRONMENT: {settings.ENVIRONMENT}")
    print()

    if not settings.CRM_ENCRYPTION_KEY:
        print("❌ ERROR: CRM_ENCRYPTION_KEY is not set!")
        print("   Set it in your .env file (must be exactly 32 characters)")
        return False

    if len(settings.CRM_ENCRYPTION_KEY) < 32:
        print(f"⚠️  WARNING: CRM_ENCRYPTION_KEY should be at least 32 characters (current: {len(settings.CRM_ENCRYPTION_KEY)})")

    try:
        # Connect to database
        print("2. Testing Database Connection...")
        conn = await asyncpg.connect(dsn=settings.DB_DSN)
        print("   ✓ Successfully connected to database")
        print()

        # Check if pgcrypto extension is installed
        print("3. Checking pgcrypto Extension...")
        pgcrypto_exists = await conn.fetchval("""
            SELECT EXISTS(
                SELECT 1 FROM pg_extension WHERE extname = 'pgcrypto'
            )
        """)

        if pgcrypto_exists:
            print("   ✓ pgcrypto extension is installed")
        else:
            print("   ❌ pgcrypto extension is NOT installed")
            print("      Run: CREATE EXTENSION IF NOT EXISTS pgcrypto;")
            await conn.close()
            return False
        print()

        # Check if CRM schema exists
        print("4. Checking CRM Schema...")
        schema_exists = await conn.fetchval("""
            SELECT EXISTS(
                SELECT 1 FROM information_schema.schemata WHERE schema_name = 'crm'
            )
        """)

        if schema_exists:
            print("   ✓ CRM schema exists")
        else:
            print("   ❌ CRM schema does NOT exist")
            print("      Run migrations: python -c 'from app.db import run_migrations; import asyncio; asyncio.run(run_migrations())'")
            await conn.close()
            return False
        print()

        # Check if tables exist
        print("5. Checking Database Tables...")
        tables = await conn.fetch("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'crm'
            ORDER BY table_name
        """)

        required_tables = {'crm_integrations', 'crm_sync_logs'}
        existing_tables = {row['table_name'] for row in tables}

        for table in required_tables:
            if table in existing_tables:
                print(f"   ✓ Table '{table}' exists")
            else:
                print(f"   ❌ Table '{table}' does NOT exist")

        if not required_tables.issubset(existing_tables):
            print("      Run migrations to create missing tables")
            await conn.close()
            return False
        print()

        # Check if functions exist
        print("6. Checking Database Functions...")
        functions = await conn.fetch("""
            SELECT routine_name
            FROM information_schema.routines
            WHERE routine_schema = 'crm'
            AND routine_type = 'FUNCTION'
            ORDER BY routine_name
        """)

        required_functions = {'encrypt_credentials', 'decrypt_credentials', 'calculate_duration'}
        existing_functions = {row['routine_name'] for row in functions}

        for func in required_functions:
            if func in existing_functions:
                print(f"   ✓ Function '{func}' exists")
            else:
                print(f"   ❌ Function '{func}' does NOT exist")

        if not required_functions.issubset(existing_functions):
            print("      Run migrations to create missing functions")
            await conn.close()
            return False
        print()

        # Test encryption/decryption
        print("7. Testing Encryption Functions...")
        try:
            test_data = {"api_key": "test_key_12345"}
            encrypted = await conn.fetchval(
                "SELECT crm.encrypt_credentials($1::jsonb, $2)",
                test_data,
                settings.CRM_ENCRYPTION_KEY
            )
            print("   ✓ Encryption successful")

            decrypted = await conn.fetchval(
                "SELECT crm.decrypt_credentials($1, $2)",
                encrypted,
                settings.CRM_ENCRYPTION_KEY
            )
            print("   ✓ Decryption successful")

            if decrypted == test_data:
                print("   ✓ Encryption/Decryption round-trip successful")
            else:
                print("   ❌ Encryption/Decryption data mismatch")
                await conn.close()
                return False
        except Exception as e:
            print(f"   ❌ Encryption test failed: {e}")
            await conn.close()
            return False
        print()

        await conn.close()

        print("=" * 70)
        print("✅ All checks passed! Database is properly configured.")
        print("=" * 70)
        return True

    except asyncpg.exceptions.InvalidPasswordError:
        print("❌ Database authentication failed. Check your DB_DSN credentials.")
        return False
    except asyncpg.exceptions.InvalidCatalogNameError:
        print("❌ Database does not exist. Check your DB_DSN.")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(check_database_setup())
    sys.exit(0 if success else 1)
