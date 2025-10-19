-- Smart Parking v5.3 - Multi-Tenancy & RBAC Migration
-- Implements tenant isolation, site hierarchy, user management, and role-based access control
-- Date: 2025-10-19

-- ============================================================
-- Core Tenant Tables
-- ============================================================

-- Tenants (Organizations)
CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) NOT NULL UNIQUE,

    -- Metadata
    metadata JSONB DEFAULT '{}',

    -- Settings
    settings JSONB DEFAULT '{}',

    -- Status
    is_active BOOLEAN DEFAULT true,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Constraints
    CONSTRAINT valid_slug CHECK (slug ~ '^[a-z0-9-]+$')
);

CREATE INDEX idx_tenants_slug ON tenants(slug) WHERE is_active = true;
CREATE INDEX idx_tenants_active ON tenants(is_active) WHERE is_active = true;

-- Sites (Multi-site support within tenant)
CREATE TABLE sites (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    name VARCHAR(255) NOT NULL,

    -- Location details
    timezone VARCHAR(50) DEFAULT 'UTC',
    location JSONB, -- {address, city, country, coordinates, etc}

    -- Metadata
    metadata JSONB DEFAULT '{}',

    -- Status
    is_active BOOLEAN DEFAULT true,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Foreign keys
    CONSTRAINT fk_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,

    -- Constraints
    CONSTRAINT unique_tenant_site_name UNIQUE (tenant_id, name)
);

CREATE INDEX idx_sites_tenant ON sites(tenant_id) WHERE is_active = true;
CREATE INDEX idx_sites_tenant_active ON sites(tenant_id, is_active);

-- ============================================================
-- User Management
-- ============================================================

-- Users table
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,

    -- User settings
    metadata JSONB DEFAULT '{}',

    -- Status
    is_active BOOLEAN DEFAULT true,
    email_verified BOOLEAN DEFAULT false,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_login_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_users_email ON users(email) WHERE is_active = true;
CREATE INDEX idx_users_active ON users(is_active);

-- User memberships (links users to tenants with roles)
CREATE TABLE user_memberships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    tenant_id UUID NOT NULL,
    role VARCHAR(20) NOT NULL,

    -- Metadata
    metadata JSONB DEFAULT '{}',

    -- Status
    is_active BOOLEAN DEFAULT true,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Foreign keys
    CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,

    -- Constraints
    CONSTRAINT valid_role CHECK (role IN ('owner', 'admin', 'operator', 'viewer')),
    CONSTRAINT unique_user_tenant UNIQUE (user_id, tenant_id)
);

CREATE INDEX idx_user_memberships_user ON user_memberships(user_id) WHERE is_active = true;
CREATE INDEX idx_user_memberships_tenant ON user_memberships(tenant_id) WHERE is_active = true;
CREATE INDEX idx_user_memberships_role ON user_memberships(tenant_id, role) WHERE is_active = true;

-- ============================================================
-- Update Existing Tables for Multi-Tenancy
-- ============================================================

-- Add tenant_id to api_keys
ALTER TABLE api_keys ADD COLUMN tenant_id UUID;
ALTER TABLE api_keys ADD CONSTRAINT fk_tenant
    FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
CREATE INDEX idx_api_keys_tenant ON api_keys(tenant_id) WHERE is_active = true;

-- Add site_id to spaces (spaces belong to sites)
ALTER TABLE spaces ADD COLUMN site_id UUID;
ALTER TABLE spaces ADD CONSTRAINT fk_site
    FOREIGN KEY (site_id) REFERENCES sites(id) ON DELETE RESTRICT;
CREATE INDEX idx_spaces_site ON spaces(site_id) WHERE deleted_at IS NULL;

-- Add tenant_id denormalized to spaces for fast lookups
ALTER TABLE spaces ADD COLUMN tenant_id UUID;
CREATE INDEX idx_spaces_tenant ON spaces(tenant_id) WHERE deleted_at IS NULL;

-- Add unique constraint for code within tenant+site
DROP INDEX IF EXISTS unique_space_code;
ALTER TABLE spaces DROP CONSTRAINT IF EXISTS unique_space_code;
-- Make code unique within tenant (not globally)
CREATE UNIQUE INDEX unique_tenant_site_space_code ON spaces(tenant_id, site_id, code) WHERE deleted_at IS NULL;

-- ============================================================
-- Triggers for Denormalization
-- ============================================================

-- Function to sync tenant_id from site to space
CREATE OR REPLACE FUNCTION sync_space_tenant_id()
RETURNS TRIGGER AS $$
BEGIN
    -- Sync tenant_id from site
    IF NEW.site_id IS NOT NULL THEN
        NEW.tenant_id := (SELECT tenant_id FROM sites WHERE id = NEW.site_id);
    ELSIF NEW.site_id IS NULL THEN
        NEW.tenant_id := NULL;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER spaces_sync_tenant_id
    BEFORE INSERT OR UPDATE OF site_id ON spaces
    FOR EACH ROW
    EXECUTE FUNCTION sync_space_tenant_id();

