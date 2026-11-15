"""
Pydantic Data Transfer Objects (DTO) for Controller & API Layer.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class AgentStepDTO(BaseModel):
    step_number: int = Field(..., description="Step sequence number (1, 2, ...)")
    thought: str = Field(..., description="Reasoning thought in Thai")
    tool_name: Optional[str] = Field(None, description="Tool invoked (inspect_schema or execute_sql)")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Parameters passed to the tool")
    observation: Optional[Any] = Field(None, description="Tool execution result or summary")
    is_error: bool = Field(False, description="Flag indicating if this step encountered an error")


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, description="Natural language question in Thai")
    provider: Optional[str] = Field(None, description="LLM provider: 'ollama', 'gemini', or 'mock'")
    model_name: Optional[str] = Field(None, description="Model identifier override")
    chat_history: Optional[List[Dict[str, Any]]] = Field(None, description="Multi-turn conversation history")


class ChatResponse(BaseModel):
    user_question: str
    final_answer: str
    steps: List[AgentStepDTO]
    last_executed_sql: Optional[str] = None
    last_query_result: Optional[List[Dict[str, Any]]] = None
    expanded_question: Optional[str] = None
    success: bool
    error_message: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    database: str
    db_type: str
    active_provider: str
    version: str = "2.0.0"


class SchemaInspectRequest(BaseModel):
    tables: List[str] = Field(..., min_length=1, description="List of table names to inspect")


class SchemaInspectResponse(BaseModel):
    tables: List[str]
    summary: str
    raw: Dict[str, Any]
