"""
Gemini Cloud ReAct Engine
Uses official Google GenAI SDK with Tool Calling and Self-Healing.
"""

import json
from typing import List, Dict, Any, Optional, Callable
from src.agent.models import AgentStep, AgentRunResult
from src.agent.rules import is_quota_error, sanitize_sql_limits
from src.agent.narrative import format_thai_narrative
from src.prompts import GEMINI_SYSTEM_PROMPT


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
            ret_msg = json.dumps(exec_res, ensure_ascii=False) + "\n\n[SYSTEM DIRECTIVE: Data retrieval complete. STOP calling any more tools and deliver your Final Answer in Thai immediately.]"
        else:
            step.is_error = True
            step.observation = f"ERROR: {exec_res.get('message')}"
            ret_msg = json.dumps(exec_res, ensure_ascii=False)
        steps.append(step)
        if step_callback:
            step_callback(step)
        return ret_msg

    excel_box = {"file_path": None, "file_name": None, "sheets": None}

    def create_multi_sheet_excel(file_name: str, sheets: List[Dict[str, Any]]) -> str:
        step = AgentStep(
            step_number=len(steps) + 1,
            thought="สร้างรายงาน Excel แบบหลายแท็บ (Multi-Worksheet) พร้อมจัดฟอร์แมตตัวเลขและสีหัวตาราง บันทึกลง Desktop",
            tool_name="create_multi_sheet_excel",
            parameters={"file_name": file_name, "sheets_count": len(sheets) if isinstance(sheets, list) else 0}
        )
        res = agent.create_multi_sheet_excel(file_name, sheets)
        if res.get("status") == "success":
            excel_box["file_path"] = res.get("file_path")
            excel_box["file_name"] = res.get("file_name")
            excel_box["sheets"] = res.get("sheets")
            step.observation = res
            ret_msg = json.dumps(res, ensure_ascii=False) + "\n\n[SYSTEM DIRECTIVE: Excel created successfully. STOP calling any more tools and deliver your Final Answer in Thai immediately.]"
        else:
            step.is_error = True
            step.observation = f"ERROR: {res.get('error', 'Failed to create Excel workbook')}"
            ret_msg = json.dumps(res, ensure_ascii=False)
        steps.append(step)
        if step_callback:
            step_callback(step)
        return ret_msg

    tools = [inspect_schema, execute_sql, create_multi_sheet_excel]
    quota_exceeded = False
    error_details = None

    # Multi-Turn: For Gemini (1M+ context window), inject ALL chat history into chat session
    initial_history: List[types.Content] = []
    if chat_history:
        for item in chat_history:
            role = item.get("role")
            content_text = str(item.get("content", "")).strip()
            if not content_text:
                continue
            if role == "user":
                initial_history.append(
                    types.Content(
                        role="user",
                        parts=[types.Part.from_text(text=content_text)]
                    )
                )
            elif role in ("assistant", "model"):
                sql_info = f"\n\n[Executed SQL: {item.get('sql')}]" if item.get("sql") else ""
                full_text = f"{content_text}{sql_info}"
                initial_history.append(
                    types.Content(
                        role="model",
                        parts=[types.Part.from_text(text=full_text)]
                    )
                )

    try:
        chat = agent.gemini_client.chats.create(
            model=agent.model_name,
            config=types.GenerateContentConfig(
                system_instruction=GEMINI_SYSTEM_PROMPT,
                tools=tools,
                temperature=0.1
            ),
            history=initial_history if initial_history else None
        )

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
        success=False if quota_exceeded or (error_details and not excel_box["file_path"]) else (True if (last_result is not None or excel_box["file_path"] or final_text) else False),
        error_message="Ran out of quota (Gemini 429 RESOURCE_EXHAUSTED)" if quota_exceeded else error_details,
        excel_file_path=excel_box["file_path"],
        excel_file_name=excel_box["file_name"],
        excel_sheets=excel_box["sheets"]
    )
