"""
Database Connector & Inspection Module
Handles database connections (MySQL and SQLite fallback),
dynamic schema inspection, and safe read-only SQL execution.
"""

from typing import List, Dict, Any, Optional, Tuple
from contextlib import contextmanager
import datetime
from decimal import Decimal
import pymysql
import sqlite3
from src.config import Config
from src.validator import validate_ast_safety, SQLSecurityError, SQLSyntaxError

def serialize_row_value(val: Any) -> Any:
    """Helper to convert non-JSON serializable values like Decimal, datetime, bytes."""
    if isinstance(val, Decimal):
        return float(val) if (val % 1 != 0) else int(val)
    elif isinstance(val, (datetime.date, datetime.datetime, datetime.time)):
        return val.isoformat()
    elif isinstance(val, bytes):
        return val.decode("utf-8", errors="replace")
    return val

class DatabaseConnection:
    """
    Unified database manager supporting both MySQL and SQLite.
    Dynamically inspects schema and executes read-only queries with AST validation.
    """

    def __init__(
        self,
        db_type: str = Config.DB_TYPE,
        host: str = Config.DB_HOST,
        port: int = Config.DB_PORT,
        user: str = Config.DB_USER,
        password: str = Config.DB_PASSWORD,
        database: str = Config.DB_NAME,
        sqlite_path: str = Config.SQLITE_DB_PATH,
        auto_fallback: bool = True
    ):
        self.db_type = db_type.lower()
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database
        self.sqlite_path = sqlite_path
        self.auto_fallback = auto_fallback
        self.fallback_active = False

    def get_connection(self):
        """Creates and returns a new connection based on configured DB_TYPE with auto-fallback."""
        if self.db_type == "mysql" and not self.fallback_active:
            import socket
            try:
                with socket.create_connection((self.host, self.port), timeout=1.0):
                    pass
            except Exception as se:
                if self.auto_fallback:
                    self.fallback_active = True
                    conn = sqlite3.connect(self.sqlite_path, timeout=Config.SQL_TIMEOUT_SECONDS)
                    conn.row_factory = sqlite3.Row
                    return conn
                raise se

            try:
                ssl_kwargs = {}
                import os
                if self.port == 4000 or "tidbcloud.com" in self.host.lower() or os.getenv("DB_SSL", "false").lower() in ("true", "1", "require"):
                    ssl_kwargs = {"ssl_verify_cert": True, "ssl_verify_identity": True}

                return pymysql.connect(
                    host=self.host,
                    port=self.port,
                    user=self.user,
                    password=self.password,
                    database=self.database,
                    charset=Config.DB_CHARSET,
                    cursorclass=pymysql.cursors.DictCursor,
                    connect_timeout=5 if self.auto_fallback else Config.SQL_TIMEOUT_SECONDS,
                    autocommit=True,
                    **ssl_kwargs
                )
            except Exception as e:
                if self.auto_fallback:
                    self.fallback_active = True
                    # Fallback to local SQLite
                    conn = sqlite3.connect(self.sqlite_path, timeout=Config.SQL_TIMEOUT_SECONDS)
                    conn.row_factory = sqlite3.Row
                    return conn
                raise e

        # SQLite connection
        conn = sqlite3.connect(self.sqlite_path, timeout=Config.SQL_TIMEOUT_SECONDS)
        conn.row_factory = sqlite3.Row
        return conn

    @property
    def is_mysql(self) -> bool:
        return self.db_type == "mysql" and not self.fallback_active

    def is_connected(self) -> bool:
        """Returns True if database is reachable (either MySQL or SQLite fallback)."""
        ok, _ = self.test_connection()
        return ok

    def test_connection(self) -> Tuple[bool, str]:
        """Verify database connectivity."""
        try:
            conn = self.get_connection()
            with conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1 AS ping")
                cursor.fetchone()
            if self.fallback_active:
                return True, f"MySQL offline/blocked; using local SQLite ({self.sqlite_path})"
            return True, f"Connected successfully to {self.db_type.upper()} ({self.database if self.db_type=='mysql' else self.sqlite_path})"
        except Exception as e:
            return False, f"Connection failed: {str(e)}"

    def get_available_tables(self) -> List[str]:
        """Returns all table names in the active database."""
        conn = self.get_connection()
        tables = []
        try:
            with conn:
                cursor = conn.cursor()
                if self.is_mysql:
                    cursor.execute("""
                        SELECT table_name 
                        FROM information_schema.tables 
                        WHERE table_schema = %s 
                        ORDER BY table_name;
                    """, (self.database,))
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
        except Exception as e:
            # Fallback for MySQL if information_schema permission issue
            if self.is_mysql:
                try:
                    with conn:
                        cursor = conn.cursor()
                        cursor.execute("SHOW TABLES")
                        rows = cursor.fetchall()
                        tables = [list(r.values())[0] for r in rows]
                except Exception:
                    pass
        return tables

    def inspect_schema(self, tables: List[str]) -> Dict[str, Any]:
        """
        Inspect exact columns, types, primary keys, and foreign keys
        for a list of table names.
        """
        schema_info = {}
        all_tables = [t.lower() for t in self.get_available_tables()]

        for table in tables:
            tbl_clean = table.strip().lower()
            if tbl_clean not in all_tables:
                schema_info[table] = {"error": f"Table '{table}' does not exist in database '{self.database}'."}
                continue

            try:
                if self.is_mysql:
                    schema_info[table] = self._inspect_mysql_table(tbl_clean)
                else:
                    schema_info[table] = self._inspect_sqlite_table(tbl_clean)
            except Exception as e:
                schema_info[table] = {"error": f"Failed to inspect table '{table}': {str(e)}"}

        return schema_info

        return schema_info

    def _inspect_mysql_table(self, table_name: str) -> Dict[str, Any]:
        """Inspects columns and foreign keys of a MySQL table."""
        conn = self.get_connection()
        columns = []
        foreign_keys = []

        with conn:
            cursor = conn.cursor()
            # 1. Columns
            cursor.execute("""
                SELECT 
                    column_name, 
                    data_type, 
                    column_key, 
                    is_nullable, 
                    extra
                FROM information_schema.columns
                WHERE table_schema = %s AND table_name = %s
                ORDER BY ordinal_position;
            """, (self.database, table_name))
            col_rows = cursor.fetchall()
            for r in col_rows:
                c_name = r.get("column_name") or r.get("COLUMN_NAME")
                c_type = r.get("data_type") or r.get("DATA_TYPE")
                c_key = r.get("column_key") or r.get("COLUMN_KEY")
                c_null = (r.get("is_nullable") or r.get("IS_NULLABLE")) == "YES"
                columns.append({
                    "name": c_name,
                    "type": c_type,
                    "primary_key": c_key == "PRI",
                    "nullable": c_null
                })

            # 2. Foreign keys
            cursor.execute("""
                SELECT 
                    column_name, 
                    referenced_table_name, 
                    referenced_column_name
                FROM information_schema.key_column_usage
                WHERE table_schema = %s 
                  AND table_name = %s 
                  AND referenced_table_name IS NOT NULL;
            """, (self.database, table_name))
            fk_rows = cursor.fetchall()
            for r in fk_rows:
                foreign_keys.append({
                    "column": r.get("column_name") or r.get("COLUMN_NAME"),
                    "references_table": r.get("referenced_table_name") or r.get("REFERENCED_TABLE_NAME"),
                    "references_column": r.get("referenced_column_name") or r.get("REFERENCED_COLUMN_NAME")
                })

        return {
            "table": table_name,
            "columns": columns,
            "foreign_keys": foreign_keys
        }

    def _inspect_sqlite_table(self, table_name: str) -> Dict[str, Any]:
        """Inspects columns and foreign keys of an SQLite table."""
        conn = self.get_connection()
        columns = []
        foreign_keys = []

        with conn:
            cursor = conn.cursor()
            cursor.execute(f"PRAGMA table_info({table_name});")
            for row in cursor.fetchall():
                columns.append({
                    "name": row[1],
                    "type": row[2],
                    "primary_key": bool(row[5]),
                    "nullable": not bool(row[3])
                })

            cursor.execute(f"PRAGMA foreign_key_list({table_name});")
            for row in cursor.fetchall():
                foreign_keys.append({
                    "column": row[3],
                    "references_table": row[2],
                    "references_column": row[4]
                })

        return {
            "table": table_name,
            "columns": columns,
            "foreign_keys": foreign_keys
        }

    def _get_descriptive_columns(self, table_name: str) -> List[str]:
        """Dynamically identifies human-readable descriptive columns in a table."""
        try:
            if self.is_mysql:
                raw = self._inspect_mysql_table(table_name)
            else:
                raw = self._inspect_sqlite_table(table_name)
            cols = [c["name"] for c in raw.get("columns", [])]
            return [
                c for c in cols
                if not c.endswith("_id") and any(term in c.lower() for term in ["name", "title", "email", "desc", "code", "label", "text"])
            ]
        except Exception:
            return []

    def format_schema_summary(self, schema_dict: Dict[str, Any]) -> str:
        """Formats the schema inspection dictionary with dynamic 1-hop relationship expansion for LLM context."""
        lines = []
        relationships = []
        seen_relationships = set()

        for table, data in schema_dict.items():
            if "error" in data:
                lines.append(f"- Table `{table}`: [ERROR: {data['error']}]")
                continue

            cols_str = []
            fks = data.get("foreign_keys", [])
            fks_map = {fk["column"]: f"(FK -> {fk['references_table']}.{fk['references_column']})" for fk in fks}
            
            for col in data.get("columns", []):
                col_repr = col["name"]
                if col.get("primary_key"):
                    col_repr += " (PK)"
                elif col["name"] in fks_map:
                    col_repr += f" {fks_map[col['name']]}"
                cols_str.append(col_repr)

            lines.append(f"- Table `{table}`: {', '.join(cols_str)}")

            # Dynamic 1-Hop Foreign Key Graph Expansion
            for fk in fks:
                ref_table = fk.get("references_table")
                ref_col = fk.get("references_column")
                fk_col = fk.get("column")
                rel_key = f"{table}.{fk_col}->{ref_table}.{ref_col}"
                
                if ref_table and ref_col and fk_col and rel_key not in seen_relationships:
                    seen_relationships.add(rel_key)
                    desc_cols = self._get_descriptive_columns(ref_table)
                    desc_hint = f"human-readable fields: {', '.join(desc_cols)}" if desc_cols else f"lookup table `{ref_table}`"
                    relationships.append(
                        f"  * Dynamic Relationship: `{table}.{fk_col}` -> `{ref_table}.{ref_col}` ({desc_hint}). "
                        f"Use `LEFT JOIN {ref_table} ON {table}.{fk_col} = {ref_table}.{ref_col}` (or `JOIN`) to retrieve descriptive names."
                    )

        if relationships:
            lines.append("\nDynamic Schema Relationships & Entity Descriptors:")
            lines.extend(relationships)
            lines.append("  (Note: For human-readable business reporting, prioritize selecting descriptive name fields from related tables over raw numeric ID fields.)")
            lines.append("  (Cardinality Hint: If an entity has multiple related child records, use `DISTINCT` or `GROUP BY` when answering per-entity questions to eliminate duplicate rows.)")
            lines.append("  (Entity Preservation Hint: When reporting on all primary entities alongside optional details, use `LEFT JOIN` and `COALESCE(joined_table.descriptive_column, 'ยังไม่ระบุ')` to ensure entities without registered details are not dropped and show clearly as 'ยังไม่ระบุ'.)")

        return "\n".join(lines)

    def execute_read_only(self, query: str, max_rows: int = Config.MAX_SQL_ROWS_RETURNED) -> Dict[str, Any]:
        """
        Validates SQL AST safety, executes query against database, and returns results.
        """
        # 1. AST Validation
        try:
            validate_ast_safety(query, dialect="mysql" if self.is_mysql else "sqlite")
        except (SQLSecurityError, SQLSyntaxError) as e:
            return {"status": "error", "message": str(e), "error_type": type(e).__name__}

        # 2. Database Execution
        try:
            conn = self.get_connection()
            with conn:
                cursor = conn.cursor()
                cursor.execute(query)
                
                col_names = [d[0] for d in cursor.description] if cursor.description else []
                rows = []
                remaining = max(0, max_rows)
                while remaining:
                    batch = cursor.fetchmany(min(10_000, remaining))
                    if not batch:
                        break
                    if self.is_mysql:
                        rows.extend(
                            {k: serialize_row_value(v) for k, v in row.items()}
                            for row in batch
                        )
                    else:
                        rows.extend(
                            {col_names[i]: serialize_row_value(value) for i, value in enumerate(row)}
                            for row in batch
                        )
                    remaining -= len(batch)

                # Read one extra row to distinguish a complete result from a capped one.
                truncated = bool(cursor.fetchmany(1))

            return {
                "status": "success",
                "row_count": len(rows),
                "rows": rows,
                "truncated": truncated,
                "row_limit": max_rows,
                "columns": col_names
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e),
                "error_type": "DatabaseExecutionError"
            }

    @contextmanager
    def stream_read_only(self, query: str, batch_size: int = Config.SQL_FETCH_BATCH_SIZE):
        """Yield query columns and a bounded-memory iterator without a total-row cap."""
        validate_ast_safety(query, dialect="mysql" if self.is_mysql else "sqlite")
        conn = self.get_connection()
        cursor = None
        try:
            # SSCursor streams MySQL results instead of buffering the full result client-side.
            cursor = conn.cursor(pymysql.cursors.SSDictCursor) if self.is_mysql else conn.cursor()
            cursor.execute(query)
            columns = [description[0] for description in cursor.description] if cursor.description else []

            def iter_rows():
                while True:
                    batch = cursor.fetchmany(batch_size)
                    if not batch:
                        break
                    for row in batch:
                        if isinstance(row, dict):
                            yield {key: serialize_row_value(value) for key, value in row.items()}
                        else:
                            yield {
                                columns[index]: serialize_row_value(value)
                                for index, value in enumerate(row)
                            }

            yield {"columns": columns, "rows": iter_rows()}
        finally:
            try:
                if cursor is not None:
                    cursor.close()
            finally:
                conn.close()
