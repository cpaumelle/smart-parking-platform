"""
Multi-Tenancy and RBAC Tests
Tests tenant isolation, role-based access control, and API key authentication
"""
import pytest
import asyncio
from uuid import uuid4
from httpx import AsyncClient
from datetime import datetime

# NOTE: These tests require the database to be migrated and test fixtures to be set up
# Run migration: docker compose exec postgres psql -U parking -d parking_v5 -f /migrations/002_multi_tenancy_rbac.sql

# Test fixtures will be added here - for now, manual testing recommended

@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires test database fixtures - use for integration testing")
async def test_tenant_isolation_spaces():
    """
    Test that Tenant A cannot see Tenant B's spaces

    Test plan:
    1. Create two tenants with separate users
    2. Tenant A creates a site and space
    3. Tenant B lists spaces
    4. Verify Tenant B cannot see Tenant A's space
    """
    from src.main import app

    async with AsyncClient(app=app, base_url="http://test") as ac:
        # Login as Tenant A user
        login_a = await ac.post("/api/v1/auth/login", json={
            "email": "admin-a@tenant-a.com",
            "password": "password123"
        })
        assert login_a.status_code == 200
        token_a = login_a.json()["access_token"]
        headers_a = {"Authorization": f"Bearer {token_a}"}

        # Login as Tenant B user
        login_b = await ac.post("/api/v1/auth/login", json={
            "email": "admin-b@tenant-b.com",
            "password": "password123"
        })
        assert login_b.status_code == 200
        token_b = login_b.json()["access_token"]
        headers_b = {"Authorization": f"Bearer {token_b}"}

        # Tenant A creates a site
        site_a = await ac.post("/api/v1/sites", headers=headers_a, json={
            "name": "Tenant A Site",
            "timezone": "America/Los_Angeles",
            "location": {"city": "San Francisco"}
        })
        assert site_a.status_code == 201
        site_a_id = site_a.json()["id"]

        # Tenant A creates a space
        space_a = await ac.post("/api/v1/spaces", headers=headers_a, json={
            "name": "Tenant A Space 001",
            "code": "A-001",
            "site_id": site_a_id,
            "building": "Building A",
            "floor": "1",
            "zone": "North"
        })
        assert space_a.status_code == 201
        space_a_code = space_a.json()["code"]

        # Tenant B lists all spaces
        spaces_b = await ac.get("/api/v1/spaces", headers=headers_b)
        assert spaces_b.status_code == 200
        spaces_b_list = spaces_b.json()["spaces"]

        # CRITICAL: Tenant B must not see Tenant A's space
        tenant_a_space_codes = [s["code"] for s in spaces_b_list]
        assert space_a_code not in tenant_a_space_codes, "TENANT ISOLATION FAILED!"

        # Tenant B tries to access Tenant A's space by ID
        space_id_a = space_a.json()["id"]
        space_direct = await ac.get(f"/api/v1/spaces/{space_id_a}", headers=headers_b)
        assert space_direct.status_code == 404, "TENANT ISOLATION FAILED - can access other tenant's space!"


@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires test database fixtures")
async def test_rbac_role_hierarchy():
    """
    Test RBAC role hierarchy enforcement

    Test plan:
    1. VIEWER cannot create spaces (403)
    2. OPERATOR cannot create spaces (403)
    3. ADMIN can create spaces (201)
    4. OWNER can create spaces (201)
    """
    from src.main import app

    async with AsyncClient(app=app, base_url="http://test") as ac:
        # Login as VIEWER
        login_viewer = await ac.post("/api/v1/auth/login", json={
            "email": "viewer@tenant-a.com",
            "password": "password123"
        })
        assert login_viewer.status_code == 200
        token_viewer = login_viewer.json()["access_token"]
        headers_viewer = {"Authorization": f"Bearer {token_viewer}"}

        # Login as OPERATOR
        login_operator = await ac.post("/api/v1/auth/login", json={
            "email": "operator@tenant-a.com",
            "password": "password123"
        })
        assert login_operator.status_code == 200
        token_operator = login_operator.json()["access_token"]
        headers_operator = {"Authorization": f"Bearer {token_operator}"}

        # Login as ADMIN
        login_admin = await ac.post("/api/v1/auth/login", json={
            "email": "admin@tenant-a.com",
            "password": "password123"
        })
        assert login_admin.status_code == 200
        token_admin = login_admin.json()["access_token"]
        headers_admin = {"Authorization": f"Bearer {token_admin}"}

        # Get site ID
        sites = await ac.get("/api/v1/sites", headers=headers_admin)
        site_id = sites.json()[0]["id"]

        # VIEWER cannot create spaces
        space_viewer = await ac.post("/api/v1/spaces", headers=headers_viewer, json={
            "name": "Test Space",
            "code": "TEST-001",
            "site_id": site_id
        })
        assert space_viewer.status_code == 403, "VIEWER should not be able to create spaces"

        # OPERATOR cannot create spaces
        space_operator = await ac.post("/api/v1/spaces", headers=headers_operator, json={
            "name": "Test Space",
            "code": "TEST-002",
            "site_id": site_id
        })
        assert space_operator.status_code == 403, "OPERATOR should not be able to create spaces"

        # ADMIN can create spaces
        space_admin = await ac.post("/api/v1/spaces", headers=headers_admin, json={
            "name": "Test Space Admin",
            "code": "TEST-003",
            "site_id": site_id
        })
        assert space_admin.status_code == 201, "ADMIN should be able to create spaces"


