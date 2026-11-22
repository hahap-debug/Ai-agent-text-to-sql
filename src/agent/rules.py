"""
Agent Rules, Sanitization & Privacy Guards
Provides field filtering, limit sanitization, quota error checks, and Action JSON extraction.
"""

import json
import re
from typing import List, Dict, Any, Optional

def extract_action_json(text: str) -> Optional[Dict[str, Any]]:
    """Robustly extracts balanced nested JSON object following 'Action:' in text."""
    pos = text.find("Action:")
    if pos == -1:
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

def is_quota_error(e: Exception) -> bool:
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

def filter_display_fields(
    rows: Optional[List[Dict[str, Any]]],
    preserve_fields: Optional[List[str]] = None,
) -> Optional[List[Dict[str, Any]]]:
    """Backward-compatible delegate to the shared field-filtering policy."""
    from src.services.sql_guard_service import SQLGuardService

    return SQLGuardService.filter_display_fields(rows, preserve_fields=preserve_fields)

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
