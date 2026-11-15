"""
Backward-compatibility routes module delegating to CSR controllers.
"""

from src.controllers import api_router as router
from src.controllers.health_controller import get_health as check_health, _db as _db_instance
from src.controllers.schema_controller import list_tables, inspect_schema_post, inspect_schema_get
from src.controllers.agent_controller import (
    execute_query,
    execute_query_stream,
    generate_sse_events,
    get_agent,
    step_to_dto,
    run_result_to_response,
)

__all__ = [
    "router",
    "check_health",
    "_db_instance",
    "list_tables",
    "inspect_schema_post",
    "inspect_schema_get",
    "execute_query",
    "execute_query_stream",
    "generate_sse_events",
    "get_agent",
    "step_to_dto",
    "run_result_to_response",
]
