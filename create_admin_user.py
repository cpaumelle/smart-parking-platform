#!/usr/bin/env python3
"""
Create Super Admin User
Creates a user with owner role in the Default Organization tenant
"""
import bcrypt
import asyncio
import asyncpg
import os
from datetime import datetime

# Database connection
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://parking_user:parking_pass@localhost:5432/parking_v5')

# User details
EMAIL = 'cpaumelle@eroundit.eu'
NAME = 'Christophe Paumelle'
PASSWORD = 'vgX3AsKP7cqFa2'

# Tenant (use default tenant)
TENANT_ID = '00000000-0000-0000-0000-000000000001'  # Default Organization

async def create_admin_user():
    """Create admin user with owner role"""

    # Hash password using bcrypt
    salt = bcrypt.gensalt()
    password_hash = bcrypt.hashpw(PASSWORD.encode('utf-8'), salt).decode('utf-8')

    print(f"🔐 Creating super admin user...")
    print(f"   Email: {EMAIL}")
    print(f"   Name: {NAME}")
    print(f"   Tenant: Default Organization")
    print(f"   Role: owner (super admin)")

    # Connect to database
    conn = await asyncpg.connect(DATABASE_URL)

    try:
        # Start transaction
        async with conn.transaction():
            # Check if user already exists
            existing_user = await conn.fetchrow(
                "SELECT id, email FROM users WHERE LOWER(email) = LOWER($1)",
                EMAIL
            )

            if existing_user:
                print(f"\n⚠️  User already exists: {existing_user['email']}")
                print(f"   User ID: {existing_user['id']}")
                user_id = existing_user['id']

                # Update password
                await conn.execute(
                    "UPDATE users SET password_hash = $1, updated_at = NOW() WHERE id = $2",
                    password_hash, user_id
                )
                print(f"✅ Password updated")
            else:
                # Create new user
                user_row = await conn.fetchrow(
                    """
                    INSERT INTO users (email, name, password_hash, is_active, email_verified, metadata)
                    VALUES ($1, $2, $3, true, true, '{"created_by": "admin_script"}'::jsonb)
                    RETURNING id, email
                    """,
                    EMAIL.lower(), NAME, password_hash
                )
                user_id = user_row['id']
                print(f"✅ User created: {user_row['email']}")
                print(f"   User ID: {user_id}")

            # Check if membership already exists
            existing_membership = await conn.fetchrow(
                """
                SELECT id, role FROM user_memberships
                WHERE user_id = $1 AND tenant_id = $2
                """,
                user_id, TENANT_ID
            )

            if existing_membership:
                print(f"\n⚠️  Membership already exists with role: {existing_membership['role']}")

                # Update to owner if not already
                if existing_membership['role'] != 'owner':
                    await conn.execute(
                        """
                        UPDATE user_memberships
                        SET role = 'owner', updated_at = NOW()
                        WHERE id = $1
                        """,
                        existing_membership['id']
                    )
                    print(f"✅ Role upgraded to: owner")
                else:
                    print(f"✅ Already has owner role")
            else:
                # Create membership with owner role
                membership_row = await conn.fetchrow(
                    """
                    INSERT INTO user_memberships (user_id, tenant_id, role, is_active, metadata)
                    VALUES ($1, $2, 'owner', true, '{"created_by": "admin_script"}'::jsonb)
                    RETURNING id, role
                    """,
                    user_id, TENANT_ID
                )
                print(f"✅ Membership created with role: {membership_row['role']}")

            # Get tenant info
            tenant = await conn.fetchrow(
                "SELECT name, slug FROM tenants WHERE id = $1",
                TENANT_ID
            )

            print(f"\n🎉 Super admin user created successfully!")
            print(f"\n📋 Login credentials:")
            print(f"   Email:    {EMAIL}")
            print(f"   Password: {PASSWORD}")
            print(f"   Tenant:   {tenant['name']} ({tenant['slug']})")
            print(f"   Role:     owner (full access)")
            print(f"\n🌐 Login at: https://devices.verdegris.eu/")

    finally:
        await conn.close()

if __name__ == '__main__':
    asyncio.run(create_admin_user())
