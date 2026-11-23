"""
SQL Guard Service: AST validation, privacy field filtering,
limit sanitization, quota checks, and Action JSON parsing.
"""

import json
import re
from typing import List, Dict, Any, Optional, Iterable
from src.validator import validate_ast_safety, SQLSecurityError, SQLSyntaxError


class SQLGuardService:
    """Service providing SQL security validation and result privacy sanitization."""

    @staticmethod
    def validate_ast(query: str):
        """Enforces strictly read-only SELECT statements via sqlglot AST parsing."""
        return validate_ast_safety(query)

    @staticmethod
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

    @staticmethod
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

    @staticmethod
    def filter_display_fields(
        rows: Optional[List[Dict[str, Any]]],
        preserve_fields: Optional[Iterable[str]] = None,
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Hide internal fields by default while allowing callers to retain selected output fields.
        Sensitive credentials are always removed, even when explicitly preserved.
        """
        if not rows or not isinstance(rows, list):
            return rows

        sensitive_exact = {
            "password", "password_hash", "remember_token", "auth_token", "token",
            "secret", "secret_key", "salt", "api_key", "access_key",
        }
        hidden_by_default = {
            "id", "created_at", "updated_at", "added_at", "performed_at", "sent_at",
            "slug", "sort_order", "alt_text",
        }
        if isinstance(preserve_fields, str):
            preserve_fields = [preserve_fields]
        preserved = {str(field).casefold() for field in (preserve_fields or [])}

        def is_sensitive(column: str) -> bool:
            name = column.casefold()
            return (
                name in sensitive_exact
                or name.startswith(("password_", "secret_", "token_"))
                or name.endswith(("_password", "_secret", "_token", "_api_key", "_access_key"))
            )

        filtered = []
        for row in rows:
            if not isinstance(row, dict):
                filtered.append(row)
                continue

            clean_row = {}
            for col, val in row.items():
                col_l = str(col).casefold()
                if is_sensitive(col_l):
                    continue
                if col_l in preserved:
                    clean_row[col] = val
                    continue
                if col_l in hidden_by_default or col_l.endswith("_id"):
                    continue
                clean_row[col] = val

            # Preserve the legacy ID-only behavior without restoring protected fields.
            if not clean_row and row:
                clean_row = {k: v for k, v in row.items() if not is_sensitive(str(k))}

            filtered.append(clean_row)

        return filtered

    @staticmethod
    def sanitize_sql_limits(sql: str, question: str) -> str:
        """
        Remove model-added result limits unless the user explicitly requested a count.
        Numbers used for dates or periods do not imply a requested result count.
        """
        if not sql:
            return sql
        q_low = (question or "").casefold()
        number = r"(?:\d+|หนึ่ง|สอง|สาม|สี่|ห้า|หก|เจ็ด|แปด|เก้า|สิบ)"
        count_unit = r"(?:อันดับ|คน|รายการ|ชิ้น|สินค้า|แบรนด์|แถว|items?|rows?|customers?|products?|brands?|orders?)"
        explicit_count_patterns = (
            rf"\b(?:top|limit|max|maximum)\s*{number}\b",
            rf"\bfirst\s+{number}\s+{count_unit}\b",
            rf"{number}\s*{count_unit}",
            rf"{count_unit}\s*(?:แรก|สูงสุด)?\s*{number}",
            rf"(?:แสดง|ขอ|ดู|เอา)\s*(?:ข้อมูล|รายการ)?\s*{number}(?:\s*{count_unit})?\s*(?:แรก|สูงสุด)?\s*$",
        )
        has_explicit_count = any(re.search(pattern, q_low) for pattern in explicit_count_patterns)

        if not has_explicit_count:
            return re.sub(
                r"\s+LIMIT\s+(?:\d+\s*,\s*)?\d+(?:\s+OFFSET\s+\d+)?\s*;?\s*$",
                ";",
                sql.strip(),
                flags=re.IGNORECASE,
            )
        return sql


# Module-level convenience aliases
validate_ast = SQLGuardService.validate_ast
extract_action_json = SQLGuardService.extract_action_json
is_quota_error = SQLGuardService.is_quota_error
filter_display_fields = SQLGuardService.filter_display_fields
sanitize_sql_limits = SQLGuardService.sanitize_sql_limits
