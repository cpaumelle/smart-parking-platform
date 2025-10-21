#!/usr/bin/env python3
"""
Test Row-Level Security (RLS) for Multi-Tenant Isolation

This script tests that:
1. Tenant A can only see their own data
2. Tenant B can only see their own data
3. Cross-tenant data leakage is prevented
"""
import asyncio
import asyncpg
import os
from uuid import UUID

# Database connection string
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://parking_user:parking_password@localhost:5432/parking_v5")

async def test_rls():
    """Test RLS tenant isolation"""
    print("=" * 70)
    print("Testing Row-Level Security (RLS) for Multi-Tenant Isolation")
    print("=" * 70)

    conn = await asyncpg.connect(DATABASE_URL)

    try:
        # Get two different tenants from the database
        tenants = await conn.fetch("SELECT id, name FROM tenants LIMIT 2")

        if len(tenants) < 2:
            print("❌ ERROR: Need at least 2 tenants in database for testing")
            return

        tenant_a = tenants[0]
        tenant_b = tenants[1]

        print(f"\nTenant A: {tenant_a['name']} ({tenant_a['id']})")
        print(f"Tenant B: {tenant_b['name']} ({tenant_b['id']})")

        # Test 1: Count spaces without RLS (should see all)
        print("\n" + "-" * 70)
        print("TEST 1: Query WITHOUT RLS (should see all spaces)")
        print("-" * 70)

        total_spaces = await conn.fetchval("SELECT COUNT(*) FROM spaces WHERE deleted_at IS NULL")
        print(f"Total spaces in database: {total_spaces}")

        # Test 2: Query with Tenant A context
        print("\n" + "-" * 70)
        print(f"TEST 2: Query WITH RLS as Tenant A ({tenant_a['name']})")
        print("-" * 70)

        # Set tenant context
        await conn.execute(f"SET LOCAL app.current_tenant = '{tenant_a['id']}'")

        tenant_a_spaces = await conn.fetchval("SELECT COUNT(*) FROM spaces WHERE deleted_at IS NULL")
        print(f"Spaces visible to Tenant A: {tenant_a_spaces}")

        # Show sample spaces for Tenant A
        spaces_a = await conn.fetch("""
            SELECT id, code, name, state
            FROM spaces
            WHERE deleted_at IS NULL
            LIMIT 5
        """)

        print("\nSample spaces for Tenant A:")
        for space in spaces_a:
            print(f"  - {space['code']}: {space['name']} ({space['state']})")

        # Test 3: Query with Tenant B context (new connection to reset RLS)
        print("\n" + "-" * 70)
        print(f"TEST 3: Query WITH RLS as Tenant B ({tenant_b['name']})")
        print("-" * 70)

        # Need new connection because SET LOCAL is transaction-scoped
        conn2 = await asyncpg.connect(DATABASE_URL)

        try:
            # Set tenant context for Tenant B
            await conn2.execute(f"SET LOCAL app.current_tenant = '{tenant_b['id']}'")

            tenant_b_spaces = await conn2.fetchval("SELECT COUNT(*) FROM spaces WHERE deleted_at IS NULL")
            print(f"Spaces visible to Tenant B: {tenant_b_spaces}")

            # Show sample spaces for Tenant B
            spaces_b = await conn2.fetch("""
                SELECT id, code, name, state
                FROM spaces
                WHERE deleted_at IS NULL
                LIMIT 5
            """)

            print("\nSample spaces for Tenant B:")
            for space in spaces_b:
                print(f"  - {space['code']}: {space['name']} ({space['state']})")

        finally:
            await conn2.close()

        # Test 4: Verify isolation
        print("\n" + "=" * 70)
        print("RLS ISOLATION VERIFICATION")
        print("=" * 70)

        print(f"\n✓ Total spaces: {total_spaces}")
        print(f"✓ Tenant A spaces: {tenant_a_spaces}")
        print(f"✓ Tenant B spaces: {tenant_b_spaces}")
        print(f"✓ Sum of tenant spaces: {tenant_a_spaces + tenant_b_spaces}")

        if tenant_a_spaces + tenant_b_spaces <= total_spaces:
            print("\n✅ PASS: RLS is working! Tenants see isolated data.")
        else:
            print("\n❌ FAIL: RLS may not be working correctly!")

        if tenant_a_spaces > 0 and tenant_b_spaces == 0:
            print("⚠️  WARNING: Tenant B has no spaces. Create spaces for Tenant B to verify complete isolation.")
        elif tenant_a_spaces == 0 and tenant_b_spaces > 0:
            print("⚠️  WARNING: Tenant A has no spaces. Create spaces for Tenant A to verify complete isolation.")
        elif tenant_a_spaces == 0 and tenant_b_spaces == 0:
            print("⚠️  WARNING: Both tenants have no spaces. Create spaces to verify RLS.")

        # Test 5: Test sensor_readings isolation
        print("\n" + "=" * 70)
        print("SENSOR READINGS RLS TEST")
        print("=" * 70)

        # Total sensor readings
        total_readings = await conn.fetchval("SELECT COUNT(*) FROM sensor_readings WHERE tenant_id IS NOT NULL")
        print(f"\nTotal sensor_readings with tenant_id: {total_readings}")

        # Tenant A readings (need new connection)
        conn3 = await asyncpg.connect(DATABASE_URL)
        try:
            await conn3.execute(f"SET LOCAL app.current_tenant = '{tenant_a['id']}'")
            tenant_a_readings = await conn3.fetchval("SELECT COUNT(*) FROM sensor_readings")
            print(f"Sensor readings visible to Tenant A: {tenant_a_readings}")
        finally:
            await conn3.close()

        # Tenant B readings
        conn4 = await asyncpg.connect(DATABASE_URL)
        try:
            await conn4.execute(f"SET LOCAL app.current_tenant = '{tenant_b['id']}'")
            tenant_b_readings = await conn4.fetchval("SELECT COUNT(*) FROM sensor_readings")
            print(f"Sensor readings visible to Tenant B: {tenant_b_readings}")
        finally:
            await conn4.close()

        if tenant_a_readings + tenant_b_readings <= total_readings:
            print("✅ PASS: Sensor readings RLS is working!")
        else:
            print("❌ FAIL: Sensor readings RLS may not be working!")

    finally:
        await conn.close()

    print("\n" + "=" * 70)
    print("RLS Test Complete")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(test_rls())
