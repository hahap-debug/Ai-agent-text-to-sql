"""
NVIDIA NIM Provider: Executes ReAct loop using OpenAI-compatible client with Tool Calling on NVIDIA Cloud.
"""

import json
from typing import List, Dict, Any, Optional, Callable
from openai import OpenAI
from src.models.entities import AgentStep, AgentRunResult
from src.services.sql_guard_service import SQLGuardService
from src.services.narrative_service import NarrativeService
from src.prompts import NVIDIA_SYSTEM_PROMPT, MASTER_SYSTEM_PROMPT


NVIDIA_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "inspect_schema",
            "description": "Inspect exact column names, data types, primary keys, and foreign keys for specific tables in ecommerce_db.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tables": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of table names to inspect, e.g. ['orders', 'users']"
                    }
                },
                "required": ["tables"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "execute_sql",
            "description": "Execute a validated, read-only SQL SELECT query on ecommerce_db. Mutations (INSERT, UPDATE, DELETE, DROP) are blocked.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Standard MySQL 8.x SELECT query."
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_multi_sheet_excel",
            "description": "Create a multi-tab Excel workbook on the user Desktop from SQL queries.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_name": {
                        "type": "string",
                        "description": "Target Excel filename ending with .xlsx"
                    },
                    "sheets": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "sheet_name": {"type": "string"},
                                "query": {"type": "string"},
                                "theme_color": {"type": "string"}
                            },
                            "required": ["sheet_name", "query"]
                        }
                    }
                },
                "required": ["file_name", "sheets"]
            }
        }
    }
]


def run_nvidia_react(
    agent: Any,
    user_question: str,
    step_callback: Optional[Callable[[AgentStep], None]] = None,
    chat_history: Optional[List[Dict[str, Any]]] = None
) -> AgentRunResult:
    """Runs the ReAct loop using NVIDIA NIM (OpenAI-compatible) API."""
    steps: List[AgentStep] = []
    last_sql_box = {"sql": None, "result": None}
    excel_box = {"file_path": None, "file_name": None, "sheets": None}

    client = agent.nvidia_client
    if not client:
        return AgentRunResult(
            user_question=user_question,
            final_answer="❌ **ไม่ได้ระบุ NVIDIA API Key:** กรุณาตรวจสอบค่า `NVIDIA_API_KEY` ในไฟล์ `.env`",
            success=False,
            error_message="NVIDIA API Key missing"
        )

    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": NVIDIA_SYSTEM_PROMPT}
    ]

    if chat_history:
        for item in chat_history:
            role = item.get("role")
            content = str(item.get("content", "")).strip()
            if not content:
                continue
            if role == "user":
                messages.append({"role": "user", "content": content})
            elif role in ("assistant", "model"):
                messages.append({"role": "assistant", "content": content})

    messages.append({"role": "user", "content": user_question})

    max_turns = agent.max_steps or 6
    final_text = ""
    error_details = None

    for turn in range(max_turns):
        try:
            response = client.chat.completions.create(
                model=agent.model_name,
                messages=messages,
                tools=NVIDIA_TOOLS,
                tool_choice="auto",
                temperature=0.1,
                max_tokens=1500
            )
            msg = response.choices[0].message
            #list[dict]
            tool_calls = getattr(msg, "tool_calls", None)

            if not tool_calls:
                final_text = msg.content or ""
                if not final_text and getattr(msg, "reasoning_content", None):
                    final_text = str(msg.reasoning_content)
                break

            # Handle Tool Calls
            messages.append(msg)

            for tc in tool_calls:
                fn_name = tc.function.name
                fn_args_raw = tc.function.arguments or "{}"
                try:
                    fn_args = json.loads(fn_args_raw) #json to python object
                except Exception:
                    fn_args = {}

                step = AgentStep(
                    step_number=len(steps) + 1,
                    thought=f"เรียกใช้เครื่องมือ {fn_name} เพื่อรวบรวมข้อมูล",
                    tool_name=fn_name,
                    parameters=fn_args
                )

                if fn_name == "inspect_schema":
                    tables = fn_args.get("tables", [])
                    obs_dict = agent.inspect_schema(tables)
                    obs_str = obs_dict.get("summary", "") #summary = schme in easy to read format.
                    step.observation = obs_str
                    tool_output = obs_str

                elif fn_name == "execute_sql":
                    query = fn_args.get("query", "")
                    clean_query = SQLGuardService.sanitize_sql_limits(query, user_question)
                    last_sql_box["sql"] = clean_query
                    exec_res = agent.execute_sql(clean_query)
                    if exec_res.get("status") == "success":
                        rows = exec_res.get("rows", [])
                        last_sql_box["result"] = rows
                        step.observation = rows
                    else:
                        step.is_error = True
                        step.observation = f"ERROR: {exec_res.get('message')}"
                    tool_output = json.dumps(exec_res, ensure_ascii=False)

                elif fn_name == "create_multi_sheet_excel":
                    fname = fn_args.get("file_name", "report.xlsx")
                    sheets = fn_args.get("sheets", [])
                    res = agent.create_multi_sheet_excel(fname, sheets)
                    if res.get("status") == "success":
                        excel_box["file_path"] = res.get("file_path")
                        excel_box["file_name"] = res.get("file_name")
                        excel_box["sheets"] = res.get("sheets")
                        step.observation = res
                    else:
                        step.is_error = True
                        step.observation = f"ERROR: {res.get('error')}"
                    tool_output = json.dumps(res, ensure_ascii=False)

                else:
                    tool_output = json.dumps({"error": f"Unknown tool: {fn_name}"})

                steps.append(step)
                if step_callback:
                    step_callback(step)

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": fn_name,
                    "content": tool_output
                })

        except Exception as e:
            error_details = str(e)
            final_text = f"❌ เกิดข้อผิดพลาดในการประมวลผลผ่าน NVIDIA NIM: {e}"
            break

    last_sql = last_sql_box["sql"]
    last_result = last_sql_box["result"]

    if ("สรุปผลลัพธ์สำคัญ" not in final_text or not final_text.strip()) and last_result:
        final_text = NarrativeService.format_thai_narrative(user_question, last_sql or "", last_result)

    return AgentRunResult(
        user_question=user_question,
        final_answer=final_text if final_text else "ไม่สามารถประมวลผลคำตอบได้",
        steps=steps,
        last_executed_sql=last_sql,
        last_query_result=last_result,
        success=bool(last_result is not None or excel_box["file_path"] or final_text) and not bool(error_details),
        error_message=error_details,
        excel_file_path=excel_box["file_path"],
        excel_file_name=excel_box["file_name"],
        excel_sheets=excel_box["sheets"]
    )
