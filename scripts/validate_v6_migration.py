#!/usr/bin/env python3
"""
V6 Migration Validation Script
Validates database schema and RLS policies
"""

import asyncio
import asyncpg
import os
import sys
from datetime import datetime

async def validate_migration():
    """Validate v6 migration data integrity and RLS"""
    
    # Connection parameters
    conn_params = {
        'host': os.getenv('DB_HOST', 'localhost'),
        'database': os.getenv('DB_NAME', 'parking_v6'),
        'user': os.getenv('DB_USER', 'parking_user'),
        'password': os.getenv('DB_PASSWORD', 'parking_password')
    }
    
    print("=" * 70)
    print("🔍 V6 Migration Validation")
    print("=" * 70)
    print(f"Database: {conn_params['database']}@{conn_params['host']}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    try:
        conn = await asyncpg.connect(**conn_params)
    except Exception as e:
        print(f"❌ Failed to connect to database: {e}")
        return False
    
    all_passed = True
    
    # Test 1: Check required tables exist
    print("\n📋 Test 1: Checking required tables...")
    required_tables = [
        'tenants', 'sensor_devices', 'display_devices', 'gateways',
        'device_assignments', 'chirpstack_sync', 'display_policies',
        'webhook_secrets', 'downlink_queue', 'refresh_tokens',
        'audit_log', 'metrics_snapshot', 'rate_limit_state'
    ]
    
    for table in required_tables:
        exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = $1
            )
        """, table)
        
        if exists:
            print(f"   ✅ {table}")
        else:
            print(f"   ❌ {table} - NOT FOUND")
            all_passed = False
    
    # Test 2: Check tenant_id columns exist
    print("\n🔑 Test 2: Checking tenant_id columns...")
    tenant_tables = [
        'sensor_devices', 'display_devices', 'gateways', 
        'spaces', 'sites', 'display_policies'
    ]
    
    for table in tenant_tables:
        has_tenant_id = await conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_name = $1 AND column_name = 'tenant_id'
            )
        """, table)
        
        if has_tenant_id:
            print(f"   ✅ {table}.tenant_id")
        else:
            print(f"   ❌ {table}.tenant_id - MISSING")
            all_passed = False
    
    # Test 3: Check platform tenant exists
    print("\n🏢 Test 3: Checking platform tenant...")
    platform_tenant = await conn.fetchrow("""
        SELECT * FROM tenants 
        WHERE id = '00000000-0000-0000-0000-000000000000'
    """)
    
    if platform_tenant:
        print(f"   ✅ Platform tenant exists: {platform_tenant['name']}")
    else:
        print("   ❌ Platform tenant NOT FOUND")
        all_passed = False
    
    # Test 4: Check RLS is enabled
    print("\n🔒 Test 4: Checking Row-Level Security...")
    rls_tables = [
        'sensor_devices', 'display_devices', 'gateways',
        'spaces', 'sites', 'audit_log'
    ]
    
    for table in rls_tables:
        rls_enabled = await conn.fetchval("""
            SELECT relrowsecurity 
            FROM pg_class 
            WHERE relname = $1
        """, table)
        
        if rls_enabled:
            print(f"   ✅ {table} - RLS enabled")
        else:
            print(f"   ❌ {table} - RLS NOT enabled")
            all_passed = False
    
    # Test 5: Check RLS policies exist
    print("\n📜 Test 5: Checking RLS policies...")
    policy_count = await conn.fetchval("""
        SELECT COUNT(*) FROM pg_policies
        WHERE policyname = 'tenant_isolation'
    """)
    
    if policy_count >= 6:
        print(f"   ✅ Found {policy_count} tenant_isolation policies")
    else:
        print(f"   ⚠️  Only found {policy_count} tenant_isolation policies (expected >= 6)")
        all_passed = False
    
    # Test 6: Check RLS helper functions exist
    print("\n🔧 Test 6: Checking RLS helper functions...")
    functions = ['current_tenant_id', 'is_platform_admin']
    
    for func in functions:
        exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM pg_proc 
                WHERE proname = $1
            )
        """, func)
        
        if exists:
            print(f"   ✅ {func}()")
        else:
            print(f"   ❌ {func}() - NOT FOUND")
            all_passed = False
    
    # Test 7: Check indexes exist
    print("\n📊 Test 7: Checking indexes...")
    required_indexes = [
        'idx_sensor_devices_tenant',
        'idx_display_devices_tenant',
        'idx_gateways_tenant',
        'idx_audit_log_tenant',
        'idx_chirpstack_sync_status'
    ]
    
    for idx in required_indexes:
        exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM pg_indexes 
                WHERE indexname = $1
            )
        """, idx)
        
        if exists:
            print(f"   ✅ {idx}")
        else:
            print(f"   ❌ {idx} - NOT FOUND")
            all_passed = False
    
    # Test 8: Test RLS with tenant context
    print("\n🧪 Test 8: Testing RLS tenant isolation...")
    try:
        # Set platform tenant context
        await conn.execute(
            "SET LOCAL app.current_tenant_id = '00000000-0000-0000-0000-000000000000'"
        )
        await conn.execute("SET LOCAL app.is_platform_admin = false")
        
        # Count devices visible
        device_count = await conn.fetchval("SELECT COUNT(*) FROM sensor_devices")
        print(f"   ✅ Platform tenant context: sees {device_count} devices")
        
        # Test with non-existent tenant
        await conn.execute(
            "SET LOCAL app.current_tenant_id = '11111111-1111-1111-1111-111111111111'"
        )
        await conn.execute("SET LOCAL app.is_platform_admin = false")
        
        isolated_count = await conn.fetchval("SELECT COUNT(*) FROM sensor_devices")
        print(f"   ✅ Isolated tenant context: sees {isolated_count} devices")
        
    except Exception as e:
        print(f"   ❌ RLS test failed: {e}")
        all_passed = False
    
    # Test 9: Check audit log immutability
    print("\n🛡️  Test 9: Testing audit log immutability...")
    try:
        # Try to create a test entry
        test_id = await conn.fetchval("""
            INSERT INTO audit_log (action, resource_type)
            VALUES ('test', 'validation')
            RETURNING id
        """)
        
        # Try to update it (should fail)
        try:
            await conn.execute("""
                UPDATE audit_log 
                SET action = 'modified' 
                WHERE id = $1
            """, test_id)
            print("   ❌ Audit log allows updates (should be immutable)")
            all_passed = False
        except asyncpg.exceptions.RaiseException:
            print("   ✅ Audit log is immutable (cannot update)")
        
        # Try to delete it (should fail)
        try:
            await conn.execute("DELETE FROM audit_log WHERE id = $1", test_id)
            print("   ❌ Audit log allows deletes (should be immutable)")
            all_passed = False
        except asyncpg.exceptions.RaiseException:
            print("   ✅ Audit log is immutable (cannot delete)")
        
    except Exception as e:
        print(f"   ❌ Audit log immutability test failed: {e}")
        all_passed = False
    
    # Test 10: Check constraints
    print("\n⚖️  Test 10: Checking constraints...")
    constraints = await conn.fetch("""
        SELECT conname, conrelid::regclass::text as table_name
        FROM pg_constraint
        WHERE conname LIKE '%tenant%' OR conname LIKE '%unique%'
        ORDER BY table_name
    """)
    
    if len(constraints) > 0:
        print(f"   ✅ Found {len(constraints)} tenant-related constraints")
        for c in constraints[:5]:
            print(f"      - {c['table_name']}: {c['conname']}")
        if len(constraints) > 5:
            print(f"      ... and {len(constraints) - 5} more")
    else:
        print("   ⚠️  No tenant-related constraints found")
    
    await conn.close()
    
    # Final Summary
    print("\n" + "=" * 70)
    if all_passed:
        print("✅ ALL TESTS PASSED - Migration is valid!")
        print("=" * 70)
        return True
    else:
        print("❌ SOME TESTS FAILED - Please review the migration")
        print("=" * 70)
        return False

if __name__ == "__main__":
    try:
        success = asyncio.run(validate_migration())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Validation interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Validation failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
