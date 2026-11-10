"""
Database Connection Helper for MCP Server
Provides read-only connections to MySQL ecommerce_db.
"""

import pymysql
from typing import Dict, Any, List, Optional
from mcp_server.config import MCPConfig

class MCPDatabase:
    @staticmethod
    def get_connection():
        return pymysql.connect(
            host=MCPConfig.DB_HOST,
            port=MCPConfig.DB_PORT,
            user=MCPConfig.DB_USER,
            password=MCPConfig.DB_PASSWORD,
            database=MCPConfig.DB_NAME,
            charset=MCPConfig.DB_CHARSET,
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=int(MCPConfig.QUERY_TIMEOUT)
        )

    @classmethod
    def test_connection(cls) -> bool:
        try:
            conn = cls.get_connection()
            conn.close()
            return True
        except Exception:
            return False
