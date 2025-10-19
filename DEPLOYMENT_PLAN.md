# Smart Parking v2 - Deployment Plan

## Current Situation

The v4 system is still running with these services:
- PostgreSQL on port 5432
- Redis on port 6379
- Mosquitto on port 1883
- ChirpStack on port 8080
- Various APIs on port 8000

## Deployment Options

### Option 1: Side-by-Side Deployment (Recommended for Testing)
Run v5 alongside v4 using different ports:
- **API**: 8002 (instead of 8000)
- **PostgreSQL**: 5433 (instead of 5432) - new database
- **Redis**: 6380 (instead of 6379) - new instance
- **ChirpStack**: Reuse existing on 8080
- **Mosquitto**: Reuse existing on 1883

**Pros:**
- Safe testing without affecting production
- Can compare behavior side-by-side
- Easy rollback

**Cons:**
- Uses more resources
- Need separate database

### Option 2: In-Place Migration (Production Cutover)
Stop v4 services and start v5:
1. Stop old API services
2. Migrate database data
3. Start v5 services on same ports
4. Update ChirpStack webhooks

**Pros:**
- Clean migration
- Uses standard ports
- Lower resource usage

**Cons:**
- Requires downtime
- Riskier
- Harder to rollback

### Option 3: Shared Infrastructure
Use existing ChirpStack/Mosquitto/PostgreSQL, only run new API:
- **API**: Port 8002
- **Database**: Connect to existing PostgreSQL (new schema)
- **Redis**: Use existing Redis (different DB number)
- **ChirpStack**: Reuse existing
- **Mosquitto**: Reuse existing

**Pros:**
- Minimal resource usage
- Quick to start
- Easy migration path

**Cons:**
- Shared database requires careful schema management
- Could affect production if bugs exist

## Recommended Approach

**Start with Option 3 (Shared Infrastructure) for Initial Testing:**

1. Use existing PostgreSQL with a new database name: `parking_v2`
2. Use existing Redis DB 1 (v4 uses DB 0)
3. Reuse ChirpStack and Mosquitto
4. Run new API on port 8002

Then move to Option 2 for production cutover after testing.

## Next Steps

Choose your deployment option and I'll help configure it.
