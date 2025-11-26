-- ============================================================================
-- CRM Microservice - Simplified Schema Migration
-- ============================================================================
-- This migration creates a minimal CRM microservice schema with only 2 tables.
-- Merchant management is handled by the parent service.
-- ============================================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Drop existing schema and recreate (use CASCADE to drop dependent objects)
DROP SCHEMA IF EXISTS crm CASCADE;

-- Create CRM schema (separate from other schemas)
CREATE SCHEMA crm;

-- ============================================================================
-- TABLE 1: CRM INTEGRATIONS
-- ============================================================================
-- Stores CRM connection configurations for each merchant
-- One row per merchant-CRM pair (e.g., merchant A connects Klaviyo + Salesforce = 2 rows)

CREATE TABLE crm.crm_integrations (
  integration_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Merchant identifier (provided by parent service, no FK)
  merchant_id UUID NOT NULL,

  -- CRM type: 'klaviyo', 'salesforce', 'creatio', 'hubspot', etc.
  crm_type TEXT NOT NULL,

  -- Encrypted credentials stored as BYTEA (pgcrypto encrypted)
  -- Format varies by CRM type (see docs for examples)
  encrypted_credentials BYTEA NOT NULL,

  -- CRM-specific settings (NOT encrypted) - JSONB for flexibility
  -- Examples: field_mapping, sync_frequency, enabled_events, list_id, etc.
  settings JSONB DEFAULT '{}'::jsonb,

  -- Integration status tracking
  is_active BOOLEAN DEFAULT TRUE,
  sync_status TEXT DEFAULT 'connected',  -- 'connected', 'syncing', 'error', 'disconnected'
  sync_error TEXT,                       -- Last error message if any

  -- Timestamps
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_sync_at TIMESTAMPTZ,

  -- Constraint: One integration per merchant per CRM type
  UNIQUE(merchant_id, crm_type)
);

-- Indexes for performance
CREATE INDEX idx_crm_integrations_merchant_id ON crm.crm_integrations(merchant_id);
CREATE INDEX idx_crm_integrations_crm_type ON crm.crm_integrations(crm_type);
CREATE INDEX idx_crm_integrations_is_active ON crm.crm_integrations(is_active);
CREATE INDEX idx_crm_integrations_merchant_crm ON crm.crm_integrations(merchant_id, crm_type);
CREATE INDEX idx_crm_integrations_sync_status ON crm.crm_integrations(sync_status);

COMMENT ON TABLE crm.crm_integrations IS 'Stores CRM integration configurations and encrypted credentials';
COMMENT ON COLUMN crm.crm_integrations.merchant_id IS 'UUID from parent service (no foreign key)';
COMMENT ON COLUMN crm.crm_integrations.encrypted_credentials IS 'Encrypted JSON credentials using pgcrypto';
COMMENT ON COLUMN crm.crm_integrations.settings IS 'Non-sensitive CRM configuration (field mapping, sync settings, etc.)';

-- ============================================================================
-- TABLE 2: CRM SYNC LOGS
-- ============================================================================
-- Audit trail for every data sync sent to CRM systems
-- Critical for debugging, monitoring, and analytics

