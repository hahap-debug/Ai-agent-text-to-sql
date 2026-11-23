"""Builds a compact, evidence-based context from rows already exported to Excel."""

from collections import Counter
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlglot import exp, parse_one


class InsightContextService:
    """Create bounded summaries without running a second query or returning raw detail rows."""

    MAX_AGGREGATE_ROWS = 25
    MAX_PROFILE_COLUMNS = 15
    MAX_TOP_VALUES = 5
    MAX_LABEL_LENGTH = 80
    SENSITIVE_COLUMN_PARTS = (
        "email", "phone", "mobile", "password", "secret", "token",
        "address", "first_name", "last_name", "full_name", "username"
    )
    IDENTIFIER_COLUMN_PARTS = ("_id", "id", "sku", "postal", "zip", "code", "phone")

    @classmethod
    def build(
        cls,
        query: str,
        rows: List[Dict[str, Any]],
        columns: List[str],
        truncated: bool = False,
        dialect: str = "mysql",
        sampled: bool = False,
    ) -> Dict[str, Any]:
        rows = rows or []
        context: Dict[str, Any] = {
            "row_count": len(rows),
            "truncated": bool(truncated),
            "sampled": bool(sampled),
            "evidence_type": "column_profile",
        }

        if not sampled and cls._is_aggregate_query(query, dialect) and len(rows) <= cls.MAX_AGGREGATE_ROWS:
            grouped_rows = cls._safe_aggregate_rows(rows, columns)
            if grouped_rows:
                context["evidence_type"] = "aggregate_rows"
                context["aggregate_rows"] = grouped_rows
                return context

        context["column_profiles"] = cls._profile_columns(rows, columns)
        return context

    @staticmethod
    def _is_aggregate_query(query: str, dialect: str) -> bool:
        try:
            tree = parse_one(query, read=dialect)
        except Exception:
            return False
        return tree.find(exp.Group) is not None or tree.find(exp.AggFunc) is not None

    @classmethod
    def _safe_aggregate_rows(
        cls,
        rows: List[Dict[str, Any]],
        columns: List[str],
    ) -> List[Dict[str, Any]]:
        safe_columns = [
            column for column in columns
            if not cls._is_sensitive_column(column)
            and not cls._is_identifier_column(column)
        ][:cls.MAX_PROFILE_COLUMNS]
        if not safe_columns:
            return []

        return [
            {
                column: cls._safe_value(row.get(column))
                for column in safe_columns
                if column in row
            }
            for row in rows
        ]

    @classmethod
    def _profile_columns(
        cls,
        rows: List[Dict[str, Any]],
        columns: List[str],
    ) -> List[Dict[str, Any]]:
        profiles: List[Dict[str, Any]] = []
        for column in columns[:cls.MAX_PROFILE_COLUMNS]:
            values = [row.get(column) for row in rows if column in row]
            non_empty = [value for value in values if not cls._is_empty(value)]
            profile: Dict[str, Any] = {
                "column": column,
                "value_count": len(values),
                "empty_count": len(values) - len(non_empty),
            }

            if cls._is_sensitive_column(column) or cls._is_identifier_column(column):
                profiles.append(profile)
                continue

            numeric_values = [
                float(value) for value in non_empty
                if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool)
            ]
            if numeric_values and len(numeric_values) == len(non_empty):
                profile.update({
                    "min": cls._safe_value(min(numeric_values)),
                    "max": cls._safe_value(max(numeric_values)),
                    "average": cls._safe_value(sum(numeric_values) / len(numeric_values)),
                    "sum": cls._safe_value(sum(numeric_values)),
                })
            else:
                date_values = [cls._parse_date(value) for value in non_empty]
                if date_values and all(value is not None for value in date_values):
                    profile["date_min"] = min(date_values).isoformat()
                    profile["date_max"] = max(date_values).isoformat()
                elif non_empty:
                    counts = Counter(str(value) for value in non_empty)
                    profile["distinct_count"] = len(counts)
                    profile["top_values"] = [
                        {"value": key[:cls.MAX_LABEL_LENGTH], "count": count}
                        for key, count in counts.most_common(cls.MAX_TOP_VALUES)
                    ]
            profiles.append(profile)
        return profiles

    @classmethod
    def _is_sensitive_column(cls, column: str) -> bool:
        name = column.casefold()
        return any(part in name for part in cls.SENSITIVE_COLUMN_PARTS)

    @staticmethod
    def _is_identifier_column(column: str) -> bool:
        name = column.casefold()
        return name == "id" or name.endswith("_id") or any(
            part in name for part in ("sku", "postal", "zip", "code", "phone")
        )

    @staticmethod
    def _is_empty(value: Any) -> bool:
        return value is None or (isinstance(value, str) and not value.strip())

    @staticmethod
    def _parse_date(value: Any) -> Optional[datetime]:
        if isinstance(value, datetime):
            return value
        if isinstance(value, date):
            return datetime.combine(value, datetime.min.time())
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
            except ValueError:
                return None
        return None

    @classmethod
    def _safe_value(cls, value: Any) -> Any:
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, float):
            return round(value, 4)
        if isinstance(value, str) and len(value) > cls.MAX_LABEL_LENGTH:
            return value[:cls.MAX_LABEL_LENGTH] + "…"
        return value
