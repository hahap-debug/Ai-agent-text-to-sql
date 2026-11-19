"""
Coreference Resolution & Multi-Turn Context Expander
Reformulates ambiguous or pronoun-dropped follow-up questions into standalone self-contained queries.
"""

import json
import urllib.request
from typing import List, Dict, Any, Optional
from src.config import Config

def reformulate_query_with_context(
    current_question: str,
    chat_history: Optional[List[Dict[str, Any]]] = None,
    provider: str = "ollama",
    model_name: str = "qwen2.5-coder:7b",
    gemini_client: Optional[Any] = None
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
        if provider == "ollama":
            payload = {
                "model": model_name,
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
        elif provider == "gemini" and gemini_client:
            try:
                response = gemini_client.models.generate_content(
                    model=model_name,
                    contents=f"{sys_prompt}\n\n{user_prompt}"
                )
                expanded = response.text.strip().replace("ประธาน:", "").strip(' "\'\n')
                if expanded and len(expanded) > 3:
                    return expanded
            except Exception as ge:
                print(f"[Coreference Fallback] Gemini error ({ge}), falling back to Ollama...")
                return reformulate_query_with_context(
                    current_question, chat_history, provider="ollama", model_name=Config.OLLAMA_MODEL
                )
        elif provider == "mock":
            q_low = current_question.lower()
            if any(w in q_low for w in ["ประเทศ", "country", "มาจากไหน"]):
                return f"ลูกค้าที่มียอดใช้จ่ายสูงสุดก่อนหน้านี้ ({last_turn['question']}) มาจากประเทศไหนบ้าง โดยตรวจสอบจากตาราง addresses"
            elif any(w in q_low for w in ["กี่คน", "ใครบ้าง", "แสดงชื่อ"]):
                return f"{last_turn['question']} มีใครบ้าง"
    except Exception as e:
        print(f"[Warning] Coreference resolution fallback: {e}")

    return current_question
