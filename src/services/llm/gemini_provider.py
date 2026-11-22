"""
Gemini Provider: Executes ReAct loop using Google GenAI SDK with Tool Calling.
"""

import json
from typing import List, Dict, Any, Optional, Callable
from src.models.entities import AgentStep, AgentRunResult
from src.services.sql_guard_service import SQLGuardService
from src.services.narrative_service import NarrativeService
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
    workflow_state = {
        "schema_inspected": False,
        "schema_has_columns": False,
        "query_succeeded": False,
        "excel_attempted": False,
    }

    def inspect_schema(tables: List[str]) -> str:
        obs_dict = agent.inspect_schema(tables)
        workflow_state["schema_inspected"] = True
        raw_schema = obs_dict.get("raw", {})
        workflow_state["schema_has_columns"] = any(
            isinstance(table_info, dict) and bool(table_info.get("columns"))
            for table_info in raw_schema.values()
        )
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
        clean_query = SQLGuardService.sanitize_sql_limits(query, user_question)
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
            workflow_state["query_succeeded"] = True
            step.observation = rows
            ret_msg = json.dumps(exec_res, ensure_ascii=False) + "\n\n[SYSTEM DIRECTIVE: This query result is preliminary. For an in-scope request, create the required Excel workbook with create_multi_sheet_excel before delivering your Final Answer. Do not fetch extra details after workbook success.]"
        else:
            step.is_error = True
            step.observation = f"ERROR: {exec_res.get('message')}"
            ret_msg = json.dumps(exec_res, ensure_ascii=False)
        steps.append(step)
        if step_callback:
            step_callback(step)
        return ret_msg

    excel_box = {"file_path": None, "file_name": None, "sheets": None, "insight_context": []}

    def create_multi_sheet_excel(file_name: str, sheets: List[Dict[str, Any]]) -> str:
        workflow_state["excel_attempted"] = True
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
            excel_box["insight_context"] = res.get("insight_context", [])
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

        # Gemini's automatic function calling can return a final response after
        # schema inspection. Resume the same chat so schema-only output cannot
        # be mistaken for a completed business analysis.
        continuation_attempts = 0
        while (
            not excel_box["file_path"]
            and (
                (workflow_state["schema_inspected"] and workflow_state["schema_has_columns"])
                or workflow_state["query_succeeded"]
                or workflow_state["excel_attempted"]
            )
            and continuation_attempts < 3
        ):
            continuation_attempts += 1
            if workflow_state["query_succeeded"]:
                continuation_prompt = (
                    "The SQL query succeeded, but the required Excel workbook has not been created yet. "
                    "For this in-scope request, call create_multi_sheet_excel using the appropriate read-only query, "
                    "then provide the final Thai answer. Do not stop after the query result."
                )
            elif workflow_state["excel_attempted"]:
                continuation_prompt = (
                    "The Excel tool did not complete successfully. Review its error, correct the sheet query or "
                    "parameters, and call create_multi_sheet_excel again. Then provide the final Thai answer."
                )
            else:
                continuation_prompt = (
                    "You inspected the schema, but schema information is not the business data requested by the user. "
                    "Continue now: write a read-only query and call create_multi_sheet_excel to retrieve the requested "
                    "data and create the workbook, then provide the final Thai answer. Do not answer from schema alone."
                )
            response = chat.send_message(continuation_prompt)
            final_text = getattr(response, "text", "") or final_text

    except Exception as e:
        if SQLGuardService.is_quota_error(e):
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

    workflow_incomplete = (
        not excel_box["file_path"]
        and (
            (workflow_state["schema_inspected"] and workflow_state["schema_has_columns"])
            or workflow_state["query_succeeded"]
            or workflow_state["excel_attempted"]
        )
    )
    if workflow_incomplete and not quota_exceeded:
        error_details = error_details or "The model stopped before creating the required Excel workbook."
        final_text = (
            "⚠️ ตรวจพบโครงสร้างฐานข้อมูลแล้ว แต่ยังดึงข้อมูลหรือสร้างรายงาน Excel ไม่สำเร็จ "
            "กรุณาลองถามอีกครั้ง"
        )

    last_sql = last_sql_box["sql"]
    last_result = last_sql_box["result"]

    if not quota_exceeded and not workflow_incomplete and not excel_box["file_path"] and ("สรุปผลลัพธ์สำคัญ" not in final_text or not final_text.strip()) and last_result:
        final_text = NarrativeService.format_thai_narrative(user_question, last_sql or "", last_result)

    if excel_box["file_path"] and not NarrativeService.is_complete_executive_answer(
        final_text,
        model_truncated=NarrativeService.response_was_truncated(response),
    ):
        repair_prompt = NarrativeService.build_repair_prompt(
            question=user_question,
            file_name=excel_box["file_name"] or "รายงาน Excel",
            insight_context=excel_box["insight_context"],
            draft=final_text,
        )
        try:
            repair_response = agent.gemini_client.models.generate_content(
                model=agent.model_name,
                contents=repair_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=NarrativeService.REPAIR_SYSTEM_PROMPT,
                    temperature=0.1,
                ),
            )
            repaired_text = getattr(repair_response, "text", "") or ""
            if NarrativeService.is_complete_executive_answer(
                repaired_text,
                model_truncated=NarrativeService.response_was_truncated(repair_response),
            ):
                final_text = repaired_text
            else:
                final_text = NarrativeService.format_export_fallback(
                    excel_box["file_name"] or "รายงาน Excel",
                    excel_box["insight_context"],
                )
        except Exception:
            final_text = NarrativeService.format_export_fallback(
                excel_box["file_name"] or "รายงาน Excel",
                excel_box["insight_context"],
            )

    return AgentRunResult(
        user_question=user_question,
        final_answer=final_text if final_text else "ไม่สามารถประมวลผลคำตอบได้",
        steps=steps,
        last_executed_sql=last_sql,
        last_query_result=last_result,
        success=False if quota_exceeded or workflow_incomplete or (error_details and not excel_box["file_path"]) else (True if (last_result is not None or excel_box["file_path"] or final_text) else False),
        error_message="Ran out of quota (Gemini 429 RESOURCE_EXHAUSTED)" if quota_exceeded else error_details,
        excel_file_path=excel_box["file_path"],
        excel_file_name=excel_box["file_name"],
        excel_sheets=excel_box["sheets"]
    )