-- Update trigger for tenants
CREATE TRIGGER update_tenants_updated_at
    BEFORE UPDATE ON tenants
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- Update trigger for sites
CREATE TRIGGER update_sites_updated_at
    BEFORE UPDATE ON sites
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- Update trigger for users
CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- Update trigger for user_memberships
CREATE TRIGGER update_user_memberships_updated_at
    BEFORE UPDATE ON user_memberships
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- ============================================================
-- Views for Multi-Tenancy Management
-- ============================================================

-- View: Active tenants with user counts
CREATE VIEW tenant_summary AS
SELECT
    t.id,
    t.name,
    t.slug,
    t.is_active,
    t.created_at,
    COUNT(DISTINCT s.id) as site_count,
    COUNT(DISTINCT um.user_id) as user_count,
    COUNT(DISTINCT ak.id) as api_key_count,
    COUNT(DISTINCT sp.id) as space_count
FROM tenants t
LEFT JOIN sites s ON t.id = s.tenant_id AND s.is_active = true
LEFT JOIN user_memberships um ON t.id = um.tenant_id AND um.is_active = true
LEFT JOIN api_keys ak ON t.id = ak.tenant_id AND ak.is_active = true
LEFT JOIN spaces sp ON t.id = sp.tenant_id AND sp.deleted_at IS NULL
WHERE t.is_active = true
GROUP BY t.id, t.name, t.slug, t.is_active, t.created_at;

-- View: User permissions across tenants
CREATE VIEW user_permissions AS
SELECT
    u.id as user_id,
    u.email,
    u.name,
    t.id as tenant_id,
    t.name as tenant_name,
    t.slug as tenant_slug,
    um.role,
    um.is_active as membership_active,
    u.is_active as user_active
FROM users u
INNER JOIN user_memberships um ON u.id = um.user_id
INNER JOIN tenants t ON um.tenant_id = t.id
WHERE u.is_active = true
ORDER BY u.email, t.name;

-- View: Site details with tenant info
CREATE VIEW site_details AS
SELECT
    s.id as site_id,
    s.name as site_name,
    s.timezone,
    s.location,
    s.is_active as site_active,
    t.id as tenant_id,
    t.name as tenant_name,
    t.slug as tenant_slug,
    COUNT(DISTINCT sp.id) as space_count,
    COUNT(DISTINCT sp.id) FILTER (WHERE sp.state = 'FREE') as free_spaces,
    COUNT(DISTINCT sp.id) FILTER (WHERE sp.state = 'OCCUPIED') as occupied_spaces
FROM sites s
INNER JOIN tenants t ON s.tenant_id = t.id
LEFT JOIN spaces sp ON s.id = sp.site_id AND sp.deleted_at IS NULL
WHERE s.is_active = true AND t.is_active = true
GROUP BY s.id, s.name, s.timezone, s.location, s.is_active, t.id, t.name, t.slug;

-- ============================================================
-- Seed Data (Development/Testing)
-- ============================================================

-- Create default tenant
INSERT INTO tenants (id, name, slug, metadata) VALUES
('00000000-0000-0000-0000-000000000001', 'Default Organization', 'default', '{"description": "Default tenant for backward compatibility"}');

-- Create default site
INSERT INTO sites (id, tenant_id, name, timezone, location) VALUES
('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000001', 'Default Site', 'UTC', '{"city": "Default", "country": "Unknown"}');

-- Link existing API keys to default tenant (backward compatibility)
UPDATE api_keys SET tenant_id = '00000000-0000-0000-0000-000000000001' WHERE tenant_id IS NULL;

-- Link existing spaces to default site (backward compatibility)
UPDATE spaces SET site_id = '00000000-0000-0000-0000-000000000001' WHERE site_id IS NULL;

-- Make tenant_id and site_id required after migration
-- ALTER TABLE api_keys ALTER COLUMN tenant_id SET NOT NULL;
-- ALTER TABLE spaces ALTER COLUMN site_id SET NOT NULL;
-- ALTER TABLE spaces ALTER COLUMN tenant_id SET NOT NULL;

-- Note: Uncomment the above ALTER statements after verifying all data is migrated

-- ============================================================
-- Comments
-- ============================================================

COMMENT ON TABLE tenants IS 'Organizations/tenants with strict data isolation';
COMMENT ON TABLE sites IS 'Physical locations within a tenant (multi-site support)';
COMMENT ON TABLE users IS 'User accounts for authentication';
COMMENT ON TABLE user_memberships IS 'Links users to tenants with role-based permissions';
COMMENT ON COLUMN user_memberships.role IS 'owner: full access + billing; admin: manage site/users; operator: reservations/telemetry; viewer: read-only';
COMMENT ON COLUMN spaces.tenant_id IS 'Denormalized tenant_id for fast lookups without joins';
COMMENT ON VIEW tenant_summary IS 'Summary statistics for each active tenant';
COMMENT ON VIEW user_permissions IS 'User access matrix across all tenants';
COMMENT ON VIEW site_details IS 'Site information with occupancy statistics';

-- Grant permissions (adjust for your user)
GRANT ALL ON ALL TABLES IN SCHEMA public TO parking;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO parking;
