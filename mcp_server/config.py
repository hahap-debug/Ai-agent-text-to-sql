"""
MCP Server Configuration Module
Loads database credentials and environment settings.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

class MCPConfig:
    # Database Settings
    DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
    DB_PORT = int(os.getenv("DB_PORT", "3306"))
    DB_USER = os.getenv("DB_USER", "ecommerce_reader")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "reader_pass123")
    DB_NAME = os.getenv("DB_NAME", "ecommerce_db")
    DB_CHARSET = os.getenv("DB_CHARSET", "utf8mb4")

    # Safety Limits
    MAX_ROWS = int(os.getenv("MAX_RESULT_ROWS", "100"))
    DEFAULT_LIMIT = int(os.getenv("DEFAULT_ROW_LIMIT", "50"))
    QUERY_TIMEOUT = float(os.getenv("QUERY_TIMEOUT_SECONDS", "5.0"))
