"""Audit logging service"""

from typing import Optional, Dict, Any
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import insert
import logging

from ..core.tenant_context import TenantContext
from ..models.audit import AuditLog

logger = logging.getLogger(__name__)


class AuditService:
    """Service for creating audit log entries"""
    
    def __init__(self, db: AsyncSession, tenant: TenantContext):
        self.db = db
        self.tenant = tenant
    
    async def log_action(
        self,
        action: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        old_values: Optional[Dict[str, Any]] = None,
        new_values: Optional[Dict[str, Any]] = None,
        actor_details: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> UUID:
        """Create an audit log entry"""
        try:
            stmt = insert(AuditLog).values(
                tenant_id=self.tenant.tenant_id,
                actor_type="user",
                actor_id=str(self.tenant.user_id),
                actor_details=actor_details or {
                    "username": self.tenant.username,
                    "email": self.tenant.email,
                    "role": self.tenant.role.name
                },
                action=action,
                resource_type=resource_type,
                resource_id=str(resource_id) if resource_id else None,
                old_values=old_values,
                new_values=new_values,
                request_id=request_id,
                ip_address=ip_address,
                user_agent=user_agent
            ).returning(AuditLog.id)
            
            result = await self.db.execute(stmt)
            audit_id = result.scalar_one()
            await self.db.commit()
            
            logger.info(f"Audit log created: {action} on {resource_type}/{resource_id}")
            return audit_id
            
        except Exception as e:
            logger.error(f"Failed to create audit log: {e}")
            # Don't fail the main operation if audit logging fails
            return None
    
    async def log_device_assignment(
        self,
        device_id: UUID,
        space_id: UUID,
        old_space_id: Optional[UUID] = None
    ) -> UUID:
        """Log device assignment action"""
        return await self.log_action(
            action="device_assigned",
            resource_type="device",
            resource_id=str(device_id),
            old_values={"space_id": str(old_space_id)} if old_space_id else None,
            new_values={"space_id": str(space_id)}
        )
    
    async def log_reservation_created(
        self,
        reservation_id: UUID,
        space_id: UUID,
        start_time: str,
        end_time: str
    ) -> UUID:
        """Log reservation creation"""
        return await self.log_action(
            action="reservation_created",
            resource_type="reservation",
            resource_id=str(reservation_id),
            new_values={
                "space_id": str(space_id),
                "start_time": start_time,
                "end_time": end_time
            }
        )
