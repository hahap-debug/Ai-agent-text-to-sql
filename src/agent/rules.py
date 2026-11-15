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
