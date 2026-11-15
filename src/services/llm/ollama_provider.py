"""
Ollama Provider: Executes ReAct loop on local Ollama instance (qwen2.5-coder:7b).
"""

import json
import re
import urllib.request
from typing import List, Dict, Any, Optional, Callable

from src.config import Config
from src.models.entities import AgentStep, AgentRunResult
from src.services.sql_guard_service import SQLGuardService
from src.services.narrative_service import NarrativeService
from src.prompts import MASTER_SYSTEM_PROMPT


def run_ollama_react(
    agent: Any,
    user_question: str,
    step_callback: Optional[Callable[[AgentStep], None]] = None,
    chat_history: Optional[List[Dict[str, Any]]] = None
) -> AgentRunResult:
    """Executes ReAct loop with local Ollama instance with Multi-Turn Context Memory."""
    system_instruction = (
        MASTER_SYSTEM_PROMPT
        + "\n\n==================================================\n"
        + "CRITICAL LANGUAGE CONSTRAINT:\n"
        + "- Write all Thoughts (Thought: ...), steps, and answers in professional THAI (ภาษาไทย) ONLY.\n"
        + "- ABSOLUTELY NEVER output Chinese (中文/汉字). English is allowed only for SQL code and table names."
    )
    messages = [
        {"role": "system", "content": system_instruction}
    ]

    # Multi-Turn Context Injection
    if chat_history:
        history_pairs = []
        for i in range(len(chat_history) - 1, -1, -1):
            if chat_history[i].get("role") == "assistant":
                for j in range(i - 1, -1, -1):
                    if chat_history[j].get("role") == "user":
                        history_pairs.insert(0, (
                            chat_history[j].get("content", ""),
                            str(chat_history[i].get("content", ""))[:250],
                            chat_history[i].get("sql")
                        ))
                        break
                if len(history_pairs) >= 2:
                    break

        if history_pairs:
            ctx_lines = ["[ประวัติการสนทนาก่อนหน้านี้เพื่ออ้างอิงบริบท (Context Memory)]:"]
            for q_prev, a_prev, sql_prev in history_pairs:
                sql_hint = f" (SQL ที่ใช้: `{sql_prev}`)" if sql_prev else ""
                ctx_lines.append(f"- ผู้ใช้ถาม: {q_prev}\n  สรุปคำตอบ: {a_prev}{sql_hint}")
            messages.append({"role": "system", "content": "\n".join(ctx_lines)})

    messages.append({"role": "user", "content": user_question})

    steps: List[AgentStep] = []
    last_sql = None
    last_result = None
    step_num = 1

    tools_schema = [
        {
            "type": "function",
            "function": {
                "name": "inspect_schema",
                "description": "Get exact column names, data types, and foreign key relations for specific tables in ecommerce_db.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "tables": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of table names to inspect (e.g. ['orders', 'users'])"
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
                "description": "Execute a validated read-only SQL SELECT query against ecommerce_db and retrieve resulting rows in JSON format.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Standard MySQL 8.x SELECT query adhering to ONLY_FULL_GROUP_BY."
                        }
                    },
                    "required": ["query"]
                }
            }
        }
    ]

    #make understand right here
    for _ in range(agent.max_steps):
        payload = {
            "model": agent.model_name,
            "messages": messages,
            "tools": tools_schema,
            "stream": False,
            "options": {
                "temperature": 0.1,
                "top_p": 0.8
            }
        }

        try:
            req = urllib.request.Request(
                f"{Config.OLLAMA_BASE_URL}/api/chat",
                headers={"Content-Type": "application/json"},
                data=json.dumps(payload).encode()
            )
            with urllib.request.urlopen(req, timeout=Config.OLLAMA_TIMEOUT_SECONDS) as resp:
                resp_data = json.loads(resp.read().decode())
        except Exception as e:
            return AgentRunResult(
                user_question=user_question,
                final_answer=f"❌ เกิดข้อผิดพลาดในการเรียกใช้ Local LLM (Ollama): {e}\n\nกรุณาตรวจสอบว่า Ollama กำลังรันอยู่ที่ {Config.OLLAMA_BASE_URL} และติดตั้งโมเดล `{agent.model_name}` เรียบร้อยแล้ว",
                steps=steps,
                last_executed_sql=last_sql,
                last_query_result=last_result,
                success=False,
                error_message=str(e)
            )

        assistant_msg = resp_data.get("message", {})
        messages.append(assistant_msg)

        tool_calls = assistant_msg.get("tool_calls", [])
        is_text_action = False

        if not tool_calls and assistant_msg.get("content"):
            content_text = assistant_msg.get("content", "")
            action_data = SQLGuardService.extract_action_json(content_text)
            if action_data:
                tool_name = action_data.get("tool") or action_data.get("name")
                tool_params = action_data.get("parameters") or action_data.get("arguments") or {}
                if tool_name in ["inspect_schema", "execute_sql"]:
                    tool_calls = [{
                        "function": {
                            "name": tool_name,
                            "arguments": tool_params
                        }
                    }]
                    is_text_action = True

        if tool_calls:
            for tc in tool_calls:
                fn_name = tc.get("function", {}).get("name")
                fn_args = tc.get("function", {}).get("arguments", {})
                if isinstance(fn_args, str):
                    try:
                        fn_args = json.loads(fn_args)
                    except Exception:
                        fn_args = {}

                thought_text = assistant_msg.get("content", "").strip()
                thought_match = re.search(r"Thought:\s*(.*?)(?=\nAction:|$)", thought_text, re.DOTALL)
                if thought_match:
                    thought_text = thought_match.group(1).strip()

                if not thought_text or is_text_action or re.search(r"[\u4e00-\u9fff]", thought_text):
                    if fn_name == "inspect_schema":
                        tables_str = ", ".join(fn_args.get("tables", []))
                        thought_text = f"ตรวจสอบโครงสร้างและคอลัมน์ของตาราง `{tables_str}` เพื่อเตรียมสร้างคำสั่ง SQL"
                    elif fn_name == "execute_sql":
                        thought_text = "สร้างและประมวลผลคำสั่ง SQL SELECT เพื่อดึงข้อมูลที่ตรงตามคำถาม"
                    else:
                        thought_text = f"กำลังประมวลผลผ่านเครื่องมือ `{fn_name}`"

                step = AgentStep(
                    step_number=step_num,
                    thought=thought_text,
                    tool_name=fn_name,
                    parameters=fn_args
                )

                if fn_name == "inspect_schema":
                    tables = fn_args.get("tables", [])
                    obs_dict = agent.inspect_schema(tables)
                    obs_str = obs_dict["summary"]
                    step.observation = obs_str
                    if is_text_action:
                        messages.append({"role": "user", "content": f"Observation:\n{obs_str}"})
                    else:
                        messages.append({"role": "tool", "content": obs_str})
                elif fn_name == "execute_sql":
                    sql_query = fn_args.get("query", "")
                    clean_sql = SQLGuardService.sanitize_sql_limits(sql_query, user_question)
                    last_sql = clean_sql
                    step.parameters = {"query": clean_sql}
                    exec_res = agent.execute_sql(clean_sql)
                    if exec_res.get("status") == "success":
                        last_result = exec_res.get("rows", [])
                        step.observation = exec_res.get("rows", [])
                        compact_payload = {
                            "status": "success",
                            "total_rows_returned": len(last_result),
                            "sample_rows": last_result[:10]
                        }
                        obs_str = json.dumps(compact_payload, ensure_ascii=False)
                    else:
                        step.is_error = True
                        step.observation = f"ERROR: {exec_res.get('message')}"
                        obs_str = json.dumps(exec_res, ensure_ascii=False)

                    if is_text_action:
                        messages.append({"role": "user", "content": f"Observation:\n{obs_str}"})
                    else:
                        messages.append({"role": "tool", "content": obs_str})

                steps.append(step)
                if step_callback:
                    step_callback(step)
                step_num += 1
        else:
            final_text = assistant_msg.get("content", "")
            if re.search(r"[\u4e00-\u9fff]", final_text) or "สรุปผลลัพธ์สำคัญ" not in final_text:
                if last_result is not None:
                    final_text = NarrativeService.format_thai_narrative(user_question, last_sql or "", last_result)

            return AgentRunResult(
                user_question=user_question,
                final_answer=final_text,
                steps=steps,
                last_executed_sql=last_sql,
                last_query_result=last_result,
                success=True
            )

    if last_result is not None:
        final_text = NarrativeService.format_thai_narrative(user_question, last_sql or "", last_result)
        return AgentRunResult(
            user_question=user_question,
            final_answer=final_text,
            steps=steps,
            last_executed_sql=last_sql,
            last_query_result=last_result,
            success=True
        )

    return AgentRunResult(
        user_question=user_question,
        final_answer=assistant_msg.get("content", "ดำเนินการถึงขีดจำกัดขั้นตอนการคิดสูงสุด (Max reasoning steps reached)"),
        steps=steps,
        last_executed_sql=last_sql,
        last_query_result=last_result,
        success=False
    )
