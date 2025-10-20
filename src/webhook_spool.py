"""
Webhook File Spool for Back-Pressure Handling

When the database is slow or unavailable, uplinks are buffered to disk
in /var/spool/parking-uplinks/ and retried with exponential backoff.

This prevents data loss during database outages or high load scenarios.
"""
import asyncio
import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)

SPOOL_DIR = Path("/var/spool/parking-uplinks")
MAX_RETRY_ATTEMPTS = 5
INITIAL_BACKOFF_SECONDS = 2
MAX_BACKOFF_SECONDS = 300  # 5 minutes


class WebhookSpool:
    """
    File-based spool for webhook payloads during back-pressure scenarios

    Features:
    - Disk-based buffering when database is slow/unavailable
    - Exponential backoff retry (2s, 4s, 8s, 16s, 32s, up to 5 min)
    - Dead-letter queue for persistent failures
    - Background worker to drain spool
    """

    def __init__(self, spool_dir: Path = SPOOL_DIR):
        self.spool_dir = spool_dir
        self.pending_dir = spool_dir / "pending"
        self.processing_dir = spool_dir / "processing"
        self.dead_letter_dir = spool_dir / "dead-letter"
        self.running = False
        self.worker_task: Optional[asyncio.Task] = None

        # Create directories
        for dir_path in [self.pending_dir, self.processing_dir, self.dead_letter_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)

        logger.info(f"Webhook spool initialized at {spool_dir}")

    async def enqueue(
        self,
        webhook_data: Dict[str, Any],
        device_eui: str,
        request_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Enqueue webhook payload to file spool

        Returns:
            Spool file ID (UUID)
        """
        try:
            spool_id = str(uuid4())
            spool_file = self.pending_dir / f"{spool_id}.json"

            envelope = {
                "id": spool_id,
                "device_eui": device_eui,
                "request_id": request_id,
                "enqueued_at": datetime.utcnow().isoformat(),
                "retry_count": 0,
                "next_retry_at": datetime.utcnow().isoformat(),
                "webhook_data": webhook_data,
                "metadata": metadata or {}
            }

            # Write atomically using temp file + rename
            temp_file = spool_file.with_suffix(".tmp")
            with open(temp_file, "w") as f:
                json.dump(envelope, f, indent=2)

            temp_file.rename(spool_file)

            logger.info(f"Enqueued webhook to spool: {spool_id} (device: {device_eui})")
            return spool_id

        except Exception as e:
            logger.error(f"Failed to enqueue webhook to spool: {e}", exc_info=True)
            raise

    async def start_worker(self):
        """Start background worker to drain spool"""
        if self.running:
            logger.warning("Spool worker already running")
            return

        self.running = True
        self.worker_task = asyncio.create_task(self._worker_loop())
        logger.info("Spool worker started")

    async def stop_worker(self):
        """Stop background worker gracefully"""
        if not self.running:
            return

        self.running = False
        if self.worker_task:
            await self.worker_task

        logger.info("Spool worker stopped")

    async def _worker_loop(self):
        """Background worker that drains the spool"""
        while self.running:
            try:
                await self._process_pending_files()
                await asyncio.sleep(5)  # Check every 5 seconds
            except Exception as e:
                logger.error(f"Spool worker error: {e}", exc_info=True)
                await asyncio.sleep(10)  # Back off on error

    async def _process_pending_files(self):
        """Process all pending spool files ready for retry"""
        now = datetime.utcnow()

        # Find files ready for retry
        for spool_file in sorted(self.pending_dir.glob("*.json")):
            try:
                # Read envelope
                with open(spool_file, "r") as f:
                    envelope = json.load(f)

                # Check if ready for retry
                next_retry_at = datetime.fromisoformat(envelope["next_retry_at"])
                if next_retry_at > now:
                    continue  # Not ready yet

                # Move to processing
                processing_file = self.processing_dir / spool_file.name
                spool_file.rename(processing_file)

                # Process the webhook
                success = await self._process_envelope(envelope)

                if success:
                    # Delete processed file
                    processing_file.unlink()
                    logger.info(f"Successfully processed spooled webhook: {envelope['id']}")
                else:
                    # Increment retry count and schedule next retry
                    envelope["retry_count"] += 1

                    if envelope["retry_count"] >= MAX_RETRY_ATTEMPTS:
                        # Move to dead-letter queue
                        dead_letter_file = self.dead_letter_dir / spool_file.name
                        with open(dead_letter_file, "w") as f:
                            json.dump(envelope, f, indent=2)
                        processing_file.unlink()

                        logger.error(
                            f"Webhook {envelope['id']} moved to dead-letter queue "
                            f"after {MAX_RETRY_ATTEMPTS} attempts"
                        )
                    else:
                        # Calculate next retry time with exponential backoff
                        backoff = min(
                            INITIAL_BACKOFF_SECONDS * (2 ** envelope["retry_count"]),
                            MAX_BACKOFF_SECONDS
                        )
                        envelope["next_retry_at"] = (
                            datetime.utcnow().timestamp() + backoff
                        )
                        envelope["next_retry_at"] = datetime.fromtimestamp(
                            envelope["next_retry_at"]
                        ).isoformat()

                        # Move back to pending
                        with open(spool_file, "w") as f:
                            json.dump(envelope, f, indent=2)
                        processing_file.rename(spool_file)

                        logger.warning(
                            f"Webhook {envelope['id']} retry scheduled in {backoff}s "
                            f"(attempt {envelope['retry_count']}/{MAX_RETRY_ATTEMPTS})"
                        )

            except Exception as e:
                logger.error(f"Error processing spool file {spool_file.name}: {e}", exc_info=True)

    async def _process_envelope(self, envelope: Dict[str, Any]) -> bool:
        """
        Process a spooled webhook envelope

        Returns:
            True if processing succeeded, False if retry needed

        Note:
            This is a stub - actual implementation should call process_uplink()
            or database insert functions
        """
        # This will be implemented by injecting a callback function
        # For now, return False to indicate retry needed
        logger.warning(f"Spool processing not fully implemented for {envelope['id']}")
        return False

    def get_stats(self) -> Dict[str, int]:
        """Get spool statistics"""
        return {
            "pending": len(list(self.pending_dir.glob("*.json"))),
            "processing": len(list(self.processing_dir.glob("*.json"))),
            "dead_letter": len(list(self.dead_letter_dir.glob("*.json")))
        }


# Global spool instance (initialized in main.py)
_spool_instance: Optional[WebhookSpool] = None


def get_spool() -> Optional[WebhookSpool]:
    """Get global spool instance"""
    return _spool_instance


def set_spool(spool: WebhookSpool):
    """Set global spool instance"""
    global _spool_instance
    _spool_instance = spool


async def spool_webhook_on_error(
    webhook_data: Dict[str, Any],
    device_eui: str,
    request_id: str,
    error: Exception
) -> bool:
    """
    Spool webhook to disk if database operation failed

    Returns:
        True if spooled successfully, False otherwise
    """
    spool = get_spool()
    if not spool:
        logger.error("Spool not available - webhook lost!")
        return False

    try:
        await spool.enqueue(
            webhook_data=webhook_data,
            device_eui=device_eui,
            request_id=request_id,
            metadata={"error": str(error), "error_type": type(error).__name__}
        )
        logger.info(f"Webhook spooled due to error: {error}")
        return True
    except Exception as e:
        logger.error(f"Failed to spool webhook: {e}", exc_info=True)
        return False