CREATE TABLE crm.crm_sync_logs (
  log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Foreign key to integration (CASCADE delete)
  integration_id UUID NOT NULL REFERENCES crm.crm_integrations(integration_id) ON DELETE CASCADE,

  -- Denormalized merchant_id for fast queries (no FK)
  merchant_id UUID NOT NULL,

  -- CRM details
  crm_type TEXT NOT NULL,

  -- What was synced
  operation_type TEXT NOT NULL,  -- 'create_contact', 'update_contact', 'send_event', 'create_order'
  entity_type TEXT NOT NULL,     -- 'contact', 'lead', 'event', 'order'
  entity_id TEXT,                -- Local entity ID (e.g., order_id from parent service)

  -- Request/Response data (full audit trail)
  request_payload JSONB NOT NULL,
  response_payload JSONB,
  crm_entity_id TEXT,            -- CRM's ID for the created/updated entity

  -- Status tracking
  status TEXT NOT NULL DEFAULT 'pending',  -- 'pending', 'success', 'failed', 'retrying'
  status_code INTEGER,           -- HTTP status code (200, 401, 500, etc.)
  error_message TEXT,
  error_details JSONB,

  -- Retry logic for transient failures
  retry_count INTEGER DEFAULT 0,
  max_retries INTEGER DEFAULT 3,
  next_retry_at TIMESTAMPTZ,

  -- Performance metrics
  request_started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  request_completed_at TIMESTAMPTZ,
  duration_ms INTEGER,           -- Auto-calculated via trigger

  -- Metadata for debugging
  source TEXT,                   -- 'api', 'webhook', 'cron', 'manual'
  triggered_by TEXT,             -- merchant_id or 'system'
  endpoint TEXT,                 -- CRM API endpoint called

  -- Timestamps
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for performance and analytics
CREATE INDEX idx_crm_sync_logs_integration_id ON crm.crm_sync_logs(integration_id);
CREATE INDEX idx_crm_sync_logs_merchant_id ON crm.crm_sync_logs(merchant_id);
CREATE INDEX idx_crm_sync_logs_crm_type ON crm.crm_sync_logs(crm_type);
CREATE INDEX idx_crm_sync_logs_status ON crm.crm_sync_logs(status);
CREATE INDEX idx_crm_sync_logs_created_at ON crm.crm_sync_logs(created_at DESC);
CREATE INDEX idx_crm_sync_logs_entity ON crm.crm_sync_logs(entity_type, entity_id);
CREATE INDEX idx_crm_sync_logs_operation ON crm.crm_sync_logs(operation_type);
CREATE INDEX idx_crm_sync_logs_retry ON crm.crm_sync_logs(status, next_retry_at) WHERE status = 'retrying';

COMMENT ON TABLE crm.crm_sync_logs IS 'Complete audit trail of all CRM sync operations';
COMMENT ON COLUMN crm.crm_sync_logs.request_payload IS 'Exact data sent to CRM API';
COMMENT ON COLUMN crm.crm_sync_logs.response_payload IS 'Response from CRM API';
COMMENT ON COLUMN crm.crm_sync_logs.duration_ms IS 'Auto-calculated request duration in milliseconds';

-- ============================================================================
-- HELPER FUNCTIONS
-- ============================================================================

-- Function: Update updated_at timestamp
CREATE OR REPLACE FUNCTION crm.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger: Auto-update updated_at for crm_integrations
CREATE TRIGGER update_crm_integrations_updated_at
    BEFORE UPDATE ON crm.crm_integrations
    FOR EACH ROW
    EXECUTE FUNCTION crm.update_updated_at_column();

-- Trigger: Auto-update updated_at for crm_sync_logs
CREATE TRIGGER update_crm_sync_logs_updated_at
    BEFORE UPDATE ON crm.crm_sync_logs
    FOR EACH ROW
    EXECUTE FUNCTION crm.update_updated_at_column();

-- ============================================================================
-- ENCRYPTION FUNCTIONS
-- ============================================================================

-- Function: Encrypt credentials using pgcrypto
CREATE OR REPLACE FUNCTION crm.encrypt_credentials(credentials_json JSONB, encryption_key TEXT)
RETURNS BYTEA AS $$
BEGIN
    RETURN pgp_sym_encrypt(credentials_json::TEXT, encryption_key);
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION crm.encrypt_credentials IS 'Encrypts CRM credentials using AES-256 symmetric encryption';

-- Function: Decrypt credentials using pgcrypto
CREATE OR REPLACE FUNCTION crm.decrypt_credentials(encrypted_data BYTEA, encryption_key TEXT)
RETURNS JSONB AS $$
BEGIN
    RETURN pgp_sym_decrypt(encrypted_data, encryption_key)::JSONB;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION crm.decrypt_credentials IS 'Decrypts CRM credentials from encrypted BYTEA';

-- ============================================================================
-- PERFORMANCE TRACKING
-- ============================================================================

-- Function: Auto-calculate request duration
CREATE OR REPLACE FUNCTION crm.calculate_duration()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.request_completed_at IS NOT NULL AND NEW.request_started_at IS NOT NULL THEN
        NEW.duration_ms = EXTRACT(EPOCH FROM (NEW.request_completed_at - NEW.request_started_at)) * 1000;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger: Auto-calculate duration for sync logs
CREATE TRIGGER calculate_crm_sync_duration
    BEFORE INSERT OR UPDATE ON crm.crm_sync_logs
    FOR EACH ROW
    EXECUTE FUNCTION crm.calculate_duration();

COMMENT ON FUNCTION crm.calculate_duration IS 'Auto-calculates duration_ms from request start/complete timestamps';

-- ============================================================================
-- ANALYTICS VIEWS (Optional)
-- ============================================================================

-- View: CRM Integration Summary
CREATE OR REPLACE VIEW crm.integration_summary AS
SELECT
    merchant_id,
    COUNT(*) as total_integrations,
    COUNT(*) FILTER (WHERE is_active = TRUE) as active_integrations,
    ARRAY_AGG(DISTINCT crm_type) FILTER (WHERE is_active = TRUE) as active_crms,
    MAX(last_sync_at) as last_sync_at
FROM crm.crm_integrations
GROUP BY merchant_id;

COMMENT ON VIEW crm.integration_summary IS 'Summary of CRM integrations per merchant';

-- View: Sync Performance by CRM Type
CREATE OR REPLACE VIEW crm.sync_performance AS
SELECT
    crm_type,
    COUNT(*) as total_syncs,
    COUNT(*) FILTER (WHERE status = 'success') as successful_syncs,
    COUNT(*) FILTER (WHERE status = 'failed') as failed_syncs,
    ROUND(AVG(duration_ms), 2) as avg_duration_ms,
    ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY duration_ms), 2) as median_duration_ms,
    ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms), 2) as p95_duration_ms
