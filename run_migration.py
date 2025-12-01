#!/usr/bin/env python3
"""
Database migration script for CRM microservice
Runs the SQL migration file using asyncpg
"""
import asyncio
import asyncpg
from pathlib import Path
import sys

# Add app directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Import settings from app config
from app.config import settings

async def run_migration():
    """Run the database migration"""
    db_dsn = settings.DB_DSN

    if not db_dsn:
        print("[ERROR] DB_DSN not found in environment variables")
        return False

    # Remove the search_path option from DSN for connection
    connection_string = db_dsn.split('?')[0]

    print("[INFO] Connecting to database...")
    print(f"       Connection: {connection_string.split('@')[0].split(':')[0]}://***:***@{connection_string.split('@')[1]}")

    try:
        # Connect to database
        conn = await asyncpg.connect(connection_string)
        print("[OK] Database connection successful")

        # Read migration file
        migration_file = Path(__file__).parent / "app" / "models.sql"
        print(f"\n[INFO] Reading migration file: {migration_file}")

        with open(migration_file, 'r', encoding='utf-8') as f:
            migration_sql = f.read()

        print("\n[WARNING] This will DROP and RECREATE the crm schema!")
        print("          All existing CRM data will be lost.")
        response = input("\nContinue? (yes/no): ")

        if response.lower() != 'yes':
            print("[CANCELLED] Migration cancelled")
            await conn.close()
            return False

        print("\n[INFO] Running migration...")

        # Run migration
        await conn.execute(migration_sql)

        print("[OK] Migration completed successfully!")

        # Verify tables were created
        print("\n[INFO] Verifying schema...")
        tables = await conn.fetch("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'crm'
            ORDER BY table_name;
        """)

        print("\n[OK] Tables created:")
        for table in tables:
            print(f"     - crm.{table['table_name']}")

        # Check functions
        functions = await conn.fetch("""
            SELECT routine_name
            FROM information_schema.routines
            WHERE routine_schema = 'crm'
            ORDER BY routine_name;
        """)

        if functions:
            print("\n[OK] Functions created:")
            for func in functions:
                print(f"     - crm.{func['routine_name']}()")

        await conn.close()

        print("\n" + "="*70)
        print("              Database Setup Complete!                             ")
        print("="*70)
        print("\n[NEXT] Start the service with: python run.py")

        return True

    except asyncpg.exceptions.InvalidPasswordError:
        print("[ERROR] Invalid database password")
        return False
    except asyncpg.exceptions.InvalidCatalogNameError:
        print("[ERROR] Database 'checkoutai' does not exist")
        print("        Create it with: createdb checkoutai")
        return False
    except Exception as e:
        print(f"[ERROR] {e}")
        return False

if __name__ == "__main__":
    asyncio.run(run_migration())
