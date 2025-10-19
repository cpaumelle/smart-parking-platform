#!/usr/bin/env python3
"""
API Key Management Utility

Usage:
    python scripts/manage_api_keys.py create "My App Key"
    python scripts/manage_api_keys.py create "Admin Key" --admin
    python scripts/manage_api_keys.py list
    python scripts/manage_api_keys.py revoke <key_id>
"""
import asyncio
import sys
import argparse
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.auth import generate_api_key, hash_api_key
from src.config import settings
import asyncpg


async def create_api_key(name: str, is_admin: bool = False):
    """Create a new API key"""
    # Generate key
    api_key = generate_api_key()
    key_hash = hash_api_key(api_key)

    # Store in database
    conn = await asyncpg.connect(settings.database_url)

    try:
        row = await conn.fetchrow("""
            INSERT INTO api_keys (key_hash, key_name, is_admin, is_active)
            VALUES ($1, $2, $3, true)
            RETURNING id, created_at
        """, key_hash, name, is_admin)

        print(f"\n{'='*60}")
        print(f"✅ API Key Created Successfully")
        print(f"{'='*60}")
        print(f"ID:          {row['id']}")
        print(f"Name:        {name}")
        print(f"Admin:       {'Yes' if is_admin else 'No'}")
        print(f"Created:     {row['created_at']}")
        print(f"\n{'='*60}")
        print(f"🔑 API KEY (save this - it won't be shown again!):")
        print(f"{'='*60}")
        print(f"{api_key}")
        print(f"{'='*60}\n")

        print("Usage:")
        print(f'  curl -H "X-API-Key: {api_key}" https://api.verdegris.eu/api/v1/spaces\n')

    finally:
        await conn.close()


async def list_api_keys():
    """List all API keys"""
    conn = await asyncpg.connect(settings.database_url)

    try:
        rows = await conn.fetch("""
            SELECT
                id,
                key_name,
                is_admin,
                is_active,
                created_at,
                last_used_at
            FROM api_keys
            ORDER BY created_at DESC
        """)

        print(f"\n{'='*100}")
        print(f"API Keys")
        print(f"{'='*100}")
        print(f"{'ID':<38} {'Name':<25} {'Admin':<8} {'Active':<8} {'Last Used':<20}")
        print(f"{'-'*100}")

        for row in rows:
            last_used = row['last_used_at'].strftime('%Y-%m-%d %H:%M') if row['last_used_at'] else 'Never'
            admin_mark = '✓' if row['is_admin'] else '-'
            active_mark = '✓' if row['is_active'] else '✗'

            print(f"{str(row['id']):<38} {row['key_name']:<25} {admin_mark:<8} {active_mark:<8} {last_used:<20}")

        print(f"{'='*100}\n")
        print(f"Total: {len(rows)} keys\n")

    finally:
        await conn.close()


async def revoke_api_key(key_id: str):
    """Revoke an API key"""
    conn = await asyncpg.connect(settings.database_url)

    try:
        # Check if key exists
        row = await conn.fetchrow("""
            SELECT key_name, is_active FROM api_keys WHERE id = $1
        """, key_id)

        if not row:
            print(f"❌ Error: API key {key_id} not found")
            return

        if not row['is_active']:
            print(f"⚠️  Warning: API key '{row['key_name']}' is already revoked")
            return

        # Revoke key
        await conn.execute("""
            UPDATE api_keys
            SET is_active = false
            WHERE id = $1
        """, key_id)

        print(f"✅ API key '{row['key_name']}' has been revoked")

    finally:
        await conn.close()


async def activate_api_key(key_id: str):
    """Activate a revoked API key"""
    conn = await asyncpg.connect(settings.database_url)

    try:
        # Check if key exists
        row = await conn.fetchrow("""
            SELECT key_name, is_active FROM api_keys WHERE id = $1
        """, key_id)

        if not row:
            print(f"❌ Error: API key {key_id} not found")
            return

        if row['is_active']:
            print(f"⚠️  Warning: API key '{row['key_name']}' is already active")
            return

        # Activate key
        await conn.execute("""
            UPDATE api_keys
            SET is_active = true
            WHERE id = $1
        """, key_id)

        print(f"✅ API key '{row['key_name']}' has been activated")

    finally:
        await conn.close()


async def test_api_key(api_key: str):
    """Test an API key"""
    from src.auth import verify_api_key, set_db_pool
    from src.database import DatabasePool

    # Initialize database pool
    db_pool = DatabasePool(settings.database_url)
    await db_pool.initialize()
    set_db_pool(db_pool)

    # Test key
    key_info = await verify_api_key(api_key)

    if key_info:
        print(f"✅ Valid API Key")
        print(f"   Name: {key_info.name}")
        print(f"   ID: {key_info.id}")
        print(f"   Admin: {'Yes' if key_info.is_admin else 'No'}")
    else:
        print(f"❌ Invalid API Key")

    await db_pool.close()


def main():
    parser = argparse.ArgumentParser(description="Manage API Keys")
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')

    # Create command
    create_parser = subparsers.add_parser('create', help='Create a new API key')
    create_parser.add_argument('name', help='Name/description for the key')
    create_parser.add_argument('--admin', action='store_true', help='Create admin key')

    # List command
    subparsers.add_parser('list', help='List all API keys')

    # Revoke command
    revoke_parser = subparsers.add_parser('revoke', help='Revoke an API key')
    revoke_parser.add_argument('key_id', help='ID of key to revoke')

    # Activate command
    activate_parser = subparsers.add_parser('activate', help='Activate a revoked API key')
    activate_parser.add_argument('key_id', help='ID of key to activate')

    # Test command
    test_parser = subparsers.add_parser('test', help='Test an API key')
    test_parser.add_argument('api_key', help='API key to test')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Run command
    if args.command == 'create':
        asyncio.run(create_api_key(args.name, args.admin))
    elif args.command == 'list':
        asyncio.run(list_api_keys())
    elif args.command == 'revoke':
        asyncio.run(revoke_api_key(args.key_id))
    elif args.command == 'activate':
        asyncio.run(activate_api_key(args.key_id))
    elif args.command == 'test':
        asyncio.run(test_api_key(args.api_key))


if __name__ == '__main__':
    main()
