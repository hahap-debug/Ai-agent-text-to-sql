"""
Configuration Module for AI Data Analytics Agent
Loads environment variables and sets database and LLM parameters.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Base directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env file
load_dotenv(BASE_DIR / ".env", override=True)

class Config:
    # Database Settings
    DB_TYPE = os.getenv("DB_TYPE", "mysql").lower()
    DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
    DB_PORT = int(os.getenv("DB_PORT", "3306"))
    DB_USER = os.getenv("DB_USER", "ecommerce_reader")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "reader_pass123")
    DB_NAME = os.getenv("DB_NAME", "ecommerce_db")
    DB_CHARSET = os.getenv("DB_CHARSET", "utf8mb4")

    # Admin User
    DB_ADMIN_USER = os.getenv("DB_ADMIN_USER", "root")
    DB_ADMIN_PASSWORD = os.getenv("DB_ADMIN_PASSWORD", "admin123")

    # SQLite (Fallback/Testing mode)
    SQLITE_DB_PATH = str(BASE_DIR / os.getenv("SQLITE_DB_PATH", "data/ecommerce.db"))

    # LLM Settings
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama").lower()
    
    # Ollama Settings
    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b")
    OLLAMA_SQL_MODEL = os.getenv("OLLAMA_SQL_MODEL", "qwen2.5-coder:7b")
    OLLAMA_TEMPERATURE = float(os.getenv("OLLAMA_TEMPERATURE", "0.0"))
    OLLAMA_TIMEOUT_SECONDS = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "600"))  # 10 minutes timeout
    MAX_LLM_RETRIES = int(os.getenv("MAX_LLM_RETRIES", "2"))

    # Gemini Settings
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "") or os.getenv("GOOGLE_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")

    # Agent Limits & Safety
    MAX_REACT_STEPS = int(os.getenv("MAX_REACT_STEPS", "6"))
    MAX_RESULT_ROWS = int(os.getenv("MAX_RESULT_ROWS", "1000"))
    MAX_SQL_ROWS_RETURNED = MAX_RESULT_ROWS
    DEFAULT_ROW_LIMIT = int(os.getenv("DEFAULT_ROW_LIMIT", "1000"))
    SQL_TIMEOUT_SECONDS = int(float(os.getenv("QUERY_TIMEOUT_SECONDS", "5.0")))

    @classmethod
    def is_api_key_set(cls) -> bool:
        return cls.is_gemini_available()

    @classmethod
    def is_gemini_available(cls) -> bool:
        return bool(cls.GEMINI_API_KEY and cls.GEMINI_API_KEY != "your_gemini_api_key_here")
