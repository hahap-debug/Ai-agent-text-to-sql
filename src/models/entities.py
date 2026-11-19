"""
Domain Entities for AI Data Agent.
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional


@dataclass #สร้าง init automaically
class AgentStep:
    """Represents a single step in the ReAct reasoning loop."""
    step_number: int
    thought: str
    tool_name: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    observation: Optional[Any] = None
    is_error: bool = False


@dataclass
class AgentRunResult:
    """Represents the complete execution result of the ReAct agent."""
    user_question: str
    final_answer: str
    steps: List[AgentStep]
    last_executed_sql: Optional[str] = None
    last_query_result: Optional[List[Dict[str, Any]]] = None
    expanded_question: Optional[str] = None
    success: bool = True
    error_message: Optional[str] = None
    excel_file_path: Optional[str] = None
    excel_file_name: Optional[str] = None
    excel_sheets: Optional[List[str]] = None
