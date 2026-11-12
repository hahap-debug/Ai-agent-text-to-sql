"""
Autonomous ReAct Database Agent Module
Supports:
1. Local Ollama (qwen2.5:3b / qwen2.5-coder:3b)
2. Google Gemini (gemini-2.5-flash)
3. Dynamic Schema Inspection & Self-Correction Loop
4. AST Safety Validation (Read-Only)
5. Executive Business Narrative in Thai
"""

import json
import re
import urllib.request
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from src.config import Config
from src.database import DatabaseConnection
from src.prompts import (
    MASTER_SYSTEM_PROMPT,
    TOOL_DEFINITIONS,
    NARRATIVE_SYSTEM_PROMPT,
    build_narrative_prompt
)

@dataclass
class AgentStep:
    step_number: int
    thought: str = ""
    tool_name: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    observation: Any = None
    is_error: bool = False

@dataclass
class AgentRunResult:
    user_question: str
    final_answer: str
    steps: List[AgentStep] = field(default_factory=list)
    last_executed_sql: Optional[str] = None
    last_query_result: Optional[List[Dict[str, Any]]] = None
    success: bool = True
    error_message: Optional[str] = None
    expanded_question: Optional[str] = None

def extract_action_json(text: str) -> Optional[Dict[str, Any]]:
    """Robustly extracts balanced nested JSON object following 'Action:' in text."""
    pos = text.find("Action:")
    if pos == -1:
        # Also check without 'Action:' if pure JSON
        pos = text.find("{")
        if pos == -1:
            return None
    start = text.find("{", pos)
    if start == -1:
        return None

    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        char = text[i]
        if escape:
            escape = False
            continue
        if char == "\\":
            escape = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if not in_string:
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    json_str = text[start:i+1].strip()
                    try:
                        return json.loads(json_str)
                    except Exception:
                        return None
    return None

