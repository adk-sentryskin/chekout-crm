#!/bin/bash

# =============================================================================
# CRM Microservice Database Setup Script
# =============================================================================

set -e  # Exit on error

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║           CRM Microservice Database Setup                     ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "⚠️  .env file not found. Creating from .env.example..."
    cp .env.example .env
    echo "✅ Created .env file"
    echo ""
    echo "⚠️  IMPORTANT: Edit .env and set the following:"
    echo "   - DB_DSN (your PostgreSQL connection string)"
    echo "   - CRM_ENCRYPTION_KEY (exactly 32 characters)"
    echo ""
    read -p "Press Enter after you've updated .env..."
fi

# Load environment variables
if [ -f ".env" ]; then
    set -a
    source .env
    set +a
fi

# Check if DB_DSN is set
if [ -z "$DB_DSN" ]; then
    echo "❌ DB_DSN not set in .env file"
    echo ""
    echo "Please set DB_DSN in .env, example:"
    echo "DB_DSN=postgresql://user:password@localhost:5432/database"
    exit 1
fi

# Check if CRM_ENCRYPTION_KEY is set and is 32 characters
if [ -z "$CRM_ENCRYPTION_KEY" ]; then
    echo "❌ CRM_ENCRYPTION_KEY not set in .env file"
    echo ""
    echo "Please set a 32-character encryption key in .env:"
    echo "CRM_ENCRYPTION_KEY=$(openssl rand -base64 24)"
    exit 1
fi

KEY_LENGTH=${#CRM_ENCRYPTION_KEY}
if [ $KEY_LENGTH -ne 32 ]; then
    echo "⚠️  WARNING: CRM_ENCRYPTION_KEY should be exactly 32 characters"
    echo "   Current length: $KEY_LENGTH characters"
    echo ""
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo "📊 Database Configuration:"
echo "   Database: $(echo "$DB_DSN" | sed -E 's/@.*/@[hidden]/')"
echo ""

# Parse database details for psql connection
DB_HOST=$(echo "$DB_DSN" | sed -E 's|.*@([^:/]+).*|\1|')
DB_PORT=$(echo "$DB_DSN" | sed -E 's|.*:([0-9]+)/.*|\1|')
DB_NAME=$(echo "$DB_DSN" | sed -E 's|.*/([^?]+).*|\1|')
DB_USER=$(echo "$DB_DSN" | sed -E 's|.*://([^:]+):.*|\1|')
DB_PASS=$(echo "$DB_DSN" | sed -E 's|.*://[^:]+:([^@]+)@.*|\1|')

# Set PGPASSWORD for password authentication
export PGPASSWORD="$DB_PASS"

# Test database connection
echo "🔌 Testing database connection..."
if psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1" > /dev/null 2>&1; then
    echo "✅ Database connection successful"
else
    echo "❌ Failed to connect to database"
    echo ""
    echo "Connection details:"
    echo "   Host: $DB_HOST"
    echo "   Port: $DB_PORT"
    echo "   Database: $DB_NAME"
    echo "   User: $DB_USER"
    echo ""
    echo "Please check your DB_DSN in .env file"
    unset PGPASSWORD
    exit 1
fi

echo ""
read -p "Ready to run schema migration? (Y/n): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]] && [[ ! -z $REPLY ]]; then
    echo "Cancelled."
    exit 0
fi

echo ""
echo "⚠️  WARNING: This will DROP and RECREATE the crm schema!"
echo "   All existing CRM data will be lost."
echo ""
read -p "Are you sure you want to continue? (yes/no): " -r
if [[ ! $REPLY == "yes" ]]; then
    echo "Cancelled."
    unset PGPASSWORD
    exit 0
fi

echo ""
echo "🚀 Running schema migration..."
echo ""

# Run the migration using parsed connection details
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f app/models.sql

# Unset password after use
unset PGPASSWORD

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║              Database Setup Complete! 🎉                       ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "📋 Verification Commands:"
echo ""
echo "1. Check tables:"
echo "   PGPASSWORD='$DB_PASS' psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -c \"\\dt crm.*\""
echo ""
echo "2. Check functions:"
echo "   PGPASSWORD='$DB_PASS' psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -c \"\\df crm.*\""
echo ""
echo "3. Test encryption:"
echo "   PGPASSWORD='$DB_PASS' psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -c \"SELECT crm.encrypt_credentials('{\\\"test\\\":\\\"data\\\"}'::jsonb, '$CRM_ENCRYPTION_KEY');\""
echo ""
echo "🚀 Next Steps:"
echo "   1. Install dependencies: pip install -r requirements.txt"
echo "   2. Start the service: python run.py"
echo "   3. Test health: curl http://localhost:8001/healthz"
echo ""
