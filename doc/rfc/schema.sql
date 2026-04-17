-- Hometower Phase 1 — PostgreSQL DDL
-- All tables use UUID primary keys (gen_random_uuid())
-- updated_at is maintained by trigger on all tables that carry it

-- ============================================================
-- ENUM TYPES
-- ============================================================

CREATE TYPE device_type AS ENUM (
    'Server', 'Switch', 'Router', 'NAS', 'UPS', 'SBC',
    'Workstation', 'VM', 'LXC', 'Docker', 'Application', 'VLAN', 'Subnet'
);

CREATE TYPE connection_type AS ENUM (
    'Ethernet', 'WiFi', 'Fibre', 'iSCSI', 'NFS', 'VM', 'Other'
);

CREATE TYPE user_role AS ENUM ('Admin', 'Contributor', 'Reader');

CREATE TYPE location_type AS ENUM ('rack', 'geo');

-- ============================================================
-- USERS
-- ============================================================

CREATE TABLE users (
    id            UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    username      VARCHAR(100) NOT NULL,
    email         VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role          user_role    NOT NULL DEFAULT 'Contributor',
    is_active     BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_users_username UNIQUE (username),
    CONSTRAINT uq_users_email    UNIQUE (email)
);

CREATE INDEX idx_users_email ON users (email);

-- ============================================================
-- LOCATIONS
-- ============================================================

CREATE TABLE locations (
    id         UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    name       VARCHAR(255) NOT NULL,
    type       location_type NOT NULL,
    lat        NUMERIC(10, 7),         -- required when type = 'geo'
    lng        NUMERIC(10, 7),         -- required when type = 'geo'
    rack       VARCHAR(100),
    row        VARCHAR(100),
    parent_id  UUID REFERENCES locations (id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_locations_geo_coords CHECK (
        (type = 'geo' AND lat IS NOT NULL AND lng IS NOT NULL)
        OR (type = 'rack' AND lat IS NULL AND lng IS NULL)
    )
);

CREATE INDEX idx_locations_parent_id ON locations (parent_id);
CREATE INDEX idx_locations_type      ON locations (type);

-- ============================================================
-- DEVICES
-- ============================================================

CREATE TABLE devices (
    id          UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(255)  NOT NULL,
    type        device_type   NOT NULL,
    ip          INET,
    mac         MACADDR,
    os          VARCHAR(255),
    notes       TEXT,
    location_id UUID REFERENCES locations (id) ON DELETE SET NULL,
    created_at  TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_devices_name        ON devices (name);
CREATE INDEX idx_devices_type        ON devices (type);
CREATE INDEX idx_devices_location_id ON devices (location_id);
-- Supports free-text search on name
CREATE INDEX idx_devices_name_trgm   ON devices USING GIN (name gin_trgm_ops);

-- ============================================================
-- CONNECTIONS
-- ============================================================

CREATE TABLE connections (
    id         UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id  UUID            NOT NULL REFERENCES devices (id) ON DELETE CASCADE,
    target_id  UUID            NOT NULL REFERENCES devices (id) ON DELETE CASCADE,
    type       connection_type NOT NULL,
    label      VARCHAR(255),
    created_at TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_connections_no_self_loop CHECK (source_id <> target_id)
);

CREATE INDEX idx_connections_source_id ON connections (source_id);
CREATE INDEX idx_connections_target_id ON connections (target_id);

-- ============================================================
-- TAGS
-- ============================================================

CREATE TABLE tags (
    id         UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    name       VARCHAR(100) NOT NULL,
    color      VARCHAR(7)   NOT NULL DEFAULT '#6366f1',
    created_at TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_tags_name  UNIQUE (name),
    CONSTRAINT chk_tags_color CHECK (color ~ '^#[0-9A-Fa-f]{6}$')
);

-- ============================================================
-- DEVICE–TAG JUNCTION
-- ============================================================

CREATE TABLE device_tags (
    device_id UUID NOT NULL REFERENCES devices (id) ON DELETE CASCADE,
    tag_id    UUID NOT NULL REFERENCES tags    (id) ON DELETE CASCADE,
    PRIMARY KEY (device_id, tag_id)
);

CREATE INDEX idx_device_tags_tag_id ON device_tags (tag_id);

-- ============================================================
-- CUSTOM FIELDS
-- ============================================================

CREATE TABLE custom_fields (
    id         UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    device_id  UUID         NOT NULL REFERENCES devices (id) ON DELETE CASCADE,
    key        VARCHAR(100) NOT NULL,
    value      TEXT         NOT NULL,
    created_at TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_custom_fields_device_key UNIQUE (device_id, key)
);

CREATE INDEX idx_custom_fields_device_id ON custom_fields (device_id);

-- ============================================================
-- DIAGRAM LAYOUTS
-- ============================================================

CREATE TABLE diagram_layouts (
    id             UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    name           VARCHAR(255) NOT NULL,
    cytoscape_json JSONB        NOT NULL,
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- ============================================================
-- UPDATED_AT TRIGGER (applied to all versioned tables)
-- ============================================================

CREATE OR REPLACE FUNCTION fn_set_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();

CREATE TRIGGER trg_locations_updated_at
    BEFORE UPDATE ON locations
    FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();

CREATE TRIGGER trg_devices_updated_at
    BEFORE UPDATE ON devices
    FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();

CREATE TRIGGER trg_connections_updated_at
    BEFORE UPDATE ON connections
    FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();

CREATE TRIGGER trg_diagram_layouts_updated_at
    BEFORE UPDATE ON diagram_layouts
    FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();

-- ============================================================
-- EXTENSIONS (required for gin_trgm_ops index)
-- ============================================================

-- Add at the TOP of migration, before CREATE INDEX gin_trgm_ops:
-- CREATE EXTENSION IF NOT EXISTS pg_trgm;