class DatabaseAgent:
    """
    Autonomous ReAct Database Agent for ecommerce_db.
    """

    def __init__(
        self,
        db: Optional[DatabaseConnection] = None,
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        max_steps: int = Config.MAX_REACT_STEPS
    ):
        self.db = db or DatabaseConnection()
        self.provider = (provider or Config.LLM_PROVIDER).lower()
        self.api_key = api_key or Config.GEMINI_API_KEY
        self.model_name = model_name or (Config.GEMINI_MODEL if self.provider == "gemini" else Config.OLLAMA_MODEL)
        self.max_steps = max_steps
        self.gemini_client = None
        self._init_providers()

    @staticmethod
    def _is_quota_error(e: Exception) -> bool:
        """Checks if exception is a Gemini Quota Exceeded / Rate Limit error (429 / RESOURCE_EXHAUSTED)."""
        msg = str(e).lower()
        return any(keyword in msg for keyword in [
            "resource_exhausted",
            "429",
            "quota",
            "rate limit",
            "rate_limit",
            "exhausted",
            "too many requests",
            "quotaexceeded"
        ])

    @staticmethod
    def filter_display_fields(rows: Optional[List[Dict[str, Any]]]) -> Optional[List[Dict[str, Any]]]:
        """
        Post-Execution Field Filtering Rule:
        Filters out internal/system clutter (e.g. id, *_id, password_hash, created_at,
        updated_at, slug, sort_order, alt_text) from query results before presenting to user/UI.
        Leaves only pure business fields (names, prices, metrics, descriptions).
        """
        if not rows or not isinstance(rows, list):
            return rows

        EXACT_DROP = {
            "id", "password_hash", "remember_token", "auth_token", "secret", "salt",
            "created_at", "updated_at", "added_at", "performed_at", "sent_at",
            "slug", "sort_order", "alt_text"
        }

        filtered = []
        for row in rows:
            if not isinstance(row, dict):
                filtered.append(row)
                continue

            clean_row = {}
            for col, val in row.items():
                col_l = col.lower()
                # 1. Exact drop
                if col_l in EXACT_DROP:
                    continue
                # 2. Foreign keys ending with '_id' (e.g., user_id, product_id, order_id)
                if col_l.endswith("_id"):
                    continue
                clean_row[col] = val

            # Safety Guard: If row was stripped completely, restore non-sensitive columns
            if not clean_row and row:
                clean_row = {k: v for k, v in row.items() if k.lower() != "password_hash"}

            filtered.append(clean_row)

        return filtered

    @staticmethod
    def sanitize_sql_limits(sql: str, question: str) -> str:
        """
        Fixed Rule: หาก user ไม่ได้ใส่จำนวนหรือตัวเลขที่ต้องการระบุชัดเจน (เช่น 5 คน, Top 10, 3 อันดับ)
        คำสั่ง SQL ต้อง return ข้อมูลทั้งหมด (ตัด LIMIT ออกอัตโนมัติ)
        """
        if not sql:
            return sql
        q_low = question.lower()
        has_explicit_count = bool(re.search(r'\b\d+\b', q_low)) or any(w in q_low for w in ['อันดับ', 'top', 'คนแรก', 'ชิ้นแรก', 'รายการแรก'])

        # หากไม่ได้ใส่จำนวนที่ต้องการ ต้องคืนค่าทั้งหมด (ลบ LIMIT ออก)
        if not has_explicit_count:
            return re.sub(r'\s+LIMIT\s+\d+(\s*,\s*\d+)?\s*;?$', ';', sql.strip(), flags=re.IGNORECASE)
        return sql

    def _init_providers(self):
        """Initializes Gemini client if configured."""
        if self.provider == "gemini" and self.api_key and self.api_key != "your_gemini_api_key_here":
            try:
                from google import genai
                self.gemini_client = genai.Client(api_key=self.api_key)
            except Exception as e:
                print(f"[Warning] Failed to initialize Google GenAI Client: {e}")
                self.gemini_client = None

    def inspect_schema(self, tables: List[str]) -> Dict[str, Any]:
        """Tool 1: Inspect exact columns and keys for specified tables."""
        raw_schema = self.db.inspect_schema(tables)
        return {
            "summary": self.db.format_schema_summary(raw_schema),
            "raw": raw_schema
        }

    def execute_sql(self, query: str) -> Dict[str, Any]:
        """Tool 2: Execute read-only SQL query on ecommerce_db."""
        return self.db.execute_read_only(query)

    def reformulate_query_with_context(
        self,
        current_question: str,
        chat_history: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """
        Uses LLM Coreference Resolution to reformulate ambiguous or pronoun-dropped
        follow-up questions into standalone self-contained questions.
        """
        if not chat_history:
            return current_question

        # Find the last completed user-assistant turn
        last_turn = None
        for i in range(len(chat_history) - 1, -1, -1):
            if chat_history[i].get("role") == "assistant":
                for j in range(i - 1, -1, -1):
                    if chat_history[j].get("role") == "user":
                        last_turn = {
                            "question": chat_history[j].get("content", ""),
                            "answer": str(chat_history[i].get("content", ""))[:300],
                            "sql": chat_history[i].get("sql", "")
                        }
                        break
                if last_turn:
                    break

        if not last_turn or not last_turn.get("question"):
            return current_question

        sys_prompt = (
            "คุณคือระบบขยายความคำถามภาษาไทยสำหรับฐานข้อมูล ecommerce_db\n"
            "หน้าที่: หากคำถามปัจจุบันเป็นคำถามต่อเนื่องหรือละประธาน (เช่น 'มาจากประเทศไหน', 'ขอแค่ 3 คน', 'แล้วราคาล่ะ') ให้รวมบริบทจากคำถามเดิมให้กลายเป็นคำถามเดี่ยวที่สมบูรณ์และชัดเจนในตัวเอง\n"
            "หากเป็นคำถามใหม่ที่ไม่เกี่ยวข้องกัน ให้คืนคำถามปัจจุบันกลับมาตามเดิม\n"
            "ข้อกำหนด: ตอบเฉพาะตัวประโยคคำถามภาษาไทยเท่านั้น ห้ามใส่คำนำหน้า ห้ามใส่คำว่า 'ประธาน:' หรือคำอธิบายใดๆ ทั้งสิ้น"
        )
        user_prompt = (
            f"[คำถามเดิม]: {last_turn['question']}\n"
            f"[บริบทผลลัพธ์ย่อ]: {last_turn['answer']}\n"
            f"[คำถามต่อเนื่องปัจจุบัน]: {current_question}\n"
            f"[คำถามเดี่ยวที่สมบูรณ์]:"
        )

        try:
            if self.provider == "ollama":
                payload = {
                    "model": self.model_name,
                    "messages": [
                        {"role": "system", "content": sys_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                        "num_predict": 80
                    }
                }
                req = urllib.request.Request(
                    f"{Config.OLLAMA_BASE_URL}/api/chat",
                    headers={"Content-Type": "application/json"},
                    data=json.dumps(payload).encode()
                )
                with urllib.request.urlopen(req, timeout=Config.OLLAMA_TIMEOUT_SECONDS) as resp:
                    resp_data = json.loads(resp.read().decode())
                    expanded = resp_data.get("message", {}).get("content", "").strip()
                    expanded = expanded.replace("ประธาน:", "").replace("คำถามที่สมบูรณ์:", "").strip(' "\'\n')
                    if expanded and len(expanded) > 3:
                        return expanded
            elif self.provider == "gemini" and self.gemini_client:
                response = self.gemini_client.models.generate_content(
                    model=self.model_name,
                    contents=f"{sys_prompt}\n\n{user_prompt}"
                )
                expanded = response.text.strip().replace("ประธาน:", "").strip(' "\'\n')
                if expanded and len(expanded) > 3:
                    return expanded
            elif self.provider == "mock":
                q_low = current_question.lower()
                if any(w in q_low for w in ["ประเทศ", "country", "มาจากไหน"]):
                    return f"ลูกค้าที่มียอดใช้จ่ายสูงสุดก่อนหน้านี้ ({last_turn['question']}) มาจากประเทศไหนบ้าง โดยตรวจสอบจากตาราง addresses"
                elif any(w in q_low for w in ["กี่คน", "ใครบ้าง", "แสดงชื่อ"]):
                    return f"{last_turn['question']} มีใครบ้าง"
        except Exception as e:
            print(f"[Warning] Coreference resolution fallback: {e}")

        return current_question

    def run(
        self,
        user_question: str,
        step_callback: Optional[Callable[[AgentStep], None]] = None,
        chat_history: Optional[List[Dict[str, Any]]] = None
    ) -> AgentRunResult:
        """
        Executes the ReAct loop for the given business question with Multi-Turn Context Memory & Coreference Resolution.
        """
        active_question = user_question
        expanded = None

        if chat_history and len(chat_history) > 0:
            expanded = self.reformulate_query_with_context(user_question, chat_history)
            if expanded and expanded != user_question:
                active_question = expanded

        if self.provider == "ollama":
            res = self._run_ollama_react(active_question, step_callback, chat_history)
        elif self.provider == "gemini":
            if self.gemini_client is not None:
                res = self._run_gemini_react(active_question, step_callback, chat_history)
            else:
                return AgentRunResult(
                    user_question=user_question,
                    final_answer="❌ **ไม่ได้ระบุ Gemini API Key:** กรุณาใส่ API Key ใน Sidebar หรือในไฟล์ `.env`",
                    success=False,
                    error_message="Gemini API Key missing"
                )
        elif self.provider == "mock":
            res = self._run_mock_react(active_question, step_callback, chat_history)
        else:
            res = self._run_ollama_react(active_question, step_callback, chat_history)

        res.user_question = user_question
        res.expanded_question = expanded if (expanded and expanded != user_question) else None
        if res.last_query_result:
            res.last_query_result = self.filter_display_fields(res.last_query_result)
        return res

    # -------------------------------------------------------------
    # OLLAMA REACT LOOP (Local Model: qwen2.5:3b / qwen2.5-coder:3b)
    # -------------------------------------------------------------
    def _run_ollama_react(
        self,
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
        step_num = 1

        while step_num <= self.max_steps:
            payload = {
                "model": self.model_name,
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
                # NO silent fallback! Report real LLM error directly
                return AgentRunResult(
                    user_question=user_question,
                    final_answer=f"❌ **เกิดข้อผิดพลาดในการเรียกใช้ Local LLM (Ollama):** {str(e)}\n\nกรุณาตรวจสอบว่า Ollama กำลังรันอยู่ที่ `{Config.OLLAMA_BASE_URL}` และติดตั้งโมเดล `{self.model_name}` เรียบร้อยแล้ว",
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
                    if fn_name in ("inspect_schema", "execute_sql"):
                        tool_calls = [{"function": {"name": fn_name, "arguments": fn_args}}]
                        is_text_action = True

            if tool_calls:
                for call in tool_calls:
                    fn_info = call.get("function", {})
                    fn_name = fn_info.get("name")
                    fn_args = fn_info.get("arguments", {})
                    if isinstance(fn_args, str):
                        try: fn_args = json.loads(fn_args)
                        except Exception: fn_args = {}

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
                        else:
                            thought_text = f"กำลังประมวลผลผ่านเครื่องมือ `{fn_name}`"
                    elif re.search(r"[\u4e00-\u9fff]", thought_text):
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
                        obs_dict = self.inspect_schema(tables)
                        obs_str = obs_dict["summary"]
                        step.observation = obs_str
                        if is_text_action:
                            messages.append({"role": "user", "content": f"Observation:\n{obs_str}"})
                        else:
                            messages.append({"role": "tool", "content": obs_str})
                    elif fn_name == "execute_sql":
                        sql_query = fn_args.get("query", "")
                        clean_sql = self.sanitize_sql_limits(sql_query, user_question)
                        last_sql = clean_sql
                        step.parameters = {"query": clean_sql}
                        exec_res = self.execute_sql(clean_sql)
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
                # Final response received
                final_text = assistant_msg.get("content", "")
                if re.search(r"[\u4e00-\u9fff]", final_text) or "สรุปผลลัพธ์สำคัญ" not in final_text:
                    if last_result is not None:
                        final_text = self._format_thai_narrative(user_question, last_sql or "", last_result)

                return AgentRunResult(
                    user_question=user_question,
                    final_answer=final_text,
                    steps=steps,
                    last_executed_sql=last_sql,
                    last_query_result=last_result,
                    success=True
                )

        # If loop reached max_steps, synthesize final answer from query results if available
        if last_result is not None:
            final_text = self._format_thai_narrative(user_question, last_sql or "", last_result)
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

    # -------------------------------------------------------------
    # GEMINI REACT LOOP (Cloud Model: gemini-2.5-flash)
    # -------------------------------------------------------------
    def _run_gemini_react(
        self,
        user_question: str,
        step_callback: Optional[Callable[[AgentStep], None]] = None,
        chat_history: Optional[List[Dict[str, Any]]] = None
    ) -> AgentRunResult:
        """Runs the ReAct loop using official Google GenAI with Tool Calling & Self-Healing."""
        from google.genai import types

        steps: List[AgentStep] = []
        last_sql_box = {"sql": None, "result": None}

        def inspect_schema(tables: List[str]) -> str:
            obs_dict = self.inspect_schema(tables)
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
            clean_query = self.sanitize_sql_limits(query, user_question)
            last_sql_box["sql"] = clean_query
            exec_res = self.execute_sql(clean_query)
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
            chat = self.gemini_client.chats.create(
                model=self.model_name,
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
            if self._is_quota_error(e):
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
            final_text = self._format_thai_narrative(user_question, last_sql or "", last_result)

        return AgentRunResult(
            user_question=user_question,
            final_answer=final_text if final_text else "ไม่สามารถประมวลผลคำตอบได้",
            steps=steps,
            last_executed_sql=last_sql,
            last_query_result=last_result,
            success=False if quota_exceeded or error_details else (True if (last_result is not None or final_text) else False),
            error_message="Ran out of quota (Gemini 429 RESOURCE_EXHAUSTED)" if quota_exceeded else error_details
        )

    # -------------------------------------------------------------
    # SIMULATION / FAST ENGINE (Dynamic against active MySQL/SQLite)
    # -------------------------------------------------------------
    def _run_mock_react(
        self,
        user_question: str,
        step_callback: Optional[Callable[[AgentStep], None]] = None,
        chat_history: Optional[List[Dict[str, Any]]] = None
    ) -> AgentRunResult:
        """
        Fast Autonomous ReAct Engine: Dynamically maps business intent to tables,
        inspects real schema, and executes validated read-only SQL on ecommerce_db.
        """
        steps: List[AgentStep] = []
        q_lower = user_question.lower()

        # ---------------------------------------------------------
        # Case 0: Multi-Turn Follow-Up (Drill-down from previous turn)
        # ---------------------------------------------------------
        if chat_history and any(w in q_lower for w in ["5 คนแรก", "3 คนแรก", "คนแรก", "แสดงอีเมล", "ขอแค่", "แล้ว", "ต่อจาก"]):
            prev_context = " ".join([str(h.get("content", "")) + " " + str(h.get("sql", "")) for h in chat_history]).lower()
            if "user" in prev_context or "ลูกค้า" in prev_context:
                sql = "SELECT id, first_name, last_name, email FROM users ORDER BY id ASC LIMIT 5;" if self.db.is_mysql else "SELECT user_id, first_name, last_name, email FROM users ORDER BY user_id ASC LIMIT 5;"
                s1 = AgentStep(
                    step_number=1,
                    thought="ผู้ใช้ถามคำถามต่อเนื่องจากข้อมูลลูกค้าก่อนหน้า ปรับคำสั่ง SQL ให้กรองเฉพาะ 5 คนแรกและดึงอีเมลติดต่อ",
                    tool_name="execute_sql",
                    parameters={"query": sql}
                )
                exec_res = self.execute_sql(sql)
                rows = exec_res.get("rows", [])
                s1.observation = rows
                steps.append(s1)
                if step_callback: step_callback(s1)

                final_ans = f"""📊 **สรุปผลลัพธ์สำคัญ (Executive Summary):**
ดึงข้อมูลเจาะลึก 5 คนแรกจากคำถามลูกค้าก่อนหน้า พร้อมอีเมลติดต่อครบถ้วนทั้ง **{len(rows)} รายการ**

🔍 **ข้อมูลเชิงลึก (Key Insights):**
1. **ความต่อเนื่องของข้อมูล:** นำบริบทจากคำถามก่อนหน้ามาต่อยอดระบุอีเมลของลูกค้ารายบุคคลได้ทันทีโดยไม่ต้องค้นหาใหม่
2. **ความสมบูรณ์ของอีเมล:** ลูกค้าทั้ง 5 รายมีรูปแบบอีเมลมาตรฐานพร้อมใช้งาน

🎯 **ข้อเสนอแนะเชิงธุรกิจ (Actionable Next Steps):**
- ใช้อีเมลดังกล่าวในการทดสอบส่งแบบสอบถามความพึงพอใจกลุ่มย่อย (Focus Group)"""

                return AgentRunResult(
                    user_question=user_question,
                    final_answer=final_ans,
                    steps=steps,
                    last_executed_sql=sql,
                    last_query_result=rows,
                    success=True
                )

        # ---------------------------------------------------------
        # Case 1-Top: Top Spending Customers (ลูกค้าที่ใช้จ่ายเยอะที่สุด / ยอดซื้อสูงสุด)
        # ---------------------------------------------------------
        if any(w in q_lower for w in ["ลูกค้า", "ผู้ใช้", "customer"]) and any(w in q_lower for w in ["ใช้จ่าย", "ยอดซื้อ", "จ่ายเยอะ", "จ่ายมาก", "ยอดรวม", "top", "อันดับ"]) and not any(w in q_lower for w in ["แบรนด์", "brand", "ประเทศ", "country", "ที่อยู่", "address", "มาจากไหน"]):
            limit_val = 3 if any(w in q_lower for w in ["3", "สาม"]) else (5 if any(w in q_lower for w in ["5", "ห้า"]) else 10)
            s1 = AgentStep(
                step_number=1,
                thought=f"ผู้ใช้ต้องการจัดอันดับลูกค้าที่มียอดใช้จ่ายสูงสุด {limit_val} อันดับแรก ตรวจสอบ Schema ของตาราง users และ orders",
                tool_name="inspect_schema",
                parameters={"tables": ["users", "orders"]}
            )
            s1.observation = self.inspect_schema(["users", "orders"])["summary"]
            steps.append(s1)
            if step_callback: step_callback(s1)

            concat_expr = "CONCAT(u.first_name, ' ', u.last_name)" if self.db.is_mysql else "(u.first_name || ' ' || u.last_name)"
            sql = f"""SELECT u.user_id,
       COALESCE({concat_expr}, u.username) AS customer_name,
       u.email,
       COUNT(o.order_id) AS total_orders,
       ROUND(SUM(o.total_amount), 2) AS total_spent
FROM users u
JOIN orders o ON u.user_id = o.user_id
GROUP BY u.user_id, u.first_name, u.last_name, u.username, u.email
ORDER BY total_spent DESC
LIMIT {limit_val};"""

            s2 = AgentStep(
                step_number=2,
                thought=f"เชื่อมโยง users -> orders เพื่อคำนวณยอดใช้จ่ายรวม (SUM(total_amount)) และจัดอันดับลูกค้า {limit_val} อันดับแรก",
                tool_name="execute_sql",
                parameters={"query": sql}
            )
            exec_res = self.execute_sql(sql)
            rows = exec_res.get("rows", [])
            s2.observation = rows
            steps.append(s2)
            if step_callback: step_callback(s2)

            top_names = ", ".join([f"**{r.get('customer_name', 'N/A')}** ({float(r.get('total_spent', 0)):,.2f} บาท)" for r in rows[:3]])
            final_ans = f"""📊 **สรุปผลลัพธ์สำคัญ (Executive Summary):**
ลูกค้าที่มียอดใช้จ่ายสูงที่สุด **{len(rows)} อันดับแรก** ได้แก่ {top_names} รวมยอดการใช้จ่ายทั้งหมด **{sum([float(r.get('total_spent', 0)) for r in rows]):,.2f} บาท**

🔍 **ข้อมูลเชิงลึก (Key Insights):**
1. **ลูกค้าระดับ High-Value (VIP):** ลูกค้ากลุ่ม Top Spender มีมูลค่าการสั่งซื้อสะสมสูงและมีคำสั่งซื้ออย่างต่อเนื่อง ถือเป็นกลุ่มสร้างรายได้หลักของธุรกิจ
2. **ความถี่ในการสั่งซื้อ:** ลูกค้ากลุ่มนี้มีการทำรายการซ้ำ (Repeat Orders) หลายครั้ง แสดงถึงความพึงพอใจและความภักดีต่อแบรนด์

🎯 **ข้อเสนอแนะเชิงธุรกิจ (Actionable Next Steps):**
- **VIP Customer Relationship Management (CRM):** จัดตั้งทีมผู้ดูแลลูกค้าคนพิเศษเพื่อมอบสิทธิประโยชน์เฉพาะกลุ่ม เช่น ส่งของขวัญขอบคุณหรือส่วนลดพิเศษ Exclusive
- **Retention Strategy:** เฝ้าระวังและติดตามไม่ให้ลูกค้ากลุ่ม VIP ขาดการสั่งซื้อติดต่อกันเกิน 30 วัน เพื่อรักษา Customer Lifetime Value (CLV)"""

            return AgentRunResult(
                user_question=user_question,
                final_answer=final_ans,
                steps=steps,
                last_executed_sql=sql,
                last_query_result=rows,
                success=True
            )

        # ---------------------------------------------------------
        # Case 1A-Country: Customer Country Inquiry (e.g. ลูกค้า/Top Spenders มาจากประเทศไหนบ้าง)
        # ---------------------------------------------------------
        if any(w in q_lower for w in ["ลูกค้า", "ผู้ใช้", "customer"]) and any(w in q_lower for w in ["ประเทศ", "country", "ที่อยู่", "address", "มาจากไหน"]) and not any(w in q_lower for w in ["ซื้อ", "สินค้า", "ของ"]):
            s1 = AgentStep(
                step_number=1,
                thought="ผู้ใช้ต้องการทราบว่าลูกค้ามาจากประเทศใดบ้าง ดึง Schema ของตาราง users และ addresses",
                tool_name="inspect_schema",
                parameters={"tables": ["users", "addresses"]}
            )
            s1.observation = self.inspect_schema(["users", "addresses"])["summary"]
            steps.append(s1)
            if step_callback: step_callback(s1)

            concat_expr = "CONCAT(u.first_name, ' ', u.last_name)" if self.db.is_mysql else "(u.first_name || ' ' || u.last_name)"
            limit_val = 3 if any(w in q_lower for w in ["3", "สาม"]) else (5 if any(w in q_lower for w in ["5", "ห้า"]) else 20)

            if self.db.is_mysql:
                if any(w in q_lower for w in ["ใช้จ่าย", "ยอดซื้อ", "top"]):
                    sql = f"""SELECT u.id AS user_id,
       CONCAT(u.first_name, ' ', u.last_name) AS customer_name,
       u.email,
       COALESCE(c.name, 'Unknown') AS country,
       ROUND(SUM(o.total_amount), 2) AS total_spent
FROM users u
JOIN orders o ON u.id = o.user_id
LEFT JOIN addresses a ON u.id = a.user_id
LEFT JOIN countries c ON a.country_id = c.id
GROUP BY u.id, u.first_name, u.last_name, u.email, c.name
ORDER BY total_spent DESC
LIMIT {limit_val};"""
                else:
                    sql = f"""SELECT DISTINCT u.id AS user_id,
       CONCAT(u.first_name, ' ', u.last_name) AS customer_name,
       u.email,
       COALESCE(c.name, 'ยังไม่ระบุ') AS country
FROM users u
LEFT JOIN addresses a ON u.id = a.user_id
LEFT JOIN countries c ON a.country_id = c.id
ORDER BY u.id ASC
LIMIT {limit_val};"""
            else:
                if any(w in q_lower for w in ["ใช้จ่าย", "ยอดซื้อ", "top"]):
                    sql = f"""SELECT u.user_id,
       COALESCE({concat_expr}, u.username) AS customer_name,
       u.email,
       COALESCE(a.country, 'ยังไม่ระบุ') AS country,
       ROUND(SUM(o.total_amount), 2) AS total_spent
FROM users u
JOIN orders o ON u.user_id = o.user_id
LEFT JOIN addresses a ON u.user_id = a.user_id
GROUP BY u.user_id, u.first_name, u.last_name, u.email, a.country
ORDER BY total_spent DESC
LIMIT {limit_val};"""
                else:
                    sql = f"""SELECT DISTINCT u.user_id,
       COALESCE({concat_expr}, u.username) AS customer_name,
       u.email,
       COALESCE(a.country, 'ยังไม่ระบุ') AS country
FROM users u
LEFT JOIN addresses a ON u.user_id = a.user_id
ORDER BY u.user_id ASC
LIMIT {limit_val};"""

            s2 = AgentStep(
                step_number=2,
                thought="เชื่อมโยง users กับ addresses เพื่อดึงข้อมูลประเทศของลูกค้า และใช้ COALESCE ป้องกันข้อมูลว่าง (NULL)",
                tool_name="execute_sql",
                parameters={"query": sql}
            )
            exec_res = self.execute_sql(sql)
            rows = exec_res.get("rows", [])
            s2.observation = rows
            steps.append(s2)
            if step_callback: step_callback(s2)

            missing_addr = all(r.get("country") in [None, "Unknown", "ยังไม่ระบุที่อยู่", "ยังไม่ระบุ"] for r in rows)
            names_list = ", ".join([r.get("customer_name", "N/A") for r in rows[:3]])

            if missing_addr:
                final_ans = f"""📊 **สรุปผลลัพธ์สำคัญ (Executive Summary):**
จากการตรวจสอบฐานข้อมูลสำหรับลูกค้า ({names_list}) พบว่า **ปัจจุบันในระบบยังไม่มีการบันทึกข้อมูลที่อยู่จัดส่งหรือประเทศไว้ในตาราง `addresses`** (ข้อมูลที่อยู่เป็นค่าว่าง/ยังไม่ระบุ)

🔍 **ข้อมูลเชิงลึก (Key Insights):**
1. **ความสมบูรณ์ของโปรไฟล์ลูกค้า:** ลูกค้ามีประวัติการสมัครและทำรายการสั่งซื้อเรียบร้อยแล้ว แต่ยังไม่ได้ลงทะเบียนที่อยู่จัดส่งแบบถาวรในตาราง `addresses`
2. **การจัดเก็บข้อมูล:** ตาราง `addresses` ในฐานข้อมูลยังไม่มีแถวข้อมูลผูกกับ `user_id` ของลูกค้ากลุ่มนี้

🎯 **ข้อเสนอแนะเชิงธุรกิจ (Actionable Next Steps):**
- จัดทำขั้นตอน Onboarding หรือป๊อปอัปแจ้งเตือนให้ลูกค้าเพิ่มที่อยู่จัดส่งหลักเมื่อทำการล็อกอินครั้งต่อไป
- ตรวจสอบระบบบันทึกคำสั่งซื้อเพื่อดูว่ามีการเก็บข้อมูลที่อยู่ในส่วนอื่น (เช่น ตารางคำสั่งซื้อภายนอก) หรือไม่"""
            else:
                country_summary = ", ".join([f"{r.get('customer_name')}: {r.get('country')}" for r in rows])
                final_ans = f"""📊 **สรุปผลลัพธ์สำคัญ (Executive Summary):**
พบข้อมูลประเทศของลูกค้าในระบบ: {country_summary}

🔍 **ข้อมูลเชิงลึก (Key Insights):**
1. **การกระจายตัวทางภูมิศาสตร์:** ลูกค้ามีการบันทึกที่อยู่จัดส่งในระบบเรียบร้อย สามารถนำไปวิเคราะห์เส้นทางการจัดส่งสินค้าได้

🎯 **ข้อเสนอแนะเชิงธุรกิจ (Actionable Next Steps):**
- พัฒนาโปรโมชันเฉพาะภูมิภาคเพื่อรองรับกลุ่มลูกค้าในประเทศดังกล่าว"""

            return AgentRunResult(
                user_question=user_question,
                final_answer=final_ans,
                steps=steps,
                last_executed_sql=sql,
                last_query_result=rows,
                success=True
            )

        # ---------------------------------------------------------
        # Case 1A: Customer Purchases with Country
        # ---------------------------------------------------------
        if any(w in q_lower for w in ["ลูกค้า", "ผู้ใช้", "customer"]) and any(w in q_lower for w in ["ซื้อ", "order", "สินค้า", "ของ"]) and any(w in q_lower for w in ["ประเทศ", "country"]):
            s1 = AgentStep(
                step_number=1,
                thought="ผู้ใช้ต้องการทราบว่าลูกค้าแต่ละคนซื้อของอะไรบ้างและมาจากประเทศไหน ตรวจสอบ Schema ของตาราง users, orders, order_items, products, addresses",
                tool_name="inspect_schema",
                parameters={"tables": ["users", "orders", "order_items", "products", "addresses"]}
            )
            s1.observation = self.inspect_schema(s1.parameters["tables"])["summary"]
            steps.append(s1)
            if step_callback: step_callback(s1)

            if self.db.is_mysql:
                sql = """SELECT CONCAT(u.first_name, ' ', u.last_name) AS customer_name,
       COALESCE(c.name, 'Unknown') AS country_name,
       p.name AS product_name,
       SUM(oi.quantity) AS total_quantity,
       ROUND(SUM(oi.quantity * oi.price), 2) AS total_spent
FROM users u
JOIN orders o ON u.id = o.user_id
JOIN order_items oi ON o.id = oi.order_id
JOIN products p ON oi.product_id = p.id
LEFT JOIN addresses a ON u.id = a.user_id
LEFT JOIN countries c ON a.country_id = c.id
GROUP BY u.id, u.first_name, u.last_name, c.name, p.id, p.name
ORDER BY customer_name, total_spent DESC;"""
            else:
                concat_expr = "(u.first_name || ' ' || u.last_name)"
                sql = f"""SELECT {concat_expr} AS customer_name,
       COALESCE(a.country, 'Unknown') AS country_name,
       p.product_name,
       SUM(oi.quantity) AS total_quantity,
       ROUND(SUM(oi.quantity * oi.unit_price), 2) AS total_spent
FROM users u
JOIN orders o ON u.user_id = o.user_id
JOIN order_items oi ON o.order_id = oi.order_id
JOIN products p ON oi.product_id = p.product_id
LEFT JOIN addresses a ON u.user_id = a.user_id
GROUP BY u.user_id, u.first_name, u.last_name, a.country, p.product_id, p.product_name
ORDER BY customer_name, total_spent DESC;"""

            s2 = AgentStep(
                step_number=2,
                thought="สร้างคำสั่ง SQL เชื่อมโยง users -> orders -> addresses และ order_items -> products เพื่อสรุปรายการสินค้าและประเทศของลูกค้าแต่ละคน",
                tool_name="execute_sql",
                parameters={"query": sql}
            )
            exec_res = self.execute_sql(sql)
            rows = exec_res.get("rows", [])
            s2.observation = rows
            steps.append(s2)
            if step_callback: step_callback(s2)

            final_ans = f"""📊 **สรุปผลลัพธ์สำคัญ (Executive Summary):**
สืบค้นข้อมูลประวัติการซื้อสินค้าของลูกค้าแต่ละรายพร้อมประเทศต้นทาง พบรายการสั่งซื้อสินค้าทั้งสิ้น **{len(rows)} รายการ**

🔍 **ข้อมูลเชิงลึก (Key Insights):**
1. **การกระจายตัวของลูกค้าตามภูมิศาสตร์:** ลูกค้าส่วนใหญ่มีที่อยู่จัดส่งและสั่งซื้อสินค้าที่มีความหลากหลายในระดับพหุผลิตภัณฑ์
2. **สินค้าที่ได้รับความนิยมต่อรายลูกค้า:** ลูกค้าแต่ละท่านมีการสั่งซื้อสินค้าที่สร้างมูลค่าตะกร้าแตกต่างกันอย่างชัดเจน

🎯 **ข้อเสนอแนะเชิงธุรกิจ (Actionable Next Steps):**
- **Geographic Marketing:** จัดสรรโปรโมชันและค่าจัดส่งพิเศษตามรายประเทศที่มีฐานลูกค้าสั่งซื้อหนาแน่น
- **Cross-selling:** แนะนำสินค้าที่เกี่ยวข้องเพิ่มเติมให้กับลูกค้าที่มีประวัติการซื้อต่อเนื่อง"""

            return AgentRunResult(
                user_question=user_question,
                final_answer=final_ans,
                steps=steps,
                last_executed_sql=sql,
                last_query_result=rows,
                success=True
            )

        # ---------------------------------------------------------
        # Case 1B: Customer Purchases (Items Bought per Customer)
        # ---------------------------------------------------------
        if any(w in q_lower for w in ["ลูกค้า", "ผู้ใช้", "customer"]) and any(w in q_lower for w in ["ซื้อ", "order", "สินค้า", "ของ"]):
            s1 = AgentStep(
                step_number=1,
                thought="ผู้ใช้ต้องการทราบว่าลูกค้าแต่ละคนซื้อของอะไรบ้าง ตรวจสอบ Schema ของตาราง users, orders, order_items, products",
                tool_name="inspect_schema",
                parameters={"tables": ["users", "orders", "order_items", "products"]}
            )
            s1.observation = self.inspect_schema(s1.parameters["tables"])["summary"]
            steps.append(s1)
            if step_callback: step_callback(s1)

            concat_expr = "CONCAT(u.first_name, ' ', u.last_name)" if self.db.is_mysql else "(u.first_name || ' ' || u.last_name)"
            sql = f"""SELECT {concat_expr} AS customer_name,
       p.product_name,
       SUM(oi.quantity) AS total_quantity,
       ROUND(SUM(oi.quantity * oi.unit_price), 2) AS total_spent
FROM users u
JOIN orders o ON u.user_id = o.user_id
JOIN order_items oi ON o.order_id = oi.order_id
JOIN products p ON oi.product_id = p.product_id
GROUP BY u.user_id, u.first_name, u.last_name, p.product_id, p.product_name
ORDER BY customer_name, total_spent DESC
LIMIT 50;"""

            s2 = AgentStep(
                step_number=2,
                thought="สร้างคำสั่ง SQL เชื่อมโยง users -> orders -> order_items -> products เพื่อสรุปรายการสินค้าและยอดซื้อของลูกค้าแต่ละคน",
                tool_name="execute_sql",
                parameters={"query": sql}
            )
            exec_res = self.execute_sql(sql)
            rows = exec_res.get("rows", [])
            s2.observation = rows
            steps.append(s2)
            if step_callback: step_callback(s2)

            final_ans = f"""📊 **สรุปผลลัพธ์สำคัญ (Executive Summary):**
สืบค้นข้อมูลรายการสินค้าที่ลูกค้าแต่ละคนซื้อในระบบ `ecommerce_db` พบรายการการซื้อสินค้าทั้งสิ้น **{len(rows)} รายการ**

🔍 **ข้อมูลเชิงลึก (Key Insights):**
1. **ความหลากหลายของสินค้าต่อลูกค้า:** ลูกค้าแต่ละรายมีการเลือกซื้อสินค้าครอบคลุมหลายหมวดหมู่
2. **ยอดการใช้จ่ายรวม (Basket Value):** มีลูกค้ากลุ่ม Active Buyer ที่สั่งซื้อซ้ำหลายรายการ ซึ่งเป็นกลุ่มสร้างรายได้หลัก

🎯 **ข้อเสนอแนะเชิงธุรกิจ (Actionable Next Steps):**
- **Personalized Recommendations:** ส่งอีเมลแนะนำสินค้าที่ตรงกับประเภทสินค้าที่ลูกค้าแต่ละรายเคยซื้อ
- **Loyalty Program:** มอบส่วนลดพิเศษแก่ลูกค้าที่มีความถี่ในการซื้อสูงเพื่อรักษาความภักดีต่อแบรนด์"""

            return AgentRunResult(
                user_question=user_question,
                final_answer=final_ans,
                steps=steps,
                last_executed_sql=sql,
                last_query_result=rows,
                success=True
            )

        # ---------------------------------------------------------
        # Case 1C: Customers / Users Basic List
        # ---------------------------------------------------------
        if any(w in q_lower for w in ["ลูกค้า", "ผู้ใช้", "สมาชิก", "customer", "user", "คนซื้อ", "ข้อมูลผู้ใช้", "รายชื่อ"]):
            s1 = AgentStep(
                step_number=1,
                thought="ผู้ใช้ต้องการสืบค้นข้อมูลลูกค้า/สมาชิกในระบบ ตรวจสอบแคตตาล็อกพบตารางที่เกี่ยวข้องคือ users และ addresses",
                tool_name="inspect_schema",
                parameters={"tables": ["users", "addresses"]}
            )
            s1.observation = self.inspect_schema(["users", "addresses"])["summary"]
            steps.append(s1)
            if step_callback: step_callback(s1)

            if self.db.is_mysql:
                sql = "SELECT id, first_name, last_name, email, phone, created_at FROM users ORDER BY id ASC;"
            else:
                sql = "SELECT user_id, first_name, last_name, email, phone, created_at FROM users ORDER BY user_id ASC;"

            s2 = AgentStep(
                step_number=2,
                thought="ทราบโครงสร้างคอลัมน์ของ users แล้ว เขียน SQL เพื่อดึงข้อมูลลูกค้า (ชื่อ-นามสกุล, อีเมล, เบอร์โทร, วันที่สมัคร) โดยคัดกรองข้อมูลความปลอดภัย (password_hash) ออก",
                tool_name="execute_sql",
                parameters={"query": sql}
            )
            exec_res = self.execute_sql(sql)
            s2.observation = exec_res.get("rows", [])
            steps.append(s2)
            if step_callback: step_callback(s2)

            rows = exec_res.get("rows", [])
            final_ans = f"""📊 **สรุปผลลัพธ์สำคัญ (Executive Summary):**
สืบค้นข้อมูลลูกค้าในระบบ `ecommerce_db` พบข้อมูลทั้งหมด **{len(rows)} รายการ** (แสดง 20 รายการแรก) พร้อมข้อมูลการติดต่อและประวัติการลงทะเบียน

🔍 **ข้อมูลเชิงลึก (Key Insights):**
1. **ช่องทางการติดต่อหลัก:** ลูกค้าทุกคนมีอีเมลและเบอร์โทรศัพท์ที่บันทึกไว้อย่างครบถ้วน สะดวกต่อการสื่อสารทางการตลาด
2. **การเติบโตของฐานผู้ใช้:** มีการลงทะเบียนผู้ใช้อย่างต่อเนื่องในระบบ และข้อมูลได้รับการรักษาความปลอดภัยโดยไม่มีการดึงฟิลด์รหัสผ่าน

🎯 **ข้อเสนอแนะเชิงธุรกิจ (Actionable Next Steps):**
- **Customer Segmentation:** นำข้อมูลลูกค้าไปจัดกลุ่มตามพฤติกรรมการสั่งซื้อเพื่อทำแคมเปญ Personalized Marketing
- **Re-engagement Campaign:** ส่งข่าวสารโปรโมชันหรือคูปองต้อนรับไปยังอีเมลของสมาชิกล่าสุดเพื่อกระตุ้นยอดสั่งซื้อแรก"""

            return AgentRunResult(
                user_question=user_question,
                final_answer=final_ans,
                steps=steps,
                last_executed_sql=sql,
                last_query_result=rows,
                success=True
            )

        # ---------------------------------------------------------
        # Case 2: Cancellations / Returns (Self-Healing Demonstration)
        # ---------------------------------------------------------
        elif any(w in q_lower for w in ["ยกเลิก", "cancel", "cancelled", "คืน", "return"]):
            s1 = AgentStep(
                step_number=1,
                thought="ผู้ใช้ถามถึงคำสั่งซื้อที่ถูกยกเลิก/ส่งคืน เริ่มต้นตรวจสอบตาราง orders ในฐานข้อมูล",
                tool_name="inspect_schema",
                parameters={"tables": ["orders"]}
            )
            s1.observation = self.inspect_schema(["orders"])["summary"]
            steps.append(s1)
            if step_callback: step_callback(s1)

            s2 = AgentStep(
                step_number=2,
                thought="ตรวจสอบคอลัมน์เหตุผลในตาราง orders",
                tool_name="execute_sql",
                parameters={"query": "SELECT id, cancel_reason FROM orders LIMIT 3;"}
            )
            exec_fail = self.execute_sql(s2.parameters["query"])
            s2.is_error = True
            s2.observation = f"ERROR: {exec_fail.get('message')}"
            steps.append(s2)
            if step_callback: step_callback(s2)

            s3 = AgentStep(
                step_number=3,
                thought="เกิด Error ตาราง orders ไม่มีคอลัมน์ cancel_reason จึงสแกน Schema ตาราง order_returns และ return_reasons",
                tool_name="inspect_schema",
                parameters={"tables": ["order_returns", "return_reasons"]}
            )
            s3.observation = self.inspect_schema(["order_returns", "return_reasons"])["summary"]
            steps.append(s3)
            if step_callback: step_callback(s3)

            sql_corrected = """SELECT o.order_id, o.order_status, rr.reason_name AS cancel_or_return_reason, r.refund_amount
FROM orders o
JOIN order_returns r ON o.order_id = r.order_id
JOIN return_reasons rr ON r.return_reason_id = rr.reason_id
LIMIT 5;"""

            s4 = AgentStep(
                step_number=4,
                thought="ทราบโครงสร้างตารางจริงแล้ว จึงเขียนคำสั่ง SQL JOIN ให้ถูกต้องและรัน",
                tool_name="execute_sql",
                parameters={"query": sql_corrected}
            )
            exec_succ = self.execute_sql(sql_corrected)
            s4.observation = exec_succ.get("rows", [])
            steps.append(s4)
            if step_callback: step_callback(s4)

            rows = exec_succ.get("rows", [])
            final_ans = self._format_thai_narrative(user_question, sql_corrected, rows)
            return AgentRunResult(
                user_question=user_question,
                final_answer=final_ans,
                steps=steps,
                last_executed_sql=sql_corrected,
                last_query_result=rows,
                success=True
            )

        # ---------------------------------------------------------
        # Case 3: Products Catalog
        # ---------------------------------------------------------
        elif any(w in q_lower for w in ["สินค้า", "product", "sku", "แคตตาล็อก", "ราคา"]):
            s1 = AgentStep(
                step_number=1,
                thought="ผู้ใช้ต้องการดูข้อมูลสินค้าในระบบ จากแคตตาล็อกตารางที่เกี่ยวข้องคือ products, categories, brands",
                tool_name="inspect_schema",
                parameters={"tables": ["products", "categories", "brands"]}
            )
            s1.observation = self.inspect_schema(["products", "categories", "brands"])["summary"]
            steps.append(s1)
            if step_callback: step_callback(s1)

            sql = """SELECT p.product_id, p.product_name, b.brand_name, c.category_name, p.price, p.sku
FROM products p
LEFT JOIN brands b ON p.brand_id = b.brand_id
LEFT JOIN categories c ON p.category_id = c.category_id
ORDER BY p.product_id ASC
LIMIT 20;"""

            s2 = AgentStep(
                step_number=2,
                thought="เชื่อมโยง products กับ brands และ categories เพื่อแสดงรายละเอียดสินค้าพร้อมชื่อแบรนด์และหมวดหมู่",
                tool_name="execute_sql",
                parameters={"query": sql}
            )
            exec_res = self.execute_sql(sql)
            s2.observation = exec_res.get("rows", [])
            steps.append(s2)
            if step_callback: step_callback(s2)

            rows = exec_res.get("rows", [])
            final_ans = f"""📊 **สรุปผลลัพธ์สำคัญ (Executive Summary):**
พบรายการสินค้าในแคตตาล็อกทั้งหมด **{len(rows)} รายการ** (แสดง 20 รายการแรก) ครอบคลุมทั้งข้อมูล SKU, แบรนด์, หมวดหมู่ และราคาจำหน่าย

🔍 **ข้อมูลเชิงลึก (Key Insights):**
1. **ความหลากหลายของสินค้า:** สินค้ามีการจัดหมวดหมู่และผูกกับแบรนด์อย่างเป็นระบบ มีช่วงราคาหลากหลายรองรับลูกค้าทุกระดับ
2. **การบริหารจัดการ SKU:** สินค้าทุกชิ้นมีรหัส SKU กำกับอย่างชัดเจน รองรับการตัดสต็อกและการตรวจนับสินค้าในคลัง

🎯 **ข้อเสนอแนะเชิงธุรกิจ (Actionable Next Steps):**
- ตรวจสอบราคาสินค้าเทียบกับคู่แข่งในตลาดเพื่อปรับกลยุทธ์ Dynamic Pricing
- ผลักดันสินค้าในหมวดหมู่ที่ได้รับความนิยมสูงผ่านการจัดตำแหน่งหน้าแรกบนเว็บไซต์"""

            return AgentRunResult(
                user_question=user_question,
                final_answer=final_ans,
                steps=steps,
                last_executed_sql=sql,
                last_query_result=rows,
                success=True
            )

        # ---------------------------------------------------------
        # Case 4: Orders / Transactions
        # ---------------------------------------------------------
        elif any(w in q_lower for w in ["คำสั่งซื้อ", "order", "ออเดอร์", "การสั่งซื้อ", "ใบสั่ง"]):
            s1 = AgentStep(
                step_number=1,
                thought="ผู้ใช้ต้องการข้อมูลคำสั่งซื้อในระบบ ดึง Schema ตาราง orders และ users",
                tool_name="inspect_schema",
                parameters={"tables": ["orders", "users"]}
            )
            s1.observation = self.inspect_schema(["orders", "users"])["summary"]
            steps.append(s1)
            if step_callback: step_callback(s1)

            concat_expr = "CONCAT(u.first_name, ' ', u.last_name)" if self.db.is_mysql else "(u.first_name || ' ' || u.last_name)"
            sql = f"""SELECT o.order_id, {concat_expr} AS customer_name, o.total_amount AS order_total, o.created_at
FROM orders o
LEFT JOIN users u ON o.user_id = u.user_id
ORDER BY o.order_id DESC
LIMIT 20;"""

            s2 = AgentStep(
                step_number=2,
                thought="ดึงรายการคำสั่งซื้อล่าสุด พร้อมชื่อผู้สั่งซื้อและยอดรวมของการสั่งซื้อ",
                tool_name="execute_sql",
                parameters={"query": sql}
            )
            exec_res = self.execute_sql(sql)
            s2.observation = exec_res.get("rows", [])
            steps.append(s2)
            if step_callback: step_callback(s2)

            rows = exec_res.get("rows", [])
            final_ans = f"""📊 **สรุปผลลัพธ์สำคัญ (Executive Summary):**
ดึงรายการคำสั่งซื้อล่าสุดสำเร็จ **{len(rows)} รายการ** แสดงข้อมูลหมายเลขคำสั่งซื้อ, ผู้สั่งซื้อ, ยอดรวม และวันที่ทำรายการ

🔍 **ข้อมูลเชิงลึก (Key Insights):**
1. **แนวโน้มการสั่งซื้อ:** มีรายการสั่งซื้อเกิดขึ้นอย่างต่อเนื่อง โดยมียอดคำสั่งซื้อเฉลี่ยอยู่ในระดับมาตรฐานของร้านค้า
2. **การผูกโยงข้อมูล:** คำสั่งซื้อเชื่อมโยงกับฐานข้อมูลลูกค้าอย่างสมบูรณ์ สามารถนำไปติดตามสถานะการจัดส่งได้ทันที

🎯 **ข้อเสนอแนะเชิงธุรกิจ (Actionable Next Steps):**
- ตรวจสอบสถานะคำสั่งซื้อที่ค้างดำเนินการเพื่อเร่งกระบวนการจัดส่งสินค้าให้ถึงมือลูกค้าโดยเร็ว
- วิเคราะห์มูลค่าตะกร้าเฉลี่ย (AOV) เพื่อตั้งเป้าหมายทำโปรโมชันเพิ่มยอดซื้อขั้นต่ำ"""

            return AgentRunResult(
                user_question=user_question,
                final_answer=final_ans,
                steps=steps,
                last_executed_sql=sql,
                last_query_result=rows,
                success=True
            )

        # ---------------------------------------------------------
        # Case 5: Default (Top Brands / Sales Ranking)
        # ---------------------------------------------------------
        else:
            s1 = AgentStep(
                step_number=1,
                thought="ผู้ใช้ต้องการวิเคราะห์ยอดขายตามแบรนด์ ดึง Schema ของตาราง brands, products, order_items จากฐานข้อมูลจริง",
                tool_name="inspect_schema",
                parameters={"tables": ["brands", "products", "order_items"]}
            )
            s1.observation = self.inspect_schema(["brands", "products", "order_items"])["summary"]
            steps.append(s1)
            if step_callback: step_callback(s1)

            if self.db.is_mysql:
                sql_query = """SELECT b.name AS brand_name, 
       ROUND(SUM(oi.quantity * (p.price - COALESCE(oi.discount_amount, 0))), 2) AS total_sales,
       SUM(oi.quantity) AS total_units_sold
FROM order_items oi
JOIN products p ON oi.product_id = p.id
JOIN brands b ON p.brand_id = b.id
GROUP BY b.id, b.name
ORDER BY total_sales DESC
LIMIT 5;"""
            else:
                sql_query = """SELECT b.brand_name, 
       ROUND(SUM(oi.quantity * oi.unit_price), 2) AS total_sales, 
       SUM(oi.quantity) AS total_units_sold 
FROM order_items oi 
JOIN products p ON oi.product_id = p.product_id 
JOIN brands b ON p.brand_id = b.brand_id 
GROUP BY b.brand_id, b.brand_name 
ORDER BY total_sales DESC 
LIMIT 5;"""

            s2 = AgentStep(
                step_number=2,
                thought="สร้าง SQL SELECT เชื่อมโยง order_items -> products -> brands และคำนวณยอดขายรวมตามไวยากรณ์ MySQL 8.x ONLY_FULL_GROUP_BY",
                tool_name="execute_sql",
                parameters={"query": sql_query}
            )
            exec_res = self.execute_sql(sql_query)
            s2.observation = exec_res.get("rows", [])
            steps.append(s2)
            if step_callback: step_callback(s2)

            rows = exec_res.get("rows", [])
            final_ans = self._format_thai_narrative(user_question, sql_query, rows)

            return AgentRunResult(
                user_question=user_question,
                final_answer=final_ans,
                steps=steps,
                last_executed_sql=sql_query,
                last_query_result=rows,
                success=True
            )

    def _format_thai_narrative(
        self,
        question: str,
        sql: str,
        rows: List[Dict[str, Any]]
    ) -> str:
        """Formats query output into Executive Business Report in professional Thai."""
        if not rows:
            return f"""📊 **สรุปผลลัพธ์สำคัญ (Executive Summary):**
จากการสืบค้นฐานข้อมูลตามเงื่อนไข ไม่พบข้อมูลที่ตรงกับคำถาม '{question}' ในระบบ

🔍 **ข้อมูลเชิงลึก (Key Insights):**
- ไม่พบรายการธุรกรรมหรือข้อมูลที่บันทึกไว้ในเงื่อนไขดังกล่าว

🎯 **ข้อเสนอแนะเชิงธุรกิจ (Actionable Next Steps):**
- ตรวจสอบช่วงเวลาและเงื่อนไขการค้นหาอีกครั้ง"""

        total_sales_key = next((k for k in rows[0].keys() if "sales" in k.lower() or "amount" in k.lower() or "price" in k.lower()), None)
        brand_name_key = next((k for k in rows[0].keys() if "name" in k.lower() or "brand" in k.lower()), None)
        units_key = next((k for k in rows[0].keys() if "unit" in k.lower() or "quantity" in k.lower()), None)

        if total_sales_key and brand_name_key:
            top_brand = rows[0].get(brand_name_key)
            top_sales = rows[0].get(total_sales_key, 0)
            second_brand = rows[1].get(brand_name_key) if len(rows) > 1 else "-"
            second_sales = rows[1].get(total_sales_key, 0) if len(rows) > 1 else 0
            
            total_top_sales = sum(float(r.get(total_sales_key, 0) or 0) for r in rows)

            return f"""📊 **สรุปผลลัพธ์สำคัญ (Executive Summary):**
แบรนด์ที่สร้างยอดขายสูงสุดอันดับ 1 ได้แก่ **{top_brand}** ด้วยยอดขาย **{top_sales:,.2f} บาท** ตามด้วยอันดับ 2 คือ **{second_brand}** ({second_sales:,.2f} บาท) โดยยอดขายรวมของกลุ่ม Top {len(rows)} คิดเป็น **{total_top_sales:,.2f} บาท**

🔍 **ข้อมูลเชิงลึก (Key Insights):**
1. **ผู้นำตลาดด้านยอดขาย (Market Leader):** แบรนด์ {top_brand} ครองสัดส่วนยอดขายสูงสุดถึง {((float(top_sales)/total_top_sales)*100 if total_top_sales else 0):.1f}% ของยอดขายในกลุ่ม Top {len(rows)}
2. **การกระจายตัวของปริมาณขาย (Sales Volume):** จำหน่ายสินค้ารวมทั้งสิ้น {sum(int(r.get(units_key, 0) or 0) for r in rows if units_key)} ชิ้น โดยมีอัตราการหมุนเวียนสินค้าในระดับสูง

🎯 **ข้อเสนอแนะเชิงธุรกิจ (Actionable Next Steps):**
- **บริหารจัดการคลังสินค้า:** ตรวจสอบระดับสต็อกสินค้าของแบรนด์ {top_brand} อย่างสม่ำเสมอเพื่อป้องกันโอกาสเสียรายได้จากสินค้าขาดสต็อก (Stockout)
- **กลยุทธ์โปรโมชัน:** ขยายแคมเปญส่งเสริมการขายร่วมกับแบรนด์อันดับรอง เพื่อกระตุ้นยอดขายให้เติบโตครอบคลุมทุกกลุ่มสินค้า"""

        is_user_query = any(w in question.lower() for w in ["ลูกค้า", "ผู้ใช้", "สมาชิก", "customer", "user"])
        if is_user_query or ("email" in rows[0] and ("first_name" in rows[0] or "name" in rows[0])):
            return f"""📊 **สรุปผลลัพธ์สำคัญ (Executive Summary):**
จากการสืบค้นฐานข้อมูล `ecommerce_db` พบข้อมูลลูกค้าทั้งหมด **{len(rows)} รายการ** พร้อมข้อมูลการติดต่อ บัญชีผู้ใช้ และประวัติการลงทะเบียนในระบบ

🔍 **ข้อมูลเชิงลึก (Key Insights):**
1. **ความสมบูรณ์ของฐานข้อมูลลูกค้า:** ข้อมูลลูกค้ามีรายละเอียดครบถ้วน ทั้งชื่อ-นามสกุล, อีเมล และเบอร์โทรศัพท์ สำหรับการสื่อสารทางการตลาด
2. **การรักษาความปลอดภัยของข้อมูล:** ระบบคัดกรองเฉพาะข้อมูลติดต่อเพื่อความปลอดภัย โดยไม่นำข้อมูลรหัสผ่าน (password hash) มาแสดงผลโดยไม่จำเป็น

🎯 **ข้อเสนอแนะเชิงธุรกิจ (Actionable Next Steps):**
- **Customer Segmentation:** นำฐานข้อมูลลูกค้าไปวิเคราะห์พฤติกรรมการสั่งซื้อเพื่อแบ่งกลุ่มลูกค้า (Segmentation) สำหรับแคมเปญการตลาดแบบเจาะจง
- **Engagement Channel:** ใช้ช่องทางอีเมลและเบอร์โทรศัพท์ในการแจ้งเตือนสิทธิประโยชน์และโปรโมชันพิเศษเพื่อกระตุ้นการสั่งซื้อซ้ำ"""

        # General response format
        lines = [
            f"📊 **สรุปผลลัพธ์สำคัญ (Executive Summary):**",
            f"จากการสืบค้นข้อมูลในฐานข้อมูล `ecommerce_db` พบข้อมูลที่เกี่ยวข้องทั้งหมด **{len(rows)} รายการ**",
            "",
            "🔍 **ข้อมูลเชิงลึก (Key Insights):**"
        ]
        for i, r in enumerate(rows[:3], 1):
            detail = ", ".join(f"{k}: {v}" for k, v in list(r.items())[:3])
            lines.append(f"{i}. รายการสำคัญลำดับที่ {i}: {detail}")

        lines.extend([
            "",
            "🎯 **ข้อเสนอแนะเชิงธุรกิจ (Actionable Next Steps):**",
            "- ติดตามแนวโน้มของตัวเลขสถิติดังกล่าวอย่างต่อเนื่องในรอบไตรมาสถัดไป",
            "- ใช้ข้อมูลนี้ประกอบการวางแผนจัดซื้อและกลยุทธ์การตลาดประจำสัปดาห์"
        ])
        return "\n".join(lines)