@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires test database fixtures")
async def test_api_key_authentication():
    """
    Test API key authentication and tenant scoping

    Test plan:
    1. Create API key for Tenant A
    2. Use API key to list spaces (should work)
    3. Verify API key only sees Tenant A's spaces
    """
    from src.main import app

    async with AsyncClient(app=app, base_url="http://test") as ac:
        # Login as OWNER to create API key
        login = await ac.post("/api/v1/auth/login", json={
            "email": "owner@tenant-a.com",
            "password": "password123"
        })
        token = login.json()["access_token"]
        headers_jwt = {"Authorization": f"Bearer {token}"}

        # Get tenant ID
        tenant_info = await ac.get("/api/v1/tenants/current", headers=headers_jwt)
        tenant_id = tenant_info.json()["id"]

        # Create API key
        api_key_response = await ac.post("/api/v1/api-keys", headers=headers_jwt, json={
            "name": "Test API Key",
            "tenant_id": tenant_id
        })
        assert api_key_response.status_code == 201
        api_key = api_key_response.json()["key"]

        # Use API key to list spaces
        headers_api = {"X-API-Key": api_key}
        spaces = await ac.get("/api/v1/spaces", headers=headers_api)
        assert spaces.status_code == 200, "API key should work for authenticated requests"

        # Verify all spaces belong to Tenant A
        spaces_list = spaces.json()["spaces"]
        for space in spaces_list:
            assert space["tenant_id"] == tenant_id, "API key leaked cross-tenant data!"


@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires test database fixtures")
async def test_tenant_rate_limiting():
    """
    Test per-tenant rate limiting

    Test plan:
    1. Make many requests from Tenant A
    2. Verify rate limit is enforced (429)
    3. Make request from Tenant B
    4. Verify Tenant B is not affected by Tenant A's rate limit
    """
    from src.main import app

    async with AsyncClient(app=app, base_url="http://test") as ac:
        # Login as Tenant A
        login_a = await ac.post("/api/v1/auth/login", json={
            "email": "admin-a@tenant-a.com",
            "password": "password123"
        })
        token_a = login_a.json()["access_token"]
        headers_a = {"Authorization": f"Bearer {token_a}"}

        # Login as Tenant B
        login_b = await ac.post("/api/v1/auth/login", json={
            "email": "admin-b@tenant-b.com",
            "password": "password123"
        })
        token_b = login_b.json()["access_token"]
        headers_b = {"Authorization": f"Bearer {token_b}"}

        # Hammer Tenant A with requests
        rate_limited = False
        for i in range(200):  # Exceed rate limit
            response = await ac.get("/api/v1/spaces", headers=headers_a)
            if response.status_code == 429:
                rate_limited = True
                break

        assert rate_limited, "Rate limiting not enforced for Tenant A"

        # Tenant B should still be able to make requests
        response_b = await ac.get("/api/v1/spaces", headers=headers_b)
        assert response_b.status_code == 200, "Tenant B affected by Tenant A's rate limit!"


@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires test database fixtures")
async def test_space_code_uniqueness_per_tenant():
    """
    Test that space codes are unique within tenant+site, but not globally

    Test plan:
    1. Tenant A creates space with code "A-001"
    2. Tenant B creates space with code "A-001" (should succeed)
    3. Tenant A tries to create another space with code "A-001" (should fail)
    """
    from src.main import app

    async with AsyncClient(app=app, base_url="http://test") as ac:
        # Login as Tenant A
        login_a = await ac.post("/api/v1/auth/login", json={
            "email": "admin-a@tenant-a.com",
            "password": "password123"
        })
        token_a = login_a.json()["access_token"]
        headers_a = {"Authorization": f"Bearer {token_a}"}

        # Login as Tenant B
        login_b = await ac.post("/api/v1/auth/login", json={
            "email": "admin-b@tenant-b.com",
            "password": "password123"
        })
        token_b = login_b.json()["access_token"]
        headers_b = {"Authorization": f"Bearer {token_b}"}

        # Get site IDs
        sites_a = await ac.get("/api/v1/sites", headers=headers_a)
        site_a_id = sites_a.json()[0]["id"]

        sites_b = await ac.get("/api/v1/sites", headers=headers_b)
        site_b_id = sites_b.json()[0]["id"]

        # Tenant A creates space A-001
        space_a1 = await ac.post("/api/v1/spaces", headers=headers_a, json={
            "name": "Space A-001",
            "code": "A-001",
            "site_id": site_a_id
        })
        assert space_a1.status_code == 201

        # Tenant B creates space A-001 (should succeed - different tenant)
        space_b1 = await ac.post("/api/v1/spaces", headers=headers_b, json={
            "name": "Space A-001",
            "code": "A-001",
            "site_id": site_b_id
        })
        assert space_b1.status_code == 201, "Same code should be allowed in different tenants"

        # Tenant A tries to create another A-001 (should fail - duplicate in same tenant)
        space_a2 = await ac.post("/api/v1/spaces", headers=headers_a, json={
            "name": "Another Space A-001",
            "code": "A-001",
            "site_id": site_a_id
        })
        assert space_a2.status_code == 400, "Duplicate code should be rejected in same tenant"


