-- Migration: Rename merchant_id to user_id across CRM schema
-- Date: 2025-12-19
-- Description: Updates all references from merchant_id to user_id throughout the CRM service

BEGIN;

-- Step 1: Rename column in crm_integrations table
ALTER TABLE crm.crm_integrations
RENAME COLUMN merchant_id TO user_id;

-- Step 2: Rename column in crm_sync_logs table
ALTER TABLE crm.crm_sync_logs
RENAME COLUMN merchant_id TO user_id;

-- Step 3: Update comment on user_id column in crm_integrations
COMMENT ON COLUMN crm.crm_integrations.user_id IS 'Firebase user ID from parent service (e.g., p9uOHM8ABHgwBYGT0dRpZmfyUWn1)';

-- Step 4: Update comment on user_id column in crm_sync_logs
COMMENT ON COLUMN crm.crm_sync_logs.user_id IS 'Denormalized user_id for efficient querying';

-- Step 5: Drop and recreate the unique constraint with new column name
ALTER TABLE crm.crm_integrations
DROP CONSTRAINT IF EXISTS crm_integrations_merchant_id_crm_type_key;

ALTER TABLE crm.crm_integrations
ADD CONSTRAINT crm_integrations_user_id_crm_type_key UNIQUE (user_id, crm_type);

-- Step 6: Recreate indexes with new column names
-- Drop old indexes
DROP INDEX IF EXISTS crm.idx_crm_integrations_merchant_id;
DROP INDEX IF EXISTS crm.idx_crm_integrations_merchant_crm_type;
DROP INDEX IF EXISTS crm.idx_crm_integrations_merchant_active;
DROP INDEX IF EXISTS crm.idx_crm_sync_logs_merchant_id;
DROP INDEX IF EXISTS crm.idx_crm_sync_logs_merchant_integration;

-- Create new indexes
CREATE INDEX idx_crm_integrations_user_id ON crm.crm_integrations(user_id);
CREATE INDEX idx_crm_integrations_user_crm_type ON crm.crm_integrations(user_id, crm_type);
CREATE INDEX idx_crm_integrations_user_active ON crm.crm_integrations(user_id, is_active) WHERE is_active = TRUE;
CREATE INDEX idx_crm_sync_logs_user_id ON crm.crm_sync_logs(user_id);
CREATE INDEX idx_crm_sync_logs_user_integration ON crm.crm_sync_logs(user_id, integration_id);

-- Step 7: Recreate views with updated column names
DROP VIEW IF EXISTS crm.integration_summary;
DROP VIEW IF EXISTS crm.sync_performance;

CREATE OR REPLACE VIEW crm.integration_summary AS
SELECT
    user_id,
    crm_type,
    COUNT(*) as total_integrations,
    SUM(CASE WHEN is_active THEN 1 ELSE 0 END) as active_integrations,
    MAX(last_sync_at) as last_sync_at,
    MIN(created_at) as first_created_at
FROM crm.crm_integrations
GROUP BY user_id, crm_type;

CREATE OR REPLACE VIEW crm.sync_performance AS
SELECT
    user_id,
    crm_type,
    operation_type,
    entity_type,
    COUNT(*) as total_requests,
    SUM(CASE WHEN status = 'SUCCESS' THEN 1 ELSE 0 END) as successful_requests,
    SUM(CASE WHEN status = 'ERROR' THEN 1 ELSE 0 END) as failed_requests,
    AVG(duration_ms) as avg_duration_ms,
    MAX(duration_ms) as max_duration_ms,
    MIN(duration_ms) as min_duration_ms,
    MAX(created_at) as last_sync_at
FROM crm.crm_sync_logs
WHERE status IN ('SUCCESS', 'ERROR')
GROUP BY user_id, crm_type, operation_type, entity_type;

COMMIT;
