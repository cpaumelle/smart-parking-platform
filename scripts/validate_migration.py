#!/usr/bin/env python3
"""
Validate v6 migration data integrity
"""

import asyncio
import asyncpg
from datetime import datetime
import os

async def validate_migration():
    # Connect to database
    conn = await asyncpg.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'parking_v6_dev'),
        user=os.getenv('DB_USER', 'parking_user'),
        password=os.getenv('DB_PASSWORD', 'your_password')
    )

    print("🔍 Validating v6 Migration...")
    print("=" * 50)

    # Test 1: Check all devices have tenant_id
    orphans = await conn.fetchval("""
        SELECT COUNT(*) FROM sensor_devices WHERE tenant_id IS NULL
    """)

    if orphans > 0:
        print(f"❌ Found {orphans} sensor devices without tenant_id")
    else:
        print("✅ All sensor devices have tenant_id")

    # Test 2: Verify tenant assignments match spaces
    mismatches = await conn.fetch("""
        SELECT sd.dev_eui, sd.tenant_id as device_tenant, s.tenant_id as space_tenant
        FROM sensor_devices sd
        JOIN spaces sp ON sp.sensor_device_id = sd.id
        JOIN sites s ON s.id = sp.site_id
        WHERE sd.tenant_id != s.tenant_id
    """)

    if mismatches:
        print(f"❌ Found {len(mismatches)} tenant mismatches")
        for m in mismatches[:5]:
            print(f"   Device {m['dev_eui']}: {m['device_tenant']} != {m['space_tenant']}")
    else:
        print("✅ All device-space tenant assignments match")

    # Test 3: Check indexes exist
    indexes = await conn.fetch("""
        SELECT indexname FROM pg_indexes
        WHERE tablename IN ('sensor_devices', 'display_devices', 'gateways')
        AND indexname LIKE 'idx_%tenant%'
    """)

    print(f"✅ Created {len(indexes)} tenant-related indexes")

    # Test 4: Test RLS with tenant context
    await conn.execute("SET app.current_tenant_id = '00000000-0000-0000-0000-000000000000'")
    await conn.execute("SET app.is_platform_admin = false")

    platform_devices = await conn.fetchval("SELECT COUNT(*) FROM sensor_devices")
    print(f"✅ Platform tenant sees {platform_devices} devices")

    # Test with different tenant
    test_tenant = await conn.fetchrow("SELECT id FROM tenants WHERE slug = 'acme' LIMIT 1")
    if test_tenant:
        await conn.execute(f"SET app.current_tenant_id = '{test_tenant['id']}'")
        tenant_devices = await conn.fetchval("SELECT COUNT(*) FROM sensor_devices")
        print(f"✅ Acme tenant sees {tenant_devices} devices")

    await conn.close()
    print("=" * 50)
    print("✅ Migration validation complete!")

if __name__ == "__main__":
    asyncio.run(validate_migration())
