-- CRM Service Database Schema
-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Create CRM schema (separate from checkout's public schema)
CREATE SCHEMA IF NOT EXISTS crm;

-- ============================================================================
-- MERCHANTS TABLE (Primary entity for CRM service)
-- ============================================================================
CREATE TABLE IF NOT EXISTS crm.merchants (
  merchant_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Link to checkout system's user (optional, for cross-service reference)
  checkout_user_id TEXT,

  -- Basic info
  email TEXT UNIQUE NOT NULL,
  name TEXT,
  company_name TEXT,
  phone TEXT,
  email_verified BOOLEAN DEFAULT FALSE,

  -- Merchant status
  status TEXT DEFAULT 'active',              -- 'active', 'suspended', 'trial', 'inactive'
  plan_id TEXT,                              -- e.g., 'free', 'pro', 'enterprise'
  trial_ends_at TIMESTAMPTZ,

  -- Timestamps
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_login_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_merchants_email ON crm.merchants(email);
CREATE INDEX IF NOT EXISTS idx_merchants_checkout_user_id ON crm.merchants(checkout_user_id);
CREATE INDEX IF NOT EXISTS idx_merchants_status ON crm.merchants(status);

-- ============================================================================
-- ROLES (CRM-specific roles)
-- ============================================================================
CREATE TABLE IF NOT EXISTS crm.roles (
  role_id SERIAL PRIMARY KEY,
  role_name TEXT UNIQUE NOT NULL           -- 'OWNER', 'ADMIN', 'MEMBER', 'VIEWER'
);

INSERT INTO crm.roles (role_name)
VALUES ('OWNER'), ('ADMIN'), ('MEMBER'), ('VIEWER')
ON CONFLICT (role_name) DO NOTHING;

-- Mapping merchants -> roles (many-to-many)
CREATE TABLE IF NOT EXISTS crm.merchant_roles (
  merchant_id UUID REFERENCES crm.merchants(merchant_id) ON DELETE CASCADE,
  role_id INT REFERENCES crm.roles(role_id) ON DELETE CASCADE,
  PRIMARY KEY (merchant_id, role_id)
);

-- ============================================================================
-- LOGIN LOGS (Track merchant authentication)
-- ============================================================================
CREATE TABLE IF NOT EXISTS crm.login_logs (
  log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  merchant_id UUID REFERENCES crm.merchants(merchant_id) ON DELETE CASCADE,
  email TEXT,
  auth_provider TEXT,                      -- 'password', 'google.com', 'apple.com', etc.
  success BOOLEAN NOT NULL,
  failure_reason TEXT,

  -- Request metadata
  ip_address TEXT,
  country_code TEXT,                       -- ISO country code (US, IN, etc.)
  country_name TEXT,
  city TEXT,
  region TEXT,

  -- Device & browser info
  user_agent TEXT,
  browser_name TEXT,
  browser_version TEXT,
  os_name TEXT,
  os_version TEXT,
  device_type TEXT,                        -- 'mobile', 'tablet', 'desktop', 'bot'
  device_brand TEXT,
  device_model TEXT,
  is_mobile BOOLEAN,
  is_tablet BOOLEAN,
  is_desktop BOOLEAN,
  is_bot BOOLEAN,

  -- Request details
  referer TEXT,
  origin TEXT,
  endpoint TEXT,
  method TEXT,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_login_logs_merchant_id ON crm.login_logs(merchant_id);
CREATE INDEX IF NOT EXISTS idx_login_logs_created_at ON crm.login_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_login_logs_ip ON crm.login_logs(ip_address);
CREATE INDEX IF NOT EXISTS idx_login_logs_country ON crm.login_logs(country_code);

-- ============================================================================
-- AUDIT LOGS (Track merchant actions)
-- ============================================================================
CREATE TABLE IF NOT EXISTS crm.audit_logs (
  log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  merchant_id UUID REFERENCES crm.merchants(merchant_id) ON DELETE SET NULL,
  action TEXT NOT NULL,                    -- 'login', 'crm_connect', 'crm_disconnect', etc.
  resource_type TEXT,                      -- 'integration', 'merchant', 'sync', etc.
  resource_id TEXT,
  details JSONB,                           -- Additional action-specific data

  -- Request metadata
  ip_address TEXT,
  user_agent TEXT,
  referer TEXT,
  origin TEXT,
  endpoint TEXT,
  method TEXT,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_merchant_id ON crm.audit_logs(merchant_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON crm.audit_logs(action);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON crm.audit_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_resource ON crm.audit_logs(resource_type, resource_id);

-- ============================================================================
-- CRM INTEGRATIONS (Merchant CRM connections)
-- ============================================================================
CREATE TABLE IF NOT EXISTS crm.crm_integrations (
  integration_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  merchant_id UUID NOT NULL REFERENCES crm.merchants(merchant_id) ON DELETE CASCADE,
  crm_type TEXT NOT NULL,                  -- 'klaviyo', 'salesforce', 'creatio', etc.

  -- Encrypted credentials stored as BYTEA
  -- Format varies by CRM type:
  -- Klaviyo: {"api_key": "pk_..."}
  -- Salesforce: {"access_token": "...", "instance_url": "..."}
  -- Creatio: {"instance_url": "...", "username": "...", "password": "..."}
  encrypted_credentials BYTEA NOT NULL,    -- pgcrypto encrypted JSON

  -- Optional CRM-specific settings (not encrypted)
  -- Examples: {"sync_frequency": "real-time", "field_mapping": {...}}
  settings JSONB DEFAULT '{}'::jsonb,

  -- Integration status
  is_active BOOLEAN DEFAULT TRUE,
  sync_status TEXT DEFAULT 'connected',    -- 'connected', 'syncing', 'error', 'disconnected'
  sync_error TEXT,                         -- Last sync error message if any

  -- Timestamps
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_sync_at TIMESTAMPTZ,

  -- Ensure one integration per merchant per CRM type
  UNIQUE(merchant_id, crm_type)
);

-- Indexes for querying
CREATE INDEX IF NOT EXISTS idx_crm_integrations_merchant_id ON crm.crm_integrations(merchant_id);
CREATE INDEX IF NOT EXISTS idx_crm_integrations_crm_type ON crm.crm_integrations(crm_type);
CREATE INDEX IF NOT EXISTS idx_crm_integrations_is_active ON crm.crm_integrations(is_active);
CREATE INDEX IF NOT EXISTS idx_crm_integrations_merchant_crm ON crm.crm_integrations(merchant_id, crm_type);

-- ============================================================================
-- CRM SYNC LOGS (Track all data sent to CRMs)
-- ============================================================================
CREATE TABLE IF NOT EXISTS crm.crm_sync_logs (
  log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  integration_id UUID NOT NULL REFERENCES crm.crm_integrations(integration_id) ON DELETE CASCADE,
  merchant_id UUID NOT NULL REFERENCES crm.merchants(merchant_id) ON DELETE CASCADE,

  -- CRM details
  crm_type TEXT NOT NULL,                  -- 'klaviyo', 'salesforce', 'creatio', etc.

  -- Sync operation details
  operation_type TEXT NOT NULL,            -- 'create_lead', 'update_contact', 'create_order', etc.
  entity_type TEXT NOT NULL,               -- 'lead', 'contact', 'order', 'product', etc.
  entity_id TEXT,                          -- Local entity ID (order_id, merchant_id, etc.)

  -- Request/Response data
  request_payload JSONB NOT NULL,          -- Data sent to CRM
  response_payload JSONB,                  -- Response from CRM
  crm_entity_id TEXT,                      -- CRM's ID for the created/updated entity

  -- Status tracking
  status TEXT NOT NULL DEFAULT 'pending',  -- 'pending', 'success', 'failed', 'retrying'
  status_code INTEGER,                     -- HTTP status code
  error_message TEXT,                      -- Error details if failed
  error_details JSONB,                     -- Additional error information

  -- Retry logic
  retry_count INTEGER DEFAULT 0,
  max_retries INTEGER DEFAULT 3,
  next_retry_at TIMESTAMPTZ,

  -- Timing & Performance
  request_started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  request_completed_at TIMESTAMPTZ,
  duration_ms INTEGER,                     -- Request duration in milliseconds

  -- Request metadata (for debugging)
  source TEXT,                             -- 'api', 'webhook', 'manual_test', 'cron', etc.
  triggered_by TEXT,                       -- merchant_id or 'system'
  ip_address TEXT,
  user_agent TEXT,
  endpoint TEXT,                           -- CRM API endpoint called

  -- Timestamps
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_crm_sync_logs_integration_id ON crm.crm_sync_logs(integration_id);
CREATE INDEX IF NOT EXISTS idx_crm_sync_logs_merchant_id ON crm.crm_sync_logs(merchant_id);
CREATE INDEX IF NOT EXISTS idx_crm_sync_logs_crm_type ON crm.crm_sync_logs(crm_type);
CREATE INDEX IF NOT EXISTS idx_crm_sync_logs_status ON crm.crm_sync_logs(status);
CREATE INDEX IF NOT EXISTS idx_crm_sync_logs_created_at ON crm.crm_sync_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_crm_sync_logs_entity ON crm.crm_sync_logs(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_crm_sync_logs_operation ON crm.crm_sync_logs(operation_type);
CREATE INDEX IF NOT EXISTS idx_crm_sync_logs_retry ON crm.crm_sync_logs(status, next_retry_at) WHERE status = 'retrying';

-- ============================================================================
-- HELPER FUNCTIONS & TRIGGERS
-- ============================================================================

-- Update timestamp trigger function
CREATE OR REPLACE FUNCTION crm.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger for merchants
CREATE TRIGGER update_merchants_updated_at
    BEFORE UPDATE ON crm.merchants
    FOR EACH ROW
    EXECUTE FUNCTION crm.update_updated_at_column();

-- Trigger for crm_integrations
CREATE TRIGGER update_crm_integrations_updated_at
    BEFORE UPDATE ON crm.crm_integrations
    FOR EACH ROW
    EXECUTE FUNCTION crm.update_updated_at_column();

-- Trigger for crm_sync_logs
CREATE TRIGGER update_crm_sync_logs_updated_at
    BEFORE UPDATE ON crm.crm_sync_logs
    FOR EACH ROW
    EXECUTE FUNCTION crm.update_updated_at_column();

-- Helper functions for encryption/decryption
-- Note: Set your encryption key via environment variable CRM_ENCRYPTION_KEY

-- Encrypt credentials
CREATE OR REPLACE FUNCTION crm.encrypt_credentials(credentials_json JSONB, encryption_key TEXT)
RETURNS BYTEA AS $$
BEGIN
    RETURN pgp_sym_encrypt(credentials_json::TEXT, encryption_key);
END;
$$ LANGUAGE plpgsql;

-- Decrypt credentials
CREATE OR REPLACE FUNCTION crm.decrypt_credentials(encrypted_data BYTEA, encryption_key TEXT)
RETURNS JSONB AS $$
BEGIN
    RETURN pgp_sym_decrypt(encrypted_data, encryption_key)::JSONB;
END;
$$ LANGUAGE plpgsql;

-- Calculate duration for sync logs
CREATE OR REPLACE FUNCTION crm.calculate_duration()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.request_completed_at IS NOT NULL AND NEW.request_started_at IS NOT NULL THEN
        NEW.duration_ms = EXTRACT(EPOCH FROM (NEW.request_completed_at - NEW.request_started_at)) * 1000;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER calculate_crm_sync_duration
    BEFORE INSERT OR UPDATE ON crm.crm_sync_logs
    FOR EACH ROW
    EXECUTE FUNCTION crm.calculate_duration();

-- ============================================================================
-- API KEYS (Optional: for service-to-service calls)
-- ============================================================================
CREATE TABLE IF NOT EXISTS crm.api_keys (
  api_key_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  merchant_id UUID REFERENCES crm.merchants(merchant_id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  hashed_key TEXT NOT NULL,                -- store hash, never raw
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_used_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_api_keys_merchant_id ON crm.api_keys(merchant_id);
