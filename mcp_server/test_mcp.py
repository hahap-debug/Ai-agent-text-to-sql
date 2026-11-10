"""
Standalone Test Script for MCP Server Tools
Verifies all 3 separated tools: catalog, schema, and query execution.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mcp_server.tools.catalog import list_tables_handler
from mcp_server.tools.schema import inspect_schema_handler
from mcp_server.tools.query import execute_sql_handler

def main():
    print("=" * 60)
    print("🧪 Testing Separated MCP Server Tools")
    print("=" * 60)

    # 1. Test Catalog Tool
    print("\n[1] Testing Tool: list_tables")
    cat_res = list_tables_handler()
    assert cat_res["status"] == "success", f"Catalog failed: {cat_res}"
    print(f"  ✅ SUCCESS: Found {cat_res['total_tables']} tables in {cat_res['database']}")
    sample_tables = [t["table_name"] for t in cat_res["tables"][:5]]
    print(f"  Preview: {sample_tables}")

    # 2. Test Schema Tool
    print("\n[2] Testing Tool: inspect_schema(['products', 'brands'])")
    schema_res = inspect_schema_handler(["products", "brands"])
    assert schema_res["status"] == "success", f"Schema failed: {schema_res}"
    prod_info = schema_res["schema"]["products"]
    print(f"  ✅ SUCCESS: Inspected products table ({prod_info['total_columns']} cols)")
    print(f"  Columns Summary: {prod_info['columns_summary'][:100]}...")
    print(f"  Foreign Keys: {prod_info['foreign_keys']}")

    # 3. Test Query Tool: Safe SELECT
    print("\n[3] Testing Tool: execute_sql (Safe SELECT)")
    safe_q = "SELECT id, name FROM brands ORDER BY id ASC LIMIT 3;"
    q_res = execute_sql_handler(safe_q)
    assert q_res["status"] == "success", f"Safe query failed: {q_res}"
    print(f"  ✅ SUCCESS: Query returned {q_res['row_count']} rows")
    print(f"  Rows preview: {q_res['rows']}")

    # 4. Test Query Tool: Block Dangerous DROP
    print("\n[4] Testing Tool: execute_sql (Dangerous Mutation Block)")
    bad_q = "DROP TABLE users;"
    bad_res = execute_sql_handler(bad_q)
    assert bad_res["status"] == "security_violation", f"Should block DROP: {bad_res}"
    print(f"  ✅ SUCCESS: Security Guard blocked DROP -> {bad_res['message']}")

    print("\n" + "=" * 60)
    print("🎉 ALL MCP SERVER TOOLS PASSED VERIFICATION (100%)")
    print("=" * 60)

if __name__ == "__main__":
    main()
