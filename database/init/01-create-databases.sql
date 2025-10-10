-- Create databases for smart parking platform

-- ChirpStack database
CREATE DATABASE chirpstack;

-- Smart Parking database (already created by POSTGRES_DB env var)
-- CREATE DATABASE parking_platform;

-- Configure ChirpStack database
\c chirpstack;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Create schemas in parking_platform
\c parking_platform;

CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS devices;
CREATE SCHEMA IF NOT EXISTS spaces;
CREATE SCHEMA IF NOT EXISTS reservations;
CREATE SCHEMA IF NOT EXISTS analytics;
CREATE SCHEMA IF NOT EXISTS ingest;

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE chirpstack TO parking_user;
GRANT ALL PRIVILEGES ON DATABASE parking_platform TO parking_user;
GRANT ALL PRIVILEGES ON ALL SCHEMAS IN DATABASE parking_platform TO parking_user;
