-- APScheduler Job Store Schema Migration
-- Creates dedicated schema for APScheduler persistent job storage

-- Create schema for APScheduler jobs
CREATE SCHEMA IF NOT EXISTS scheduler;

-- Grant permissions to parking_user
GRANT USAGE ON SCHEMA scheduler TO parking_user;
GRANT ALL ON ALL TABLES IN SCHEMA scheduler TO parking_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA scheduler GRANT ALL ON TABLES TO parking_user;

COMMENT ON SCHEMA scheduler IS 'APScheduler persistent job store for reservation lifecycle management';
