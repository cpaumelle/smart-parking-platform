# src/routers/downlink_monitor.py
# Downlink Queue Monitoring API

from fastapi import APIRouter, Request, HTTPException, status
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/downlinks", tags=["downlinks"])


@router.get("/queue/metrics", response_model=Dict[str, Any])
async def get_queue_metrics(request: Request):
    """
    Get downlink queue metrics

    Returns:
    - Queue depths (pending, dead-letter)
    - Throughput counters (enqueued, succeeded, failed)
    - Success rate
    - Latency percentiles (p50, p99)
    - Deduplication stats
    """
    try:
        if not hasattr(request.app.state, 'downlink_queue'):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Downlink queue not available"
            )

        downlink_queue = request.app.state.downlink_queue
        metrics = await downlink_queue.get_metrics()

        return {
            "queue": {
                "pending_depth": metrics["queue_depth"],
                "dead_letter_depth": metrics["dead_letter_depth"]
            },
            "throughput": {
                "total_enqueued": metrics["total_enqueued"],
                "total_succeeded": metrics["total_succeeded"],
                "total_retried": metrics["total_retried"],
                "total_dead_lettered": metrics["total_dead_lettered"],
                "total_deduplicated": metrics["total_deduplicated"],
                "total_coalesced": metrics["total_coalesced"]
            },
            "performance": {
                "success_rate_percent": round(metrics["success_rate"], 2),
                "latency_p50_ms": metrics["latency_p50_ms"],
                "latency_p99_ms": metrics["latency_p99_ms"]
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get queue metrics: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/queue/health", response_model=Dict[str, Any])
async def get_queue_health(request: Request):
    """
    Get downlink queue health status

    Returns:
    - Status: healthy/degraded/unhealthy
    - Queue depth warnings
    - Dead-letter queue warnings
    """
    try:
        if not hasattr(request.app.state, 'downlink_queue'):
            return {
                "status": "unavailable",
                "message": "Downlink queue not configured"
            }

        downlink_queue = request.app.state.downlink_queue
        metrics = await downlink_queue.get_metrics()

        # Health thresholds
        QUEUE_DEPTH_WARNING = 100
        QUEUE_DEPTH_CRITICAL = 500
        DEAD_LETTER_WARNING = 10
        SUCCESS_RATE_WARNING = 90.0

        warnings = []
        status_level = "healthy"

        # Check queue depth
        if metrics["queue_depth"] > QUEUE_DEPTH_CRITICAL:
            warnings.append(f"Queue depth critical: {metrics['queue_depth']} pending commands")
            status_level = "unhealthy"
        elif metrics["queue_depth"] > QUEUE_DEPTH_WARNING:
            warnings.append(f"Queue depth elevated: {metrics['queue_depth']} pending commands")
            status_level = "degraded"

        # Check dead-letter queue
        if metrics["dead_letter_depth"] > DEAD_LETTER_WARNING:
            warnings.append(f"Dead-letter queue accumulating: {metrics['dead_letter_depth']} failed commands")
            if status_level == "healthy":
                status_level = "degraded"

        # Check success rate
        if metrics["total_enqueued"] > 10 and metrics["success_rate"] < SUCCESS_RATE_WARNING:
            warnings.append(f"Low success rate: {metrics['success_rate']:.1f}%")
            if status_level == "healthy":
                status_level = "degraded"

        return {
            "status": status_level,
            "queue_depth": metrics["queue_depth"],
            "dead_letter_depth": metrics["dead_letter_depth"],
            "success_rate_percent": round(metrics["success_rate"], 2),
            "warnings": warnings,
            "message": warnings[0] if warnings else "Queue operating normally"
        }

    except Exception as e:
        logger.error(f"Failed to get queue health: {e}", exc_info=True)
        return {
            "status": "error",
            "message": str(e)
        }


@router.post("/queue/clear-metrics")
async def clear_queue_metrics(request: Request):
    """
    Clear queue metrics (for testing/debugging)

    Requires admin authentication
    """
    try:
        if not hasattr(request.app.state, 'downlink_queue'):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Downlink queue not available"
            )

        downlink_queue = request.app.state.downlink_queue
        await downlink_queue.clear_metrics()

        return {
            "status": "success",
            "message": "Queue metrics cleared"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to clear queue metrics: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
