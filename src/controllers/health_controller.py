"""
Health Controller: Handles health checks and connectivity probes.
"""

from fastapi import APIRouter
from src.config import Config
from src.repositories import DatabaseConnection
from src.models.schemas import HealthResponse

router = APIRouter(tags=["Health"])

_db = DatabaseConnection()


@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    """Returns database connectivity and active LLM configuration."""
    db_status = "connected" if _db.is_connected() else "degraded"
    return HealthResponse(
        status="ok" if db_status == "connected" else "degraded",
        database=db_status,
        db_type="mysql" if _db.is_mysql else "sqlite",
        active_provider=Config.LLM_PROVIDER,
        version="2.0.0"
    )
