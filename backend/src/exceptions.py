"""Custom exceptions for V6 Smart Parking Platform"""

from typing import Optional, Dict, Any
from fastapi import HTTPException, status


class ParkingBaseException(Exception):
    """Base exception for all parking platform errors"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


# Tenant Exceptions
class TenantException(ParkingBaseException):
    """Base exception for tenant-related errors"""
    pass


class TenantNotFoundException(TenantException):
    """Tenant not found"""
    pass


class TenantAccessDeniedException(TenantException):
    """Access to tenant denied"""
    pass


class TenantQuotaExceededException(TenantException):
    """Tenant has exceeded their quota"""
    pass


# Device Exceptions
class DeviceException(ParkingBaseException):
    """Base exception for device-related errors"""
    pass


class DeviceNotFoundException(DeviceException):
    """Device not found"""
    pass


class DeviceAlreadyAssignedException(DeviceException):
    """Device is already assigned to a space"""
    pass


class DeviceNotAssignedException(DeviceException):
    """Device is not assigned to any space"""
    pass


class DeviceLifecycleException(DeviceException):
    """Invalid device lifecycle state transition"""
    pass


class ChirpStackSyncException(DeviceException):
    """Error syncing with ChirpStack"""
    pass


# Space Exceptions
class SpaceException(ParkingBaseException):
    """Base exception for space-related errors"""
    pass


class SpaceNotFoundException(SpaceException):
    """Space not found"""
    pass


class SpaceAlreadyHasDeviceException(SpaceException):
    """Space already has a device assigned"""
    pass


# Reservation Exceptions
class ReservationException(ParkingBaseException):
    """Base exception for reservation-related errors"""
    pass


class ReservationNotFoundException(ReservationException):
    """Reservation not found"""
    pass


class ReservationOverlapException(ReservationException):
    """Reservation overlaps with existing reservation"""
    pass


class ReservationCancelledException(ReservationException):
    """Reservation has been cancelled"""
    pass


class ReservationExpiredException(ReservationException):
    """Reservation has expired"""
    pass


# Authentication Exceptions
class AuthenticationException(ParkingBaseException):
    """Base exception for authentication errors"""
    pass


class InvalidCredentialsException(AuthenticationException):
    """Invalid username or password"""
    pass


class TokenExpiredException(AuthenticationException):
    """JWT token has expired"""
    pass


class InvalidTokenException(AuthenticationException):
    """Invalid JWT token"""
    pass


class InsufficientPermissionsException(AuthenticationException):
    """User lacks required permissions"""
    pass


# Rate Limiting Exceptions
class RateLimitException(ParkingBaseException):
    """Rate limit exceeded"""
    pass


# Webhook Exceptions
class WebhookException(ParkingBaseException):
    """Base exception for webhook errors"""
    pass


class InvalidWebhookSignatureException(WebhookException):
    """Invalid webhook signature"""
    pass


# Downlink Exceptions
class DownlinkException(ParkingBaseException):
    """Base exception for downlink errors"""
    pass


class DownlinkQueueFullException(DownlinkException):
    """Downlink queue is full"""
    pass


class DownlinkRateLimitException(DownlinkException):
    """Downlink rate limit exceeded"""
    pass


# Utility functions to convert to HTTP exceptions
def to_http_exception(exc: ParkingBaseException, status_code: int = status.HTTP_400_BAD_REQUEST) -> HTTPException:
    """Convert a parking exception to an HTTP exception"""
    return HTTPException(
        status_code=status_code,
        detail={
            "message": exc.message,
            "details": exc.details
        }
    )


# HTTP Exception helpers
class HTTPExceptionFactory:
    """Factory for creating HTTP exceptions"""
    
    @staticmethod
    def tenant_not_found(tenant_id: str) -> HTTPException:
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant {tenant_id} not found"
        )
    
    @staticmethod
    def device_not_found(device_id: str) -> HTTPException:
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device {device_id} not found"
        )
    
    @staticmethod
    def space_not_found(space_id: str) -> HTTPException:
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Space {space_id} not found"
        )
    
    @staticmethod
    def unauthorized(detail: str = "Not authenticated") -> HTTPException:
        return HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    @staticmethod
    def forbidden(detail: str = "Insufficient permissions") -> HTTPException:
        return HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail
        )
    
    @staticmethod
    def rate_limited(retry_after: int = 60) -> HTTPException:
        return HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(retry_after)}
        )
