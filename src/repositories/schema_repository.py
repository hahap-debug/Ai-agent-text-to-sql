"""
Schema Repository: Extracts metadata, table names, columns,
primary keys, and foreign key relations from MySQL or SQLite.
"""

from typing import List, Dict, Any
from src.repositories.query_repository import QueryRepository


class SchemaRepository:
    """
    Handles metadata extraction and schema inspection across MySQL and SQLite.
    """

    def __init__(self, query_repo: QueryRepository):
        self.query_repo = query_repo

    def get_available_tables(self) -> List[str]:
        """Returns all table names in the active database."""
        conn = self.query_repo.get_connection()
        tables = []
        try:
            with conn:
                cursor = conn.cursor()
                if self.query_repo.is_mysql:
                    cursor.execute("""
                        SELECT table_name 
                        FROM information_schema.tables 
                        WHERE table_schema = %s 
                        ORDER BY table_name;
                    """, (self.query_repo.database,))
                    rows = cursor.fetchall()
                    tables = [r.get("table_name") or r.get("TABLE_NAME") for r in rows]
                else:
                    cursor.execute("""
                        SELECT name FROM sqlite_master 
                        WHERE type='table' AND name NOT LIKE 'sqlite_%'
                        ORDER BY name;
                    """)
                    rows = cursor.fetchall()
                    tables = [r[0] for r in rows]
        except Exception:
            if self.query_repo.is_mysql:
                try:
                    with conn:
                        cursor = conn.cursor()
                        cursor.execute("SHOW TABLES")
                        rows = cursor.fetchall()
                        for r in rows:
                            tables.append(list(r.values())[0])
                except Exception:
                    pass
        return tables

    def inspect_schema(self, tables: List[str]) -> Dict[str, Any]:
        """
        Inspects exact columns, data types, primary keys, and foreign keys for requested tables.
        """
        schema_info = {}
        conn = self.query_repo.get_connection()

        with conn:
            cursor = conn.cursor()
            for table in tables:
                table_clean = table.strip().replace("`", "").replace("'", "")
                if self.query_repo.is_mysql:
                    # 1. Fetch Columns
                    cursor.execute("""
                        SELECT column_name, data_type, column_key, is_nullable
                        FROM information_schema.columns
                        WHERE table_schema = %s AND table_name = %s
                        ORDER BY ordinal_position;
                    """, (self.query_repo.database, table_clean))
                    cols = cursor.fetchall()

                    if not cols:
                        schema_info[table_clean] = {"error": f"Table '{table_clean}' not found in database."}
                        continue

                    columns = []
                    for c in cols:
                        col_name = c.get("column_name") or c.get("COLUMN_NAME")
                        dtype = c.get("data_type") or c.get("DATA_TYPE")
                        ckey = c.get("column_key") or c.get("COLUMN_KEY")
                        columns.append({
                            "name": col_name,
                            "type": dtype,
                            "is_pk": ckey == "PRI"
                        })

                    # 2. Fetch Foreign Keys
                    cursor.execute("""
                        SELECT column_name, referenced_table_name, referenced_column_name
                        FROM information_schema.key_column_usage
                        WHERE table_schema = %s AND table_name = %s 
                          AND referenced_table_name IS NOT NULL;
                    """, (self.query_repo.database, table_clean))
                    fks = cursor.fetchall()
                    foreign_keys = []
                    for fk in fks:
                        col = fk.get("column_name") or fk.get("COLUMN_NAME")
                        ref_tbl = fk.get("referenced_table_name") or fk.get("REFERENCED_TABLE_NAME")
                        ref_col = fk.get("referenced_column_name") or fk.get("REFERENCED_COLUMN_NAME")
                        foreign_keys.append({
                            "column": col,
                            "references": f"{ref_tbl}.{ref_col}"
                        })

                    schema_info[table_clean] = {
                        "columns": columns,
                        "foreign_keys": foreign_keys
                    }
                else:
                    # SQLite Schema Inspection
                    cursor.execute(f"PRAGMA table_info({table_clean});")
                    cols = cursor.fetchall()
                    if not cols:
                        schema_info[table_clean] = {"error": f"Table '{table_clean}' not found in SQLite database."}
                        continue

                    columns = []
                    for c in cols:
                        columns.append({
                            "name": c[1],
                            "type": c[2],
                            "is_pk": bool(c[5])
                        })

                    cursor.execute(f"PRAGMA foreign_key_list({table_clean});")
                    fks = cursor.fetchall()
                    foreign_keys = []
                    for fk in fks:
                        foreign_keys.append({
                            "column": fk[3],
                            "references": f"{fk[2]}.{fk[4]}"
                        })

                    schema_info[table_clean] = {
                        "columns": columns,
                        "foreign_keys": foreign_keys
                    }

        return schema_info

    def format_schema_summary(self, schema_info: Dict[str, Any]) -> str:
        """
        Converts structured schema metadata into a compact, human-readable summary.
        """
        lines = []
        for table, data in schema_info.items():
            if "error" in data:
                lines.append(f"- Table `{table}`: ERROR - {data['error']}")
                continue

            col_parts = []
            for c in data.get("columns", []):
                pk_flag = " (PK)" if c.get("is_pk") else ""
                col_parts.append(f"{c['name']}{pk_flag}")

            col_str = ", ".join(col_parts)
            fk_parts = [f"{fk['column']} -> {fk['references']}" for fk in data.get("foreign_keys", [])]
            fk_str = f" | FK: {', '.join(fk_parts)}" if fk_parts else ""

            lines.append(f"- Table `{table}`: {col_str}{fk_str}")

        return "\n".join(lines)