# ============================================================
# Test Data Setup Functions (Manual Execution)
# ============================================================

async def setup_test_tenants_and_users():
    """
    Manually create test tenants and users for integration testing

    Run this function to populate test data:
    python -c "import asyncio; from tests.test_tenancy_rbac import setup_test_tenants_and_users; asyncio.run(setup_test_tenants_and_users())"
    """
    import asyncpg
    from src.tenant_auth import hash_password

    conn = await asyncpg.connect("postgresql://parking:password@localhost:5432/parking_v5")

    try:
        # Create Tenant A
        tenant_a = await conn.fetchrow("""
            INSERT INTO tenants (name, slug)
            VALUES ('Tenant A Corp', 'tenant-a')
            ON CONFLICT (slug) DO UPDATE SET name = EXCLUDED.name
            RETURNING id
        """)

        # Create Tenant B
        tenant_b = await conn.fetchrow("""
            INSERT INTO tenants (name, slug)
            VALUES ('Tenant B Inc', 'tenant-b')
            ON CONFLICT (slug) DO UPDATE SET name = EXCLUDED.name
            RETURNING id
        """)

        # Create sites for each tenant
        site_a = await conn.fetchrow("""
            INSERT INTO sites (tenant_id, name)
            VALUES ($1, 'Tenant A Main Site')
            ON CONFLICT DO NOTHING
            RETURNING id
        """, tenant_a['id'])

        site_b = await conn.fetchrow("""
            INSERT INTO sites (tenant_id, name)
            VALUES ($1, 'Tenant B Main Site')
            ON CONFLICT DO NOTHING
            RETURNING id
        """, tenant_b['id'])

        # Create users with different roles for Tenant A
        password_hash = hash_password("password123")

        for role, email in [
            ('owner', 'owner@tenant-a.com'),
            ('admin', 'admin-a@tenant-a.com'),
            ('operator', 'operator@tenant-a.com'),
            ('viewer', 'viewer@tenant-a.com')
        ]:
            user = await conn.fetchrow("""
                INSERT INTO users (email, name, password_hash)
                VALUES ($1, $2, $3)
                ON CONFLICT (email) DO UPDATE SET password_hash = EXCLUDED.password_hash
                RETURNING id
            """, email, f"Tenant A {role.title()}", password_hash)

            await conn.execute("""
                INSERT INTO user_memberships (user_id, tenant_id, role)
                VALUES ($1, $2, $3)
                ON CONFLICT (user_id, tenant_id) DO UPDATE SET role = EXCLUDED.role
            """, user['id'], tenant_a['id'], role)

        # Create admin user for Tenant B
        user_b = await conn.fetchrow("""
            INSERT INTO users (email, name, password_hash)
            VALUES ('admin-b@tenant-b.com', 'Tenant B Admin', $1)
            ON CONFLICT (email) DO UPDATE SET password_hash = EXCLUDED.password_hash
            RETURNING id
        """, password_hash)

        await conn.execute("""
            INSERT INTO user_memberships (user_id, tenant_id, role)
            VALUES ($1, $2, 'admin')
            ON CONFLICT (user_id, tenant_id) DO UPDATE SET role = 'admin'
        """, user_b['id'], tenant_b['id'])

        print("✅ Test tenants and users created successfully!")
        print(f"   - Tenant A: {tenant_a['id']}")
        print(f"   - Tenant B: {tenant_b['id']}")
        print(f"   - Site A: {site_a['id'] if site_a else 'exists'}")
        print(f"   - Site B: {site_b['id'] if site_b else 'exists'}")
        print("\nTest users:")
        print("   - owner@tenant-a.com (password: password123)")
        print("   - admin-a@tenant-a.com (password: password123)")
        print("   - operator@tenant-a.com (password: password123)")
        print("   - viewer@tenant-a.com (password: password123)")
        print("   - admin-b@tenant-b.com (password: password123)")

    finally:
        await conn.close()


if __name__ == "__main__":
    print("Setting up test data...")
    asyncio.run(setup_test_tenants_and_users())
