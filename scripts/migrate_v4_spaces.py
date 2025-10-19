#!/usr/bin/env python3
"""
Migrate parking spaces from v4 (parking_platform) to v5 (parking_v2)

Usage:
    python scripts/migrate_v4_spaces.py [--dry-run] [--include-archived]
"""
import asyncio
import sys
import argparse
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncpg
from src.config import settings

# V4 to V5 state mapping
STATE_MAPPING = {
    'FREE': 'FREE',
    'OCCUPIED': 'OCCUPIED',
    'RESERVED': 'RESERVED',
    'MAINTENANCE': 'FREE',  # Map maintenance to FREE in v5
}


async def migrate_spaces(dry_run: bool = False, include_archived: bool = False):
    """Migrate parking spaces from v4 to v5"""

    print("=" * 80)
    print("Parking Space Migration: v4 → v5")
    print("=" * 80)
    print(f"Mode: {'DRY RUN (no changes)' if dry_run else 'LIVE MIGRATION'}")
    print(f"Include archived: {include_archived}")
    print()

    # Connect to both databases
    v4_conn = await asyncpg.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        user=settings.postgres_user,
        password=settings.postgres_password,
        database='parking_platform'
    )

    v5_conn = await asyncpg.connect(settings.database_url)

    try:
        # Fetch spaces from v4
        query = """
            SELECT
                space_id,
                space_name,
                space_code,
                location_description,
                building,
                floor,
                zone,
                gps_latitude,
                gps_longitude,
                occupancy_sensor_deveui,
                display_device_deveui,
                current_state,
                enabled,
                archived,
                maintenance_mode,
                space_metadata,
                notes,
                created_at,
                updated_at
            FROM parking_spaces.spaces
            WHERE archived = false AND enabled = true
        """

        if include_archived:
            query = query.replace("WHERE archived = false AND enabled = true", "")

        v4_spaces = await v4_conn.fetch(query + " ORDER BY space_code")

        print(f"Found {len(v4_spaces)} spaces in v4 database")
        print()

        # Check existing spaces in v5
        existing_v5_spaces = await v5_conn.fetch("SELECT code FROM spaces")
        existing_codes = {row['code'] for row in existing_v5_spaces}

        print(f"Existing spaces in v5: {len(existing_codes)}")
        if existing_codes:
            print(f"  Codes: {', '.join(sorted(existing_codes))}")
        print()

        # Migrate each space
        migrated_count = 0
        skipped_count = 0
        updated_count = 0

        for space in v4_spaces:
            space_code = space['space_code']
            space_name = space['space_name']

            # Check if already exists
            if space_code in existing_codes:
                print(f"⚠️  SKIP: {space_code} - {space_name} (already exists in v5)")
                skipped_count += 1
                continue

            # Prepare v5 data
            sensor_eui = space['occupancy_sensor_deveui']
            display_eui = space['display_device_deveui']

            # Map state
            v4_state = space['current_state'] or 'FREE'
            v5_state = STATE_MAPPING.get(v4_state, 'FREE')

            # Build metadata
            metadata = space['space_metadata'] or {}
            if space['location_description']:
                metadata['description'] = space['location_description']
            if space['notes']:
                metadata['notes'] = space['notes']
            if space['maintenance_mode']:
                metadata['maintenance_mode'] = True

            # Display migration info
            status = "🔄 MIGRATE" if not dry_run else "📋 WOULD MIGRATE"
            print(f"{status}: {space_code} - {space_name}")
            print(f"  Building: {space['building']}, Floor: {space['floor']}, Zone: {space['zone']}")
            print(f"  Sensor: {sensor_eui or 'None'}")
            print(f"  Display: {display_eui or 'None'}")
            print(f"  State: {v4_state} → {v5_state}")

            if not dry_run:
                # Insert into v5
                await v5_conn.execute("""
                    INSERT INTO spaces (
                        id, name, code, building, floor, zone,
                        gps_latitude, gps_longitude,
                        sensor_eui, display_eui,
                        state, metadata,
                        created_at, updated_at
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6,
                        $7, $8,
                        $9, $10,
                        $11::space_state, $12,
                        $13, $14
                    )
                """,
                    space['space_id'],
                    space_name,
                    space_code,
                    space['building'],
                    space['floor'],
                    space['zone'],
                    space['gps_latitude'],
                    space['gps_longitude'],
                    sensor_eui,
                    display_eui,
                    v5_state,
                    metadata,
                    space['created_at'],
                    space['updated_at']
                )
                print(f"  ✅ Migrated successfully")
                migrated_count += 1
            else:
                print(f"  📋 Would be migrated")

            print()

        # Summary
        print("=" * 80)
        print("Migration Summary")
        print("=" * 80)
        print(f"Total v4 spaces found: {len(v4_spaces)}")
        print(f"Skipped (already exist): {skipped_count}")

        if dry_run:
            print(f"Would migrate: {len(v4_spaces) - skipped_count}")
        else:
            print(f"Successfully migrated: {migrated_count}")
            print(f"Failed: {len(v4_spaces) - skipped_count - migrated_count}")

        print()

        # Show final v5 state
        if not dry_run:
            final_spaces = await v5_conn.fetch("""
                SELECT code, name, sensor_eui, display_eui, state
                FROM spaces
                ORDER BY code
            """)

            print("Final v5 spaces:")
            print("-" * 80)
            for s in final_spaces:
                sensor = s['sensor_eui'] or 'no sensor'
                display = s['display_eui'] or 'no display'
                print(f"  {s['code']}: {s['name']} - {s['state']} (sensor: {sensor[-4:]}, display: {display[-6:]})")

        print()

    finally:
        await v4_conn.close()
        await v5_conn.close()


def main():
    parser = argparse.ArgumentParser(description="Migrate parking spaces from v4 to v5")
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be migrated without making changes')
    parser.add_argument('--include-archived', action='store_true',
                       help='Include archived/disabled spaces')

    args = parser.parse_args()

    if not args.dry_run:
        print()
        print("⚠️  WARNING: This will modify the v5 database!")
        response = input("Continue? (yes/no): ")
        if response.lower() != 'yes':
            print("Migration cancelled")
            return
        print()

    asyncio.run(migrate_spaces(dry_run=args.dry_run, include_archived=args.include_archived))


if __name__ == '__main__':
    main()
