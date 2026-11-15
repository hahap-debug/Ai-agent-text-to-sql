"""
Python SDK Client for Tier 1 (Presentation) to talk to Tier 2 (FastAPI Service).
Supports both synchronous calls and real-time Server-Sent Events (SSE) streaming.
"""

import json
import requests
from typing import List, Dict, Any, Optional, Callable
from src.api.schemas import ChatResponse, AgentStepDTO, HealthResponse


class AgentAPIClient:
    """Client for interacting with the AI Data Agent via REST / SSE API."""

    def __init__(self, base_url: str = "http://localhost:8000/api/v1", timeout: int = 120):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def check_health(self) -> HealthResponse:
        """Checks API server health and database connectivity."""
        url = f"{self.base_url}/health"
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        return HealthResponse(**resp.json())

    def list_tables(self) -> List[str]:
        """Fetches all table names in ecommerce_db."""
        url = f"{self.base_url}/tables"
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        return resp.json()

    def query(
        self,
        question: str,
        provider: Optional[str] = None,
        model_name: Optional[str] = None,
        chat_history: Optional[List[Dict[str, Any]]] = None
    ) -> ChatResponse:
        """Executes a synchronous query through the API tier."""
        url = f"{self.base_url}/query"
        payload = {
            "question": question,
            "provider": provider,
            "model_name": model_name,
            "chat_history": chat_history
        }
        resp = requests.post(url, json=payload, timeout=self.timeout)
        resp.raise_for_status()
        return ChatResponse(**resp.json())

    def query_stream(
        self,
        question: str,
        step_callback: Optional[Callable[[AgentStepDTO], None]] = None,
        provider: Optional[str] = None,
        model_name: Optional[str] = None,
        chat_history: Optional[List[Dict[str, Any]]] = None
    ) -> ChatResponse:
        """
        Executes query via Server-Sent Events (SSE) and invokes step_callback
        in real-time as each reasoning thought/tool finishes on the server.
        """
        url = f"{self.base_url}/query/stream"
        payload = {
            "question": question,
            "provider": provider,
            "model_name": model_name,
            "chat_history": chat_history
        }

        final_response: Optional[ChatResponse] = None

        with requests.post(url, json=payload, stream=True, timeout=self.timeout) as response:
            response.raise_for_status()
            current_event = None
            for line in response.iter_lines(decode_unicode=True):
                if not line:
                    continue
                if line.startswith("event:"):
                    current_event = line.replace("event:", "").strip()
                elif line.startswith("data:"):
                    data_str = line.replace("data:", "").strip()
                    try:
                        data = json.loads(data_str)
                    except Exception:
                        continue

                    if current_event == "step":
                        step_dto = AgentStepDTO(**data)
                        if step_callback:
                            step_callback(step_dto)
                    elif current_event == "done":
                        final_response = ChatResponse(**data)
                    elif current_event == "error":
                        raise RuntimeError(data.get("message", "Unknown server error"))

        if final_response is None:
            raise RuntimeError("Stream ended without emitting completion event")
        return final_response
