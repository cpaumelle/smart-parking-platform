"""
Background Task Statistics Registry

Provides centralized monitoring and health tracking for background tasks.
Used by reconciliation, expiry, and other async tasks.
"""
from datetime import datetime, timezone
from typing import Dict, Any
import asyncio
import logging

logger = logging.getLogger("monitoring.stats")


class TaskStatsRegistry:
    """Central registry for background task statistics"""
    
    def __init__(self):
        self._stats: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()
    
    async def register_task(self, task_name: str):
        """Register a new background task"""
        async with self._lock:
            self._stats[task_name] = {
                "started_at": datetime.now(timezone.utc),
                "last_run": None,
                "total_runs": 0,
                "total_errors": 0,
                "last_error": None,
                "last_error_at": None,
                "custom_metrics": {}
            }
            logger.info(f"📊 Registered task: {task_name}")
    
    async def update_stats(
        self,
        task_name: str,
        success: bool = True,
        error_message: str = None,
        custom_metrics: Dict[str, Any] = None
    ):
        """Update task statistics after a run"""
        async with self._lock:
            if task_name not in self._stats:
                await self.register_task(task_name)
            
            stats = self._stats[task_name]
            stats["last_run"] = datetime.now(timezone.utc)
            stats["total_runs"] += 1
            
            if not success:
                stats["total_errors"] += 1
                stats["last_error"] = error_message
                stats["last_error_at"] = datetime.now(timezone.utc)
                logger.warning(f"⚠️ Task {task_name} error: {error_message}")
            
            if custom_metrics:
                stats["custom_metrics"].update(custom_metrics)
    
    async def get_stats(self, task_name: str = None) -> Dict[str, Any]:
        """Get stats for specific task or all tasks"""
        async with self._lock:
            if task_name:
                return self._stats.get(task_name, {})
            return self._stats.copy()
    
    async def get_health_summary(self) -> Dict[str, Any]:
        """Get health summary for all tasks"""
        async with self._lock:
            summary = {
                "total_tasks": len(self._stats),
                "healthy_tasks": 0,
                "unhealthy_tasks": 0,
                "tasks": {}
            }
            
            for task_name, stats in self._stats.items():
                error_rate = (
                    stats["total_errors"] / stats["total_runs"]
                    if stats["total_runs"] > 0
                    else 0
                )
                
                # Healthy if error rate < 10%
                is_healthy = error_rate < 0.1
                
                if is_healthy:
                    summary["healthy_tasks"] += 1
                else:
                    summary["unhealthy_tasks"] += 1
                
                summary["tasks"][task_name] = {
                    "status": "healthy" if is_healthy else "unhealthy",
                    "error_rate": f"{error_rate:.2%}",
                    "total_runs": stats["total_runs"],
                    "total_errors": stats["total_errors"],
                    "last_run": stats["last_run"].isoformat() if stats["last_run"] else None,
                    "last_error": stats["last_error"],
                    "custom_metrics": stats["custom_metrics"]
                }
            
            return summary


# Global registry instance (singleton)
_stats_registry = TaskStatsRegistry()


def get_stats_registry() -> TaskStatsRegistry:
    """Get the global stats registry (singleton)"""
    return _stats_registry
