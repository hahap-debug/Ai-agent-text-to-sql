"""
Agent Data Models & Step Definitions
Defines AgentStep and AgentRunResult dataclasses.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

@dataclass
class AgentStep:
    """Represents a single step in the ReAct reasoning trajectory."""
    step_number: int
    thought: str = ""
    tool_name: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    observation: Any = None
    is_error: bool = False

@dataclass
class AgentRunResult:
    """Encapsulates the final outcome of an Agent execution run."""
    user_question: str
    final_answer: str
    steps: List[AgentStep] = field(default_factory=list)
    last_executed_sql: Optional[str] = None
    last_query_result: Optional[List[Dict[str, Any]]] = None
    success: bool = True
    error_message: Optional[str] = None
    expanded_question: Optional[str] = None
    excel_file_path: Optional[str] = None
    excel_file_name: Optional[str] = None
    excel_sheets: Optional[List[str]] = None
