"""
Audit Logging System

Provides append-only audit trail for all tenant actions.
Implements "who did what, when, on which tenant" tracking.

Features:
- Immutable audit log (prevented by database trigger)
- Tenant isolation (all logs scoped to tenant_id)
- Actor tracking (user, API key, system, webhook)
- Resource change tracking (old/new values)
- Request correlation (request_id)
"""
import logging
from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime
from ipaddress import IPv4Address, IPv6Address

logger = logging.getLogger(__name__)


class AuditLogger:
    """
    Audit logging service

    Usage:
        audit = AuditLogger(db_pool)
        await audit.log_action(
            tenant_id=tenant_id,
            action="space.create",
            resource_type="space",
            resource_id=space_id,
            actor_type="user",
            user_id=user_id,
            new_values={"code": "A-101", "state": "free"}
        )
    """

    def __init__(self, db_pool):
        self.db_pool = db_pool

    async def log_action(
        self,
        tenant_id: UUID,
        action: str,
        resource_type: str,
        actor_type: str,
        resource_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None,
        api_key_id: Optional[UUID] = None,
        actor_name: Optional[str] = None,
        old_values: Optional[Dict[str, Any]] = None,
        new_values: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_id: Optional[str] = None,
        success: bool = True,
        error_message: Optional[str] = None
    ) -> UUID:
        """
        Log an action to the audit trail

        Args:
            tenant_id: Tenant UUID
            action: Action performed (e.g., "space.create", "reservation.delete")
            resource_type: Type of resource (e.g., "space", "reservation")
            actor_type: Type of actor ('user', 'api_key', 'system', 'webhook')
            resource_id: ID of affected resource
            user_id: User ID (if actor is user)
            api_key_id: API key ID (if actor is API key)
            actor_name: Display name of actor
            old_values: Previous state (for updates/deletes)
            new_values: New state (for creates/updates)
            metadata: Additional context
            ip_address: Client IP address
            user_agent: Client user agent
            request_id: Request correlation ID
            success: Whether action succeeded
            error_message: Error message if failed

        Returns:
            Audit log entry ID
        """
        try:
            # Convert dict to JSONB-compatible format
            import json

            async with self.db_pool.acquire() as conn:
                audit_id = await conn.fetchval("""
                    SELECT log_audit_event(
                        $1, $2, $3, $4, $5, $6, $7, $8,
                        $9::jsonb, $10::jsonb, $11::jsonb,
                        $12::inet, $13, $14, $15, $16
                    )
                """,
                    tenant_id,
                    user_id,
                    api_key_id,
                    actor_type,
                    actor_name,
                    action,
                    resource_type,
                    resource_id,
                    json.dumps(old_values) if old_values else None,
                    json.dumps(new_values) if new_values else None,
                    json.dumps(metadata) if metadata else None,
                    ip_address,
                    user_agent,
                    request_id,
                    success,
                    error_message
                )

                logger.info(
                    f"Audit: {action} by {actor_type} on {resource_type}:{resource_id} "
                    f"(tenant={tenant_id}, audit_id={audit_id})"
                )

                return audit_id

        except Exception as e:
            # Log error but don't fail the operation
            logger.error(f"Failed to write audit log: {e}", exc_info=True)
            # Re-raise to signal failure to caller
            raise

    async def log_user_action(
        self,
        tenant_id: UUID,
        user_id: UUID,
        user_email: str,
        action: str,
        resource_type: str,
        resource_id: Optional[UUID] = None,
        old_values: Optional[Dict[str, Any]] = None,
        new_values: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
        success: bool = True
    ) -> UUID:
        """Convenience method for logging user actions"""
        return await self.log_action(
            tenant_id=tenant_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=user_id,
            actor_type="user",
            actor_name=user_email,
            old_values=old_values,
            new_values=new_values,
            request_id=request_id,
            success=success
        )

    async def log_api_key_action(
        self,
        tenant_id: UUID,
        api_key_id: UUID,
        api_key_name: str,
        action: str,
        resource_type: str,
        resource_id: Optional[UUID] = None,
        new_values: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
        success: bool = True
    ) -> UUID:
        """Convenience method for logging API key actions"""
        return await self.log_action(
            tenant_id=tenant_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            api_key_id=api_key_id,
            actor_type="api_key",
            actor_name=api_key_name,
            new_values=new_values,
            request_id=request_id,
            success=success
        )

    async def log_system_action(
        self,
        tenant_id: UUID,
        action: str,
        resource_type: str,
        system_name: str = "background_worker",
        resource_id: Optional[UUID] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> UUID:
        """Convenience method for logging system/background actions"""
        return await self.log_action(
            tenant_id=tenant_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            actor_type="system",
            actor_name=system_name,
            metadata=metadata
        )

    async def get_tenant_audit_log(
        self,
        tenant_id: UUID,
        limit: int = 100,
        offset: int = 0,
        action_filter: Optional[str] = None,
        resource_type_filter: Optional[str] = None,
        user_id_filter: Optional[UUID] = None
    ) -> list:
        """
        Retrieve audit log for a tenant

        Args:
            tenant_id: Tenant UUID
            limit: Max records to return
            offset: Pagination offset
            action_filter: Filter by action (e.g., "space.delete")
            resource_type_filter: Filter by resource type
            user_id_filter: Filter by user

        Returns:
            List of audit log entries
        """
        try:
            conditions = ["tenant_id = $1"]
            params = [tenant_id]
            param_idx = 2

            if action_filter:
                conditions.append(f"action = ${param_idx}")
                params.append(action_filter)
                param_idx += 1

            if resource_type_filter:
                conditions.append(f"resource_type = ${param_idx}")
                params.append(resource_type_filter)
                param_idx += 1

            if user_id_filter:
                conditions.append(f"user_id = ${param_idx}")
                params.append(user_id_filter)
                param_idx += 1

            where_clause = " AND ".join(conditions)

            query = f"""
                SELECT
                    id, created_at, tenant_id, user_id, api_key_id,
                    actor_type, actor_name, action, resource_type, resource_id,
                    old_values, new_values, metadata,
                    ip_address, user_agent, request_id,
                    success, error_message
                FROM audit_log
                WHERE {where_clause}
                ORDER BY created_at DESC
                LIMIT ${param_idx} OFFSET ${param_idx + 1}
            """

            params.extend([limit, offset])

            async with self.db_pool.acquire() as conn:
                rows = await conn.fetch(query, *params)

                return [
                    {
                        "id": str(row["id"]),
                        "created_at": row["created_at"].isoformat(),
                        "actor_type": row["actor_type"],
                        "actor_name": row["actor_name"],
                        "action": row["action"],
                        "resource_type": row["resource_type"],
                        "resource_id": str(row["resource_id"]) if row["resource_id"] else None,
                        "old_values": row["old_values"],
                        "new_values": row["new_values"],
                        "metadata": row["metadata"],
                        "success": row["success"],
                        "error_message": row["error_message"],
                        "request_id": row["request_id"]
                    }
                    for row in rows
                ]

        except Exception as e:
            logger.error(f"Failed to retrieve audit log: {e}", exc_info=True)
            return []


# Global audit logger instance (initialized in main.py)
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> Optional[AuditLogger]:
    """Get global audit logger instance"""
    return _audit_logger


def set_audit_logger(audit_logger: AuditLogger):
    """Set global audit logger instance"""
    global _audit_logger
    _audit_logger = audit_logger
