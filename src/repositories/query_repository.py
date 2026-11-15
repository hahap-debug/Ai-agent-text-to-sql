"""
Query Repository: Manages database connections, type serialization,
and safe read-only SQL execution against MySQL and SQLite.
"""

import socket
import datetime
from decimal import Decimal
from typing import List, Dict, Any, Tuple
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


class QueryRepository:
    """
    Handles physical database connection lifecycle and read-only query execution.
    Features fast socket probing to avoid hanging on dead/sandboxed ports.
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
        """Creates and returns a connection with fast socket probing and fallback."""
        if self.db_type == "mysql" and not self.fallback_active:
            # Fast socket pre-check to prevent blocking on closed/firewalled ports
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
                return pymysql.connect(
                    host=self.host,
                    port=self.port,
                    user=self.user,
                    password=self.password,
                    database=self.database,
                    charset=Config.DB_CHARSET,
                    cursorclass=pymysql.cursors.DictCursor,
                    connect_timeout=3 if self.auto_fallback else Config.SQL_TIMEOUT_SECONDS,
                    autocommit=True
                )
            except Exception as e:
                if self.auto_fallback:
                    self.fallback_active = True
                    conn = sqlite3.connect(self.sqlite_path, timeout=Config.SQL_TIMEOUT_SECONDS)
                    conn.row_factory = sqlite3.Row
                    return conn
                raise e

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

    def execute_read_only(self, query: str) -> Dict[str, Any]:
        """
        Executes read-only SQL query on ecommerce_db with AST safety enforcement.
        """
        # 1. AST Validation
        try:
            validate_ast_safety(query)
        except (SQLSecurityError, SQLSyntaxError) as e:
            return {
                "status": "error",
                "message": f"Security/Syntax Violation: {str(e)}",
                "rows": [],
                "row_count": 0
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Validation Error: {str(e)}",
                "rows": [],
                "row_count": 0
            }

        # 2. Database Execution
        try:
            conn = self.get_connection()
            with conn:
                cursor = conn.cursor()
                cursor.execute(query)
                raw_rows = cursor.fetchall()

                # Normalize rows into standard list of dicts
                rows = []
                for r in raw_rows:
                    if isinstance(r, dict):
                        row_dict = {k: serialize_row_value(v) for k, v in r.items()}
                    else:
                        # SQLite sqlite3.Row object
                        row_dict = {k: serialize_row_value(r[k]) for k in r.keys()}
                    rows.append(row_dict)

                return {
                    "status": "success",
                    "rows": rows,
                    "row_count": len(rows),
                    "dialect": "mysql" if self.is_mysql else "sqlite"
                }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e),
                "rows": [],
                "row_count": 0
            }
