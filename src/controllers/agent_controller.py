"""
Agent Controller: Handles natural language queries (Synchronous and SSE Streaming).
"""

import json
import queue
import threading
from typing import Optional, List
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from src.config import Config
from src.services.agent_service import AgentService
from src.models.entities import AgentStep, AgentRunResult
from src.models.schemas import (
    AgentStepDTO,
    ChatRequest,
    ChatResponse,
)

router = APIRouter(tags=["Agent"])


def get_agent(provider: Optional[str] = None, model_name: Optional[str] = None) -> AgentService:
    """Factory helper to obtain an AgentService instance."""
    return AgentService(
        provider=provider or Config.LLM_PROVIDER,
        model_name=model_name
    )


def step_to_dto(step: AgentStep) -> AgentStepDTO:
    return AgentStepDTO(
        step_number=step.step_number,
        thought=step.thought,
        tool_name=step.tool_name,
        parameters=step.parameters,
        observation=step.observation,
        is_error=step.is_error
    )


def run_result_to_response(res: AgentRunResult) -> ChatResponse:
    return ChatResponse(
        user_question=res.user_question,
        final_answer=res.final_answer,
        steps=[step_to_dto(s) for s in res.steps],
        last_executed_sql=res.last_executed_sql,
        last_query_result=res.last_query_result,
        expanded_question=res.expanded_question,
        success=res.success,
        error_message=res.error_message,
        excel_file_path=res.excel_file_path,
        excel_file_name=res.excel_file_name,
        excel_sheets=res.excel_sheets
    )


def generate_sse_events(
    agent: AgentService,
    question: str,
    chat_history: Optional[List[dict]] = None
):
    """Generator yielding formatted Server-Sent Events (SSE) strings."""
    event_queue: queue.Queue = queue.Queue()

    def step_callback(step: AgentStep):
        event_queue.put({
            "event": "step",
            "data": step_to_dto(step).model_dump()
        })

    def background_worker():
        try:
            res = agent.run(
                user_question=question,
                step_callback=step_callback,
                chat_history=chat_history
            )
            event_queue.put({
                "event": "done",
                "data": run_result_to_response(res).model_dump()
            })
        except Exception as e:
            event_queue.put({
                "event": "error",
                "data": {"message": str(e)}
            })
        finally:
            event_queue.put(None)

    threading.Thread(target=background_worker, daemon=True).start()

    while True:
        item = event_queue.get()
        if item is None:
            break
        event_name = item.get("event", "message")
        json_payload = json.dumps(item.get("data", {}), ensure_ascii=False)
        yield f"event: {event_name}\ndata: {json_payload}\n\n"


@router.post("/query", response_model=ChatResponse)
def execute_query(req: ChatRequest) -> ChatResponse:
    """Executes full ReAct loop synchronously."""
    agent = get_agent(provider=req.provider, model_name=req.model_name) #Get AgentService
    try:
        result = agent.run(
            user_question=req.question,
            chat_history=req.chat_history
        )
        return run_result_to_response(result)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent execution failed: {str(e)}"
        )


@router.post("/query/stream")
def execute_query_stream(req: ChatRequest):
    """Executes ReAct loop and streams reasoning thoughts live via SSE."""
    agent = get_agent(provider=req.provider, model_name=req.model_name)
    return StreamingResponse(
        generate_sse_events(agent, req.question, req.chat_history),
        media_type="text/event-stream"
    )
