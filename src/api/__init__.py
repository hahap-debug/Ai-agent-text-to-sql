"""
Tier 2: API Service Layer (FastAPI)
Provides REST and Server-Sent Events (SSE) streaming endpoints for the AI Data Agent.
"""

from src.api.app import create_app

__all__ = ["create_app"]
