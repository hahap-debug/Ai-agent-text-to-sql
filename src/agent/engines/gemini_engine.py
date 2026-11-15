"""
Gemini Cloud ReAct Engine
Uses official Google GenAI SDK with Tool Calling and Self-Healing.
"""

import json
from typing import List, Dict, Any, Optional, Callable
from src.agent.models import AgentStep, AgentRunResult
from src.agent.rules import is_quota_error, sanitize_sql_limits
from src.agent.narrative import format_thai_narrative
from src.prompts import MASTER_SYSTEM_PROMPT


def run_gemini_react(
    agent: Any,
    user_question: str,
    step_callback: Optional[Callable[[AgentStep], None]] = None,
    chat_history: Optional[List[Dict[str, Any]]] = None
) -> AgentRunResult:
    """Runs the ReAct loop using official Google GenAI with Tool Calling & Self-Healing."""
    from google.genai import types

    steps: List[AgentStep] = []
    last_sql_box = {"sql": None, "result": None}

    def inspect_schema(tables: List[str]) -> str:
        obs_dict = agent.inspect_schema(tables)
        obs_str = obs_dict.get("summary", "")
        step = AgentStep(
            step_number=len(steps) + 1,
            thought="ตรวจสอบโครงสร้างตารางเพื่อดูชื่อคอลัมน์และ Foreign Keys ที่แท้จริง",
            tool_name="inspect_schema",
            parameters={"tables": tables},
            observation=obs_str
        )
        steps.append(step)
        if step_callback:
            step_callback(step)
        return obs_str

    def execute_sql(query: str) -> str:
        clean_query = sanitize_sql_limits(query, user_question)
        last_sql_box["sql"] = clean_query
        exec_res = agent.execute_sql(clean_query)
        step = AgentStep(
            step_number=len(steps) + 1,
            thought="ส่งคำสั่ง SQL ที่ผ่านการตรวจสอบไวยากรณ์ไปรันบนฐานข้อมูล ecommerce_db",
            tool_name="execute_sql",
            parameters={"query": clean_query}
        )
        if exec_res.get("status") == "success":
            rows = exec_res.get("rows", [])
            last_sql_box["result"] = rows
            step.observation = rows
        else:
            step.is_error = True
            step.observation = f"ERROR: {exec_res.get('message')}"
        steps.append(step)
        if step_callback:
            step_callback(step)
        return json.dumps(exec_res, ensure_ascii=False)

    tools = [inspect_schema, execute_sql]
    quota_exceeded = False
    error_details = None

    try:
        chat = agent.gemini_client.chats.create(
            model=agent.model_name,
            config=types.GenerateContentConfig(
                system_instruction=MASTER_SYSTEM_PROMPT,
                tools=tools,
                temperature=0.1
            )
        )

        # Multi-Turn: Send previous context summary if chat_history exists
        if chat_history:
            for item in chat_history[-2:]:
                if item.get("role") == "user":
                    chat.send_message(f"[บริบทคำถามก่อนหน้า]: {item.get('content')}")
                elif item.get("role") == "assistant":
                    asst_summary = item.get("content", "")[:250]
                    sql_info = f" [SQL ที่เคยรัน: {item.get('sql')}]" if item.get("sql") else ""
                    chat.send_message(f"[ผลลัพธ์บริบทก่อนหน้า]: {asst_summary}{sql_info}")

        response = chat.send_message(user_question)
        final_text = getattr(response, "text", "") or ""
    except Exception as e:
        if is_quota_error(e):
            quota_exceeded = True
            error_details = str(e)
            final_text = (
                "⚠️ **Ran out of quota:** โควตาการใช้งานของ Google Gemini API หมดแล้ว (Rate Limit / Quota Exceeded)\n\n"
                "ระบบไม่สามารถเรียกใช้ Gemini ได้ในขณะนี้เนื่องจากติดโควตาคำขอฟรีหรือถึงขีดจำกัดของบัญชี (429 RESOURCE_EXHAUSTED)\n\n"
                "💡 **คำแนะนำในการใช้งานต่อ:**\n"
                "- สลับไปใช้ **🖥️ Local Ollama (`qwen2.5-coder:7b`)** ที่แถบเมนูด้านซ้าย (รันบนเครื่อง 100% ไม่มีข้อจำกัดโควตา)\n"
                "- หรือรอประมาณ 1-2 นาทีเพื่อให้อัตราโควตารีเซ็ต แล้วลองส่งคำถามใหม่อีกครั้ง"
            )
        else:
            final_text = f"❌ เกิดข้อผิดพลาดในการประมวลผลผ่าน Gemini: {e}"
            error_details = str(e)

    last_sql = last_sql_box["sql"]
    last_result = last_sql_box["result"]

    if not quota_exceeded and ("สรุปผลลัพธ์สำคัญ" not in final_text or not final_text.strip()) and last_result:
        final_text = format_thai_narrative(user_question, last_sql or "", last_result)

    return AgentRunResult(
        user_question=user_question,
        final_answer=final_text if final_text else "ไม่สามารถประมวลผลคำตอบได้",
        steps=steps,
        last_executed_sql=last_sql,
        last_query_result=last_result,
        success=False if quota_exceeded or error_details else (True if (last_result is not None or final_text) else False),
        error_message="Ran out of quota (Gemini 429 RESOURCE_EXHAUSTED)" if quota_exceeded else error_details
    )
