"""
API Routers
"""
from .spaces import router as spaces_router
from .devices import router as devices_router
from .reservations import router as reservations_router
from .gateways import router as gateways_router

__all__ = ["spaces_router", "devices_router", "reservations_router", "gateways_router"]
