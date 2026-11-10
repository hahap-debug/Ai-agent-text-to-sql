"""
Tool 2: Schema Inspection
Allows AI to inspect exact columns, data types, primary keys, and foreign keys.
"""

from typing import List, Dict, Any
from mcp_server.db import MCPDatabase
from mcp_server.config import MCPConfig

def inspect_schema_handler(tables: List[str]) -> Dict[str, Any]:
    """
    Inspects specific tables in ecommerce_db and returns their columns, types, and foreign key relationships.
    """
    if not tables:
        return {"status": "error", "message": "Please specify at least one table name."}

    results = {}
    try:
        conn = MCPDatabase.get_connection()
        with conn.cursor() as cursor:
            for table in tables:
                clean_table = table.strip().replace("`", "")
                
                # Check table exists
                cursor.execute("""
                    SELECT TABLE_NAME 
                    FROM information_schema.tables 
                    WHERE table_schema = %s AND table_name = %s;
                """, (MCPConfig.DB_NAME, clean_table))
                if not cursor.fetchone():
                    results[clean_table] = {"error": f"Table '{clean_table}' does not exist in ecommerce_db."}
                    continue

                # Columns
                cursor.execute("""
                    SELECT 
                        COLUMN_NAME AS name,
                        COLUMN_TYPE AS type,
                        IS_NULLABLE AS nullable,
                        COLUMN_KEY AS `key`,
                        COLUMN_DEFAULT AS `default`
                    FROM information_schema.columns
                    WHERE table_schema = %s AND table_name = %s
                    ORDER BY ORDINAL_POSITION;
                """, (MCPConfig.DB_NAME, clean_table))
                columns = cursor.fetchall()

                # Foreign Keys
                cursor.execute("""
                    SELECT 
                        COLUMN_NAME AS from_column,
                        REFERENCED_TABLE_NAME AS to_table,
                        REFERENCED_COLUMN_NAME AS to_column
                    FROM information_schema.key_column_usage
                    WHERE table_schema = %s AND table_name = %s 
                      AND REFERENCED_TABLE_NAME IS NOT NULL;
                """, (MCPConfig.DB_NAME, clean_table))
                foreign_keys = cursor.fetchall()

                # Build readable text summary
                col_strs = []
                for c in columns:
                    name = c["name"]
                    c_type = c["type"].upper()
                    flags = []
                    if c["key"] == "PRI":
                        flags.append("PK")
                    for fk in foreign_keys:
                        if fk["from_column"] == name:
                            flags.append(f"FK -> {fk['to_table']}.{fk['to_column']}")
                    flag_str = f" ({', '.join(flags)})" if flags else ""
                    col_strs.append(f"{name}: {c_type}{flag_str}")

                results[clean_table] = {
                    "columns_summary": ", ".join(col_strs),
                    "total_columns": len(columns),
                    "foreign_keys": foreign_keys
                }

        conn.close()
        return {
            "status": "success",
            "schema": results
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to inspect schema: {str(e)}"
        }
