"""
Tool 3: Query Execution
Executes AST-validated read-only SELECT queries on MySQL ecommerce_db.
"""

from typing import Dict, Any, List
import decimal
import datetime
from mcp_server.db import MCPDatabase
from mcp_server.config import MCPConfig
from mcp_server.security import validate_mcp_query, SQLSecurityError, SQLSyntaxError

def _clean_sql_value(val: Any) -> Any:
    """Converts Decimal, Date, and DateTime objects to JSON-friendly types."""
    if isinstance(val, decimal.Decimal):
        return float(val)
    elif isinstance(val, (datetime.date, datetime.datetime)):
        return val.isoformat()
    elif isinstance(val, bytes):
        return val.decode("utf-8", errors="replace")
    return val

def execute_sql_handler(query: str) -> Dict[str, Any]:
    """
    Validates and executes a read-only SQL query against ecommerce_db.
    Enforces ONLY_FULL_GROUP_BY and safety limits.
    """
    clean_q = query.strip().rstrip(";")
    if not clean_q:
        return {"status": "error", "message": "SQL query cannot be empty."}

    # 1. AST Security Validation
    try:
        validate_mcp_query(clean_q)
    except (SQLSecurityError, SQLSyntaxError) as e:
        return {
            "status": "security_violation",
            "message": f"Security Guard Blocked Query: {str(e)}"
        }
    except Exception as ex:
        return {
            "status": "error",
            "message": f"Query Validation Failed: {str(ex)}"
        }

    # 2. Add safe LIMIT if query lacks LIMIT clause
    if "limit" not in clean_q.lower():
        clean_q = f"{clean_q} LIMIT {MCPConfig.DEFAULT_LIMIT}"

    # 3. Execute on MySQL
    try:
        conn = MCPDatabase.get_connection()
        with conn.cursor() as cursor:
            # Enforce strict group by and read only session
            cursor.execute("SET SESSION sql_mode = CONCAT(@@sql_mode, ',ONLY_FULL_GROUP_BY');")
            cursor.execute(clean_q)
            raw_rows = cursor.fetchall()
        conn.close()

        # Format rows cleanly
        formatted_rows = []
        for row in raw_rows[:MCPConfig.MAX_ROWS]:
            formatted_rows.append({k: _clean_sql_value(v) for k, v in row.items()})

        return {
            "status": "success",
            "row_count": len(formatted_rows),
            "executed_sql": clean_q,
            "rows": formatted_rows
        }
    except Exception as e:
        return {
            "status": "database_error",
            "message": str(e),
            "failed_sql": clean_q
        }
