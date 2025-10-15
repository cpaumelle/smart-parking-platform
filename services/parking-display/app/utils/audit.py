"""
Audit Logging Module
====================
Records security-critical events for compliance and security monitoring.

Event Types:
- Authentication (success/failure)
- API key operations (create/revoke/rotate)
- Tenant isolation violations
- Administrative actions
"""

import logging
from typing import Optional, Dict, Any
from uuid import UUID
import asyncio

logger = logging.getLogger("audit")


class AuditLogger:
    """
    Audit logger for security events.
    
    All methods are async and non-blocking.
    """
    
    @staticmethod
    async def log_event(
        db_pool,
        event_type: str,
        severity: str,
        tenant_id: Optional[UUID],
        event_description: str,
        api_key_id: Optional[UUID] = None,
        user_identifier: Optional[str] = None,
        event_details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None
    ):
        """
        Record an audit event in the database.
        
        Args:
            db_pool: Database connection pool
            event_type: Type of event (auth_success, auth_failure, api_key_created, etc.)
            severity: Event severity (info, warning, error, critical)
            tenant_id: Tenant UUID
            event_description: Human-readable description
            api_key_id: API key involved (if applicable)
            user_identifier: User email, username, or "system"
            event_details: Additional structured data (dict)
            ip_address: Client IP address
            user_agent: Client user agent
            resource_type: Type of resource affected
            resource_id: ID of resource affected
        """
        try:
            import json
            
            async with db_pool.acquire() as conn:
                await conn.execute(
                    """
                    SELECT core.record_audit_event(
                        $1::core.audit_event_type,
                        $2::core.audit_severity,
                        $3::UUID,
                        $4::UUID,
                        $5,
                        $6,
                        $7::JSONB,
                        $8::INET,
                        $9,
                        $10,
                        $11
                    )
                    """,
                    event_type,
                    severity,
                    str(tenant_id) if tenant_id else None,
                    str(api_key_id) if api_key_id else None,
                    user_identifier,
                    event_description,
                    json.dumps(event_details) if event_details else None,
                    ip_address,
                    user_agent,
                    resource_type,
                    resource_id
                )
            
            logger.info(f"Audit: {event_type} | {severity} | {event_description}")
            
        except Exception as e:
            logger.error(f"Failed to record audit event: {e}")
    
    @staticmethod
    def log_auth_success(db_pool, tenant_id: UUID, tenant_slug: str, api_key_id: UUID, ip_address: str = None):
        """Log successful authentication"""
        asyncio.create_task(
            AuditLogger.log_event(
                db_pool,
                event_type="auth_success",
                severity="info",
                tenant_id=tenant_id,
                api_key_id=api_key_id,
                event_description=f"Successful authentication for tenant {tenant_slug}",
                ip_address=ip_address,
                resource_type="authentication"
            )
        )
    
    @staticmethod
    def log_auth_failure(db_pool, reason: str, ip_address: str = None, api_key_prefix: str = None):
        """Log failed authentication attempt"""
        asyncio.create_task(
            AuditLogger.log_event(
                db_pool,
                event_type="auth_failure",
                severity="warning",
                tenant_id=None,
                event_description=f"Authentication failed: {reason}",
                event_details={"reason": reason, "api_key_prefix": api_key_prefix},
                ip_address=ip_address,
                resource_type="authentication"
            )
        )
    
    @staticmethod
    def log_api_key_created(
        db_pool,
        tenant_id: UUID,
        tenant_slug: str,
        api_key_id: UUID,
        key_name: str,
        created_by: str,
        ip_address: str = None
    ):
        """Log API key creation"""
        asyncio.create_task(
            AuditLogger.log_event(
                db_pool,
                event_type="api_key_created",
                severity="info",
                tenant_id=tenant_id,
                api_key_id=api_key_id,
                user_identifier=created_by,
                event_description=f"API key '  {key_name}' created for tenant {tenant_slug}",
                event_details={"key_name": key_name, "tenant_slug": tenant_slug},
                ip_address=ip_address,
                resource_type="api_key",
                resource_id=str(api_key_id)
            )
        )
    
    @staticmethod
    def log_api_key_revoked(
        db_pool,
        tenant_id: UUID,
        tenant_slug: str,
        api_key_id: UUID,
        key_name: str,
        revoked_by: str,
        ip_address: str = None
    ):
        """Log API key revocation"""
        asyncio.create_task(
            AuditLogger.log_event(
                db_pool,
                event_type="api_key_revoked",
                severity="warning",
                tenant_id=tenant_id,
                api_key_id=api_key_id,
                user_identifier=revoked_by,
                event_description=f"API key '{key_name}' revoked for tenant {tenant_slug}",
                event_details={"key_name": key_name, "tenant_slug": tenant_slug},
                ip_address=ip_address,
                resource_type="api_key",
                resource_id=str(api_key_id)
            )
        )
    
    @staticmethod
    def log_api_key_rotated(
        db_pool,
        tenant_id: UUID,
        tenant_slug: str,
        old_key_id: UUID,
        new_key_id: UUID,
        key_name: str,
        rotated_by: str,
        ip_address: str = None
    ):
        """Log API key rotation"""
        asyncio.create_task(
            AuditLogger.log_event(
                db_pool,
                event_type="api_key_rotated",
                severity="info",
                tenant_id=tenant_id,
                api_key_id=new_key_id,
                user_identifier=rotated_by,
                event_description=f"API key '{key_name}' rotated for tenant {tenant_slug}",
                event_details={
                    "key_name": key_name,
                    "tenant_slug": tenant_slug,
                    "old_key_id": str(old_key_id),
                    "new_key_id": str(new_key_id)
                },
                ip_address=ip_address,
                resource_type="api_key",
                resource_id=str(new_key_id)
            )
        )
    
    @staticmethod
    def log_tenant_isolation_violation(
        db_pool,
        tenant_id: UUID,
        tenant_slug: str,
        resource_type: str,
        resource_id: str,
        ip_address: str = None
    ):
        """Log cross-tenant access attempt (security alert)"""
        asyncio.create_task(
            AuditLogger.log_event(
                db_pool,
                event_type="tenant_isolation_violation",
                severity="critical",
                tenant_id=tenant_id,
                event_description=f"Tenant {tenant_slug} attempted cross-tenant access to {resource_type} {resource_id}",
                event_details={
                    "tenant_slug": tenant_slug,
                    "resource_type": resource_type,
                    "resource_id": resource_id
                },
                ip_address=ip_address,
                resource_type=resource_type,
                resource_id=resource_id
            )
        )
    
    @staticmethod
    def log_admin_action(
        db_pool,
        tenant_id: UUID,
        admin_user: str,
        action: str,
        description: str,
        ip_address: str = None
    ):
        """Log administrative action"""
        asyncio.create_task(
            AuditLogger.log_event(
                db_pool,
                event_type="admin_action",
                severity="info",
                tenant_id=tenant_id,
                user_identifier=admin_user,
                event_description=description,
                event_details={"action": action},
                ip_address=ip_address,
                resource_type="admin"
            )
        )
