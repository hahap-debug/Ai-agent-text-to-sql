import json
from mcp.server.fastmcp import FastMCP
from mcp_server.tools.catalog import list_tables_handler
from mcp_server.tools.schema import inspect_schema_handler
from mcp_server.tools.query import execute_sql_handler

mcp = FastMCP(
    "ecommerce-analytics-mcp",
    instructions="Expert E-Commerce Database MCP Server for ecommerce_db. Provides safe read-only SQL analytics."
)

@mcp.tool()
def list_tables() -> str:
    """
    Get all authorized tables in ecommerce_db and their descriptions.
    Always call this tool first to see what tables are available.
    """
    res = list_tables_handler()
    return json.dumps(res, ensure_ascii=False, indent=2)

@mcp.tool()
def inspect_schema(tables: list[str]) -> str:
    """
    Get exact column names, data types, primary keys, and foreign keys for specific tables.
    Args:
        tables: List of table names to inspect, e.g. ["orders", "users"]
    """
    res = inspect_schema_handler(tables)
    return json.dumps(res, ensure_ascii=False, indent=2)

@mcp.tool()
def execute_sql(query: str) -> str:
    """
    Execute a validated, read-only SQL SELECT query on ecommerce_db.
    Non-SELECT operations (INSERT, UPDATE, DELETE, DROP) are strictly blocked.
    Args:
        query: Standard MySQL 8.x SELECT query.
    """
    res = execute_sql_handler(query)
    return json.dumps(res, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    # When launched by Claude Desktop, Cursor, or Antigravity, runs over standard input/output (stdio)
    mcp.run(transport="stdio")
