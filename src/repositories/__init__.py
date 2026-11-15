"""
Repository Layer Package: Manages raw database access, dynamic read-only query execution,
and schema metadata extraction.
"""

from typing import List, Dict, Any, Tuple
from src.repositories.query_repository import QueryRepository, serialize_row_value
from src.repositories.schema_repository import SchemaRepository


class DatabaseConnection(QueryRepository):
    """
    Combined repository interface maintaining 100% backward compatibility
    with existing code while leveraging clean CSR separation.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.schema_repo = SchemaRepository(self)

    def get_available_tables(self) -> List[str]:
        return self.schema_repo.get_available_tables()

    def inspect_schema(self, tables: List[str]) -> Dict[str, Any]:
        return self.schema_repo.inspect_schema(tables)

    def format_schema_summary(self, schema_info: Dict[str, Any]) -> str:
        return self.schema_repo.format_schema_summary(schema_info)


__all__ = [
    "QueryRepository",
    "SchemaRepository",
    "DatabaseConnection",
    "serialize_row_value",
]
