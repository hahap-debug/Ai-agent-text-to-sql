"""
Controller Layer Package: Handles HTTP routes and transports.
"""

from fastapi import APIRouter
from src.controllers.health_controller import router as health_router
from src.controllers.schema_controller import router as schema_router
from src.controllers.agent_controller import router as agent_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health_router)
api_router.include_router(schema_router)
api_router.include_router(agent_router)

__all__ = ["api_router", "health_router", "schema_router", "agent_router"]
