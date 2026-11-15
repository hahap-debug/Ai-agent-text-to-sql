"""
Schema Controller: Handles table catalog and schema inspection endpoints.
"""

from typing import List
from fastapi import APIRouter, HTTPException, Query, status
from src.repositories import DatabaseConnection
from src.models.schemas import SchemaInspectRequest, SchemaInspectResponse

router = APIRouter(tags=["Schema"])

_db = DatabaseConnection()


@router.get("/tables", response_model=List[str])
def list_tables() -> List[str]:
    """Lists all available tables in ecommerce_db."""
    return _db.get_available_tables()


@router.post("/schema/inspect", response_model=SchemaInspectResponse)
def inspect_schema_post(req: SchemaInspectRequest) -> SchemaInspectResponse:
    """Inspects real column definitions and keys for requested tables via POST."""
    raw = _db.inspect_schema(req.tables)
    summary = _db.format_schema_summary(raw)
    return SchemaInspectResponse(
        tables=req.tables,
        summary=summary,
        raw=raw
    )


@router.get("/schema", response_model=SchemaInspectResponse)
def inspect_schema_get(tables: str = Query(..., description="Comma-separated list of table names")) -> SchemaInspectResponse:
    """Inspects real column definitions and keys for requested tables via GET."""
    table_list = [t.strip() for t in tables.split(",") if t.strip()]
    if not table_list:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No valid table names provided")
    raw = _db.inspect_schema(table_list)
    summary = _db.format_schema_summary(raw)
    return SchemaInspectResponse(
        tables=table_list,
        summary=summary,
        raw=raw
    )
