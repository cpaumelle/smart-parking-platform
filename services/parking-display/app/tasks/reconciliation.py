"""
State Reconciliation Task
Periodically verifies and corrects display states across all parking spaces
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict
import sys
sys.path.append("/app")

from app.database import get_db
from app.services.state_engine import ParkingStateEngine
from app.services.downlink_client import DownlinkClient
from app.services.rejoin_detector import RejoinDetector
from app.models import ParkingState

logger = logging.getLogger("reconciliation")

class StateReconciliation:
    """Periodic state reconciliation to ensure displays show correct state"""
    
    def __init__(self, interval_minutes: int = 10):
        self.interval_minutes = interval_minutes
        self.downlink_client = DownlinkClient()
        self.stats = {
            "total_checks": 0,
            "reconciliations_sent": 0,
            "rejoins_detected": 0,
            "errors": 0
        }
    
    async def run_forever(self):
        """Main reconciliation loop"""
        logger.info(f"🔄 State reconciliation task started (interval: {self.interval_minutes} min)")
        
        while True:
            try:
                await self.reconcile_all_spaces()
                await asyncio.sleep(self.interval_minutes * 60)
            except Exception as e:
                logger.error(f"Error in reconciliation loop: {e}", exc_info=True)
                await asyncio.sleep(60)  # Wait 1 min before retrying
    
    async def reconcile_all_spaces(self):
        """Check and reconcile all enabled parking spaces"""
        start_time = datetime.utcnow()
        
        async with get_db() as db:
            try:
                # Get all enabled spaces with displays
                spaces = await db.fetch("""
                    SELECT 
                        s.space_id,
                        s.space_name,
                        s.current_state,
                        s.sensor_state,
                        s.display_device_deveui,
                        dr.display_codes,
                        dr.fport,
                        dr.confirmed_downlinks,
                        s.auto_actuation,
                        s.maintenance_mode,
                        s.last_display_update,
                        s.last_sensor_update,
                        dr.last_uplink_at,
                        dr.last_dev_addr,
                        dr.last_fcnt
                    FROM parking_spaces.spaces s
                    JOIN parking_config.display_registry dr 
                        ON s.display_device_deveui = dr.dev_eui
                    WHERE s.enabled = TRUE
                      AND s.auto_actuation = TRUE
                      AND dr.enabled = TRUE
                """)
                
                logger.info(f"🔍 Checking {len(spaces)} spaces for reconciliation")
                
                for space in spaces:
                    await self.reconcile_space(space, db)
                
                self.stats["total_checks"] += len(spaces)
                
                elapsed = (datetime.utcnow() - start_time).total_seconds()
                logger.info(
                    f"✅ Reconciliation complete: {len(spaces)} spaces checked in {elapsed:.1f}s "
                    f"(sent: {self.stats['reconciliations_sent']}, "
                    f"rejoins: {self.stats['rejoins_detected']}, "
                    f"errors: {self.stats['errors']})"
                )
                
            except Exception as e:
                logger.error(f"Error in reconcile_all_spaces: {e}", exc_info=True)
                self.stats["errors"] += 1
    
    async def reconcile_space(self, space: Dict, db):
        """Reconcile a single parking space"""
        try:
            space_id = str(space["space_id"])
            space_name = space["space_name"]
            dev_eui = space["display_device_deveui"]
            
            # Determine expected display state
            state_result = await ParkingStateEngine.determine_display_state(
                space_id=space_id,
                sensor_state=ParkingState(space["current_state"]),
                db_connection=db
            )
            
            expected_state = state_result["display_state"]
            last_display_update = space["last_display_update"]
            
            # Decide if reconciliation is needed
            should_reconcile = False
            reconcile_reason = None
            
            # Reason 1: No recent display update (>15 minutes)
            if not last_display_update or (datetime.utcnow() - last_display_update) > timedelta(minutes=15):
                should_reconcile = True
                reconcile_reason = "stale_display_update"
            
            # Reason 2: Display hasn't been seen recently (>20 minutes)
            elif space["last_uplink_at"] and (datetime.utcnow() - space["last_uplink_at"]) > timedelta(minutes=20):
                should_reconcile = True
                reconcile_reason = "display_not_seen"
            
            # Reason 3: Sensor state differs from current state (potential missed actuation)
            elif space["sensor_state"] and space["sensor_state"] != space["current_state"]:
                should_reconcile = True
                reconcile_reason = "state_mismatch"
            
            if should_reconcile:
                logger.info(f"🔧 Reconciling {space_name}: {reconcile_reason} (expected: {expected_state.value})")
                
                # Send downlink
                display_code = ParkingStateEngine.get_display_code(expected_state, space["display_codes"])
                result = await self.downlink_client.send_downlink(
                    dev_eui=dev_eui,
                    fport=space["fport"],
                    data=display_code,
                    confirmed=space["confirmed_downlinks"]
                )
                
                # Log reconciliation actuation
                actuation_id = await ParkingStateEngine.log_actuation(
                    space_id=space_id,
                    trigger_type="reconciliation",
                    trigger_source="periodic_task",
                    trigger_data={"reason": reconcile_reason},
                    previous_state=space["current_state"],
                    new_state=expected_state,
                    display_deveui=dev_eui,
                    display_code=display_code,
                    db_connection=db
                )
                
                # Update actuation result
                await db.execute("""
                    UPDATE parking_operations.actuations
                    SET downlink_sent = $1,
                        response_time_ms = $2,
                        downlink_error = $3,
                        sent_at = NOW()
                    WHERE actuation_id = $4
                """,
                    result["success"],
                    result["response_time_ms"],
                    result["error"],
                    actuation_id
                )
                
                if result["success"]:
                    # Update display state
                    await db.execute("""
                        UPDATE parking_spaces.spaces
                        SET last_display_update = NOW(),
                            updated_at = NOW()
                        WHERE space_id = $1
                    """, space["space_id"])
                    
                    self.stats["reconciliations_sent"] += 1
                    logger.info(f"✅ Reconciled {space_name} successfully")
                else:
                    logger.error(f"❌ Failed to reconcile {space_name}: {result['error']}")
                    self.stats["errors"] += 1
            
        except Exception as e:
            logger.error(f"Error reconciling space {space.get('space_name', 'unknown')}: {e}", exc_info=True)
            self.stats["errors"] += 1


async def start_reconciliation_task(interval_minutes: int = 10):
    """Start the state reconciliation background task"""
    reconciliation = StateReconciliation(interval_minutes=interval_minutes)
    await reconciliation.run_forever()
