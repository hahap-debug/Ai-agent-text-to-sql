"""
Ollama ReAct Execution Engine
Executes local Ollama (qwen2.5-coder:7b) with ReAct loop, Action JSON parsing, and self-correction.
"""

import json
import re
import urllib.request
from typing import List, Dict, Any, Optional, Callable
from src.config import Config
from src.prompts import OLLAMA_SYSTEM_PROMPT, TOOL_DEFINITIONS
from src.agent.models import AgentStep, AgentRunResult
from src.agent.rules import extract_action_json, sanitize_sql_limits
from src.agent.narrative import format_thai_narrative

def run_ollama_react(
    agent: Any,
    user_question: str,
    step_callback: Optional[Callable[[AgentStep], None]] = None,
    chat_history: Optional[List[Dict[str, Any]]] = None
) -> AgentRunResult:
    """Executes ReAct loop with local Ollama instance with Multi-Turn Context Memory."""
    messages = [
        {"role": "system", "content": OLLAMA_SYSTEM_PROMPT}
    ]

    # Multi-Turn Context Injection: Include compact recent conversation history
    if chat_history:
        history_pairs = []
        curr_q = None
        for item in chat_history:
            if item.get("role") == "user":
                curr_q = item.get("content")
            elif item.get("role") == "assistant" and curr_q:
                history_pairs.append({
                    "question": curr_q,
                    "answer": item.get("content", ""),
                    "sql": item.get("sql", "")
                })
                curr_q = None

        # Retain up to the 2 most recent completed turns to keep context fast and focused
        for pair in history_pairs[-2:]:
            ans_preview = pair["answer"]
            if "🔍" in ans_preview:
                ans_preview = ans_preview.split("🔍")[0].strip()
            ans_preview = ans_preview[:250]

            messages.append({"role": "user", "content": pair["question"]})
            asst_reply = f"{ans_preview}\n[Executed SQL: {pair['sql']}]" if pair.get("sql") else ans_preview
            messages.append({"role": "assistant", "content": asst_reply})

    messages.append({
        "role": "user",
        "content": f"{user_question}\n(หากคำถามนี้เป็นการถามเจาะลึกหรือต่อเนื่องจากคำถามก่อนหน้า สามารถนำ SQL และตารางเดิมมาต่อยอดได้ทันที กรุณาคิดขั้นตอน Thought และตอบผลลัพธ์เป็นภาษาไทยเท่านั้น ห้ามมีภาษาจีน)"
    })

    steps: List[AgentStep] = []
    last_sql = None
    last_result = None
    excel_file_path = None
    excel_file_name = None
    excel_sheets = None
    seen_actions = set()
    step_num = 1

    while step_num <= agent.max_steps:
        payload = {
            "model": agent.model_name,
            "messages": messages,
            "tools": TOOL_DEFINITIONS,
            "stream": False,
            "options": {
                "temperature": Config.OLLAMA_TEMPERATURE,
                "stop": ["Observation:", "\nObservation:"]
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
                final_answer=f"❌ **เกิดข้อผิดพลาดในการเรียกใช้ Local LLM (Ollama):** {str(e)}\n\nกรุณาตรวจสอบว่า Ollama กำลังรันอยู่ที่ `{Config.OLLAMA_BASE_URL}` และติดตั้งโมเดล `{agent.model_name}` เรียบร้อยแล้ว",
                steps=steps,
                success=False,
                error_message=str(e)
            )

        assistant_msg = resp_data.get("message", {})
        content = assistant_msg.get("content", "")
        # Ensure hallucinated observations from local model are trimmed
        if "Observation:" in content:
            content = content.split("Observation:")[0].strip()
            assistant_msg["content"] = content

        messages.append(assistant_msg)
        tool_calls = assistant_msg.get("tool_calls", [])
        is_text_action = False

        # If model formatted action in text rather than native tool_call
        if not tool_calls:
            action_data = extract_action_json(content)
            if action_data:
                fn_name = action_data.get("tool") or action_data.get("name")
                fn_args = action_data.get("parameters") or action_data.get("arguments") or {}
                if fn_name in ("inspect_schema", "execute_sql", "create_multi_sheet_excel"):
                    tool_calls = [{"function": {"name": fn_name, "arguments": fn_args}}]
                    is_text_action = True

        if tool_calls:
            if last_result is not None or excel_file_path is not None:
                break

            for call in tool_calls:
                fn_info = call.get("function", {})
                fn_name = fn_info.get("name")
                fn_args = fn_info.get("arguments", {})
                if isinstance(fn_args, str):
                    try: fn_args = json.loads(fn_args)
                    except Exception: fn_args = {}

                action_sig = f"{fn_name}:{json.dumps(fn_args, sort_keys=True)}"
                if action_sig in seen_actions:
                    break
                seen_actions.add(action_sig)

                thought_text = content
                if is_text_action and "Action:" in thought_text:
                    thought_text = thought_text.split("Action:")[0].replace("Thought:", "").strip()

                # Auto-fallback/sanitize for Thought in Thai
                if not thought_text:
                    if fn_name == "inspect_schema":
                        tables_str = ", ".join(fn_args.get("tables", []))
                        thought_text = f"ตรวจสอบโครงสร้างและคอลัมน์ของตาราง `{tables_str}` เพื่อเตรียมสร้างคำสั่ง SQL"
                    elif fn_name == "execute_sql":
                        thought_text = "สร้างและประมวลผลคำสั่ง SQL SELECT เพื่อดึงข้อมูลที่ตรงตามคำถาม"
                    elif fn_name == "create_multi_sheet_excel":
                        thought_text = "สร้างรายงาน Excel แบบหลายแท็บพร้อมฟอร์แมตตัวเลข บันทึกลง Desktop"
                    else:
                        thought_text = f"กำลังประมวลผลผ่านเครื่องมือ `{fn_name}`"
                elif re.search(r"[\u4e00-\u9fff]", thought_text):
                    if fn_name == "inspect_schema":
                        tables_str = ", ".join(fn_args.get("tables", []))
                        thought_text = f"ตรวจสอบโครงสร้างและคอลัมน์ของตาราง `{tables_str}` เพื่อเตรียมสร้างคำสั่ง SQL"
                    elif fn_name == "execute_sql":
                        thought_text = "สร้างและประมวลผลคำสั่ง SQL SELECT เพื่อดึงข้อมูลที่ตรงตามคำถาม"
                    elif fn_name == "create_multi_sheet_excel":
                        thought_text = "สร้างรายงาน Excel แบบหลายแท็บพร้อมฟอร์แมตตัวเลข บันทึกลง Desktop"
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
                    clean_sql = sanitize_sql_limits(sql_query, user_question)
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
                elif fn_name == "create_multi_sheet_excel":
                    fname = fn_args.get("file_name", "Report.xlsx")
                    sheets_param = fn_args.get("sheets", [])
                    excel_res = agent.create_multi_sheet_excel(fname, sheets_param)
                    if excel_res.get("status") == "success":
                        excel_file_path = excel_res.get("file_path")
                        excel_file_name = excel_res.get("file_name")
                        excel_sheets = excel_res.get("sheets")
                        step.observation = excel_res
                    else:
                        step.is_error = True
                        step.observation = f"ERROR: {excel_res.get('error', 'Excel creation failed')}"
                    obs_str = json.dumps(excel_res, ensure_ascii=False)
                    if is_text_action:
                        messages.append({"role": "user", "content": f"Observation:\n{obs_str}"})
                    else:
                        messages.append({"role": "tool", "content": obs_str})

                steps.append(step)
                if step_callback:
                    step_callback(step)
                step_num += 1
        else:
            # Final response received
            final_text = assistant_msg.get("content", "")
            if re.search(r"[\u4e00-\u9fff]", final_text) or "สรุปผลลัพธ์สำคัญ" not in final_text:
                if last_result is not None:
                    final_text = format_thai_narrative(user_question, last_sql or "", last_result)

            return AgentRunResult(
                user_question=user_question,
                final_answer=final_text,
                steps=steps,
                last_executed_sql=last_sql,
                last_query_result=last_result,
                success=True,
                excel_file_path=excel_file_path,
                excel_file_name=excel_file_name,
                excel_sheets=excel_sheets
            )

    # If loop reached max_steps, synthesize final answer from query results if available
    if last_result is not None or excel_file_path is not None:
        if last_result is not None:
            final_text = format_thai_narrative(user_question, last_sql or "", last_result)
        else:
            final_text = "สร้างรายงาน Excel เรียบร้อยแล้ว"
        return AgentRunResult(
            user_question=user_question,
            final_answer=final_text,
            steps=steps,
            last_executed_sql=last_sql,
            last_query_result=last_result,
            success=True,
            excel_file_path=excel_file_path,
            excel_file_name=excel_file_name,
            excel_sheets=excel_sheets
        )

    return AgentRunResult(
        user_question=user_question,
        final_answer=assistant_msg.get("content", "ดำเนินการถึงขีดจำกัดขั้นตอนการคิดสูงสุด (Max reasoning steps reached)"),
        steps=steps,
        last_executed_sql=last_sql,
        last_query_result=last_result,
        success=False,
        excel_file_path=excel_file_path,
        excel_file_name=excel_file_name,
        excel_sheets=excel_sheets
    )