FROM crm.crm_sync_logs
WHERE created_at > NOW() - INTERVAL '7 days'
  AND status IN ('success', 'failed')
GROUP BY crm_type;

COMMENT ON VIEW crm.sync_performance IS 'CRM sync performance metrics (last 7 days)';

-- ============================================================================
-- GRANT PERMISSIONS (Optional - adjust based on your setup)
-- ============================================================================

-- Example: Grant permissions to CRM service role
-- GRANT USAGE ON SCHEMA crm TO crm_service_role;
-- GRANT ALL ON ALL TABLES IN SCHEMA crm TO crm_service_role;
-- GRANT ALL ON ALL SEQUENCES IN SCHEMA crm TO crm_service_role;
-- GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA crm TO crm_service_role;

-- ============================================================================
-- MIGRATION COMPLETE
-- ============================================================================

DO $$
BEGIN
    RAISE NOTICE '';
    RAISE NOTICE '╔════════════════════════════════════════════════════════════════╗';
    RAISE NOTICE '║  ✅ CRM Microservice Schema Setup Complete                    ║';
    RAISE NOTICE '╚════════════════════════════════════════════════════════════════╝';
    RAISE NOTICE '';
    RAISE NOTICE '📊 Database Objects Created:';
    RAISE NOTICE '   ├── Schema: crm';
    RAISE NOTICE '   ├── Tables (2):';
    RAISE NOTICE '   │   ├── crm.crm_integrations';
    RAISE NOTICE '   │   └── crm.crm_sync_logs';
    RAISE NOTICE '   ├── Functions (3):';
    RAISE NOTICE '   │   ├── encrypt_credentials()';
    RAISE NOTICE '   │   ├── decrypt_credentials()';
    RAISE NOTICE '   │   └── calculate_duration()';
    RAISE NOTICE '   ├── Triggers (3):';
    RAISE NOTICE '   │   ├── update_crm_integrations_updated_at';
    RAISE NOTICE '   │   ├── update_crm_sync_logs_updated_at';
    RAISE NOTICE '   │   └── calculate_crm_sync_duration';
    RAISE NOTICE '   └── Views (2):';
    RAISE NOTICE '       ├── integration_summary';
    RAISE NOTICE '       └── sync_performance';
    RAISE NOTICE '';
    RAISE NOTICE '⚠️  Important Next Steps:';
    RAISE NOTICE '   1. Set CRM_ENCRYPTION_KEY in your .env file (32 characters)';
    RAISE NOTICE '   2. Start the service: python run.py';
    RAISE NOTICE '   3. Test health: curl http://localhost:8001/healthz';
    RAISE NOTICE '';
    RAISE NOTICE '📖 Documentation: See README.md for API usage';
    RAISE NOTICE '';
END $$;
