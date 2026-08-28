from app.handlers.admin import router as admin_router
from app.handlers.booking import router as booking_router
from app.handlers.client import router as client_router

__all__ = ["admin_router", "booking_router", "client_router"]
