"""
Core DatabaseAgent Implementation
Orchestrates Autonomous ReAct investigation against ecommerce_db using
Ollama, Gemini, or Mock engines.
"""

from typing import List, Dict, Any, Optional, Callable
from src.config import Config
from src.database import DatabaseConnection
from src.agent.models import AgentStep, AgentRunResult
from src.agent.rules import (
    extract_action_json,
    is_quota_error,
    filter_display_fields,
    sanitize_sql_limits,
)
from src.agent.narrative import format_thai_narrative
from src.agent.coreference import reformulate_query_with_context
from src.agent.engines import (
    run_ollama_react,
    run_gemini_react,
    run_mock_react,
)


class DatabaseAgent:
    """
    Autonomous ReAct Database Agent for ecommerce_db.
    """

    # Static method bindings for backward compatibility and test access
    filter_display_fields = staticmethod(filter_display_fields)
    sanitize_sql_limits = staticmethod(sanitize_sql_limits)
    _is_quota_error = staticmethod(is_quota_error)
    _format_thai_narrative = staticmethod(format_thai_narrative)

    def __init__(
        self,
        db: Optional[DatabaseConnection] = None,
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        max_steps: int = Config.MAX_REACT_STEPS
    ):
        self.db = db or DatabaseConnection()
        self.provider = (provider or Config.LLM_PROVIDER).lower()
        self.api_key = api_key or Config.GEMINI_API_KEY
        self.model_name = model_name or (Config.GEMINI_MODEL if self.provider == "gemini" else Config.OLLAMA_MODEL)
        self.max_steps = max_steps
        self.gemini_client = None
        self._init_providers()

    def _init_providers(self):
        """Initializes Gemini client if configured."""
        if self.provider == "gemini" and self.api_key and self.api_key != "your_gemini_api_key_here":
            try:
                from google import genai
                self.gemini_client = genai.Client(api_key=self.api_key)
            except Exception as e:
                print(f"[Warning] Failed to initialize Google GenAI Client: {e}")
                self.gemini_client = None

    def inspect_schema(self, tables: List[str]) -> Dict[str, Any]:
        """Tool 1: Inspect exact columns and keys for specified tables."""
        raw_schema = self.db.inspect_schema(tables)
        return {
            "summary": self.db.format_schema_summary(raw_schema),
            "raw": raw_schema
        }

    def execute_sql(self, query: str) -> Dict[str, Any]:
        """Tool 2: Execute read-only SQL query on ecommerce_db."""
        return self.db.execute_read_only(query)

    def reformulate_query_with_context(
        self,
        current_question: str,
        chat_history: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """
        Uses LLM Coreference Resolution to reformulate ambiguous or pronoun-dropped
        follow-up questions into standalone self-contained questions.
        """
        return reformulate_query_with_context(
            current_question=current_question,
            chat_history=chat_history,
            provider=self.provider,
            model_name=self.model_name,
            gemini_client=self.gemini_client
        )

    def _run_ollama_react(
        self,
        user_question: str,
        step_callback: Optional[Callable[[AgentStep], None]] = None,
        chat_history: Optional[List[Dict[str, Any]]] = None
    ) -> AgentRunResult:
        return run_ollama_react(self, user_question, step_callback, chat_history)

    def _run_gemini_react(
        self,
        user_question: str,
        step_callback: Optional[Callable[[AgentStep], None]] = None,
        chat_history: Optional[List[Dict[str, Any]]] = None
    ) -> AgentRunResult:
        return run_gemini_react(self, user_question, step_callback, chat_history)

    def _run_mock_react(
        self,
        user_question: str,
        step_callback: Optional[Callable[[AgentStep], None]] = None,
        chat_history: Optional[List[Dict[str, Any]]] = None
    ) -> AgentRunResult:
        return run_mock_react(self, user_question, step_callback, chat_history)

    def run(
        self,
        user_question: str,
        step_callback: Optional[Callable[[AgentStep], None]] = None,
        chat_history: Optional[List[Dict[str, Any]]] = None
    ) -> AgentRunResult:
        """
        Executes the ReAct loop for the given business question with Multi-Turn Context Memory & Coreference Resolution.
        """
        active_question = user_question
        expanded = None

        if chat_history and len(chat_history) > 0:
            expanded = self.reformulate_query_with_context(user_question, chat_history)
            if expanded and expanded != user_question:
                active_question = expanded

        if self.provider == "ollama":
            res = self._run_ollama_react(active_question, step_callback, chat_history)
        elif self.provider == "gemini":
            if self.gemini_client is not None:
                res = self._run_gemini_react(active_question, step_callback, chat_history)
            else:
                return AgentRunResult(
                    user_question=user_question,
                    final_answer="❌ **ไม่ได้ระบุ Gemini API Key:** กรุณาใส่ API Key ใน Sidebar หรือในไฟล์ `.env`",
                    success=False,
                    error_message="Gemini API Key missing"
                )
        elif self.provider == "mock":
            res = self._run_mock_react(active_question, step_callback, chat_history)
        else:
            res = self._run_ollama_react(active_question, step_callback, chat_history)

        res.user_question = user_question
        res.expanded_question = expanded if (expanded and expanded != user_question) else None
        if res.last_query_result:
            res.last_query_result = self.filter_display_fields(res.last_query_result)
        return res
