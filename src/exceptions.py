"""
Custom exceptions for better error handling
Keep it simple but comprehensive
"""
from typing import Optional, Any

class ParkingException(Exception):
    """Base exception for all parking-related errors"""

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[dict] = None
    ):
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> dict:
        """Convert exception to dictionary for API responses"""
        return {
            "error": self.error_code,
            "message": self.message,
            "details": self.details
        }

# ============================================================
# Database Exceptions
# ============================================================

class DatabaseError(ParkingException):
    """Database connection or query error"""
    pass

class RecordNotFoundError(ParkingException):
    """Record not found in database"""

    def __init__(self, resource: str, identifier: Any):
        super().__init__(
            message=f"{resource} not found: {identifier}",
            error_code="RECORD_NOT_FOUND",
            details={"resource": resource, "identifier": str(identifier)}
        )

# ============================================================
# Domain Exceptions
# ============================================================

class SpaceNotFoundError(RecordNotFoundError):
    """Parking space not found"""

    def __init__(self, space_id: str):
        super().__init__("Space", space_id)
        self.space_id = space_id

class ReservationNotFoundError(RecordNotFoundError):
    """Reservation not found"""

    def __init__(self, reservation_id: str):
        super().__init__("Reservation", reservation_id)
        self.reservation_id = reservation_id

class DeviceNotFoundError(RecordNotFoundError):
    """Device not found"""

    def __init__(self, device_eui: str):
        super().__init__("Device", device_eui)
        self.device_eui = device_eui

# ============================================================
# Business Logic Exceptions
# ============================================================

class StateTransitionError(ParkingException):
    """Invalid state transition"""

    def __init__(
        self,
        message: str,
        current_state: Optional[str] = None,
        requested_state: Optional[str] = None
    ):
        super().__init__(
            message=message,
            error_code="INVALID_STATE_TRANSITION",
            details={
                "current_state": current_state,
                "requested_state": requested_state
            }
        )
        self.current_state = current_state
        self.requested_state = requested_state

class SpaceNotAvailableError(ParkingException):
    """Space is not available for reservation"""

    def __init__(self, space_id: str, reason: str = "Space is not available"):
        super().__init__(
            message=reason,
            error_code="SPACE_NOT_AVAILABLE",
            details={"space_id": space_id}
        )

class DuplicateResourceError(ParkingException):
    """Resource already exists"""

    def __init__(self, resource: str, identifier: Any):
        super().__init__(
            message=f"{resource} already exists: {identifier}",
            error_code="DUPLICATE_RESOURCE",
            details={"resource": resource, "identifier": str(identifier)}
        )

# ============================================================
# External Service Exceptions
# ============================================================

class ChirpStackError(ParkingException):
    """ChirpStack API error"""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(
            message=message,
            error_code="CHIRPSTACK_ERROR",
            details={"status_code": status_code} if status_code else {}
        )
        self.status_code = status_code

class RedisError(ParkingException):
    """Redis connection or operation error"""
    pass

# ============================================================
# Validation Exceptions
# ============================================================

class ValidationError(ParkingException):
    """Input validation error"""

    def __init__(self, field: str, message: str):
        super().__init__(
            message=f"Validation error for {field}: {message}",
            error_code="VALIDATION_ERROR",
            details={"field": field, "error": message}
        )

class AuthenticationError(ParkingException):
    """Authentication failed"""

    def __init__(self, message: str = "Authentication failed"):
        super().__init__(
            message=message,
            error_code="AUTHENTICATION_ERROR"
        )

class AuthorizationError(ParkingException):
    """Authorization failed"""

    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(
            message=message,
            error_code="AUTHORIZATION_ERROR"
        )
