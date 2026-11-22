"""Detect business questions whose relative time period needs clarification."""

import re
from typing import Optional


class TemporalScopeService:
    """Deterministically ask for a period before an LLM can guess one."""

    AMBIGUOUS_PERIOD = re.compile(
        r"ช่วงนี้|ช่วงหลัง|ระยะนี้|พักนี้|เมื่อเร็วๆนี้|เมื่อไม่นานมานี้|"
        r"\brecently\b|\blately\b|\bthese days\b|\brecent\b|\blast\b",
        re.IGNORECASE,
    )
    EXPLICIT_PERIOD = re.compile(
        r"\b\d+\s*(?:วัน|สัปดาห์|เดือน|ไตรมาส|ปี)(?:ล่าสุด|ที่ผ่านมา|ย้อนหลัง)?|"
        r"วันนี้|เมื่อวาน|สัปดาห์นี้|เดือนนี้|ไตรมาสนี้|ปีนี้|"
        r"\b\d+\s*(?:days?|weeks?|months?|quarters?|years?)\b|"
        r"\b(?:today|yesterday|this week|this month|this quarter|this year|year to date)\b|"
        r"\b\d{4}-\d{1,2}-\d{1,2}\b",
        re.IGNORECASE,
    )
    HISTORICAL_METRIC = re.compile(
        r"ยอดขาย|ขายดี|ขายดีที่สุด|รายได้|กำไร|แบรนด์|สินค้า|คำสั่งซื้อ|ออเดอร์|"
        r"แนวโน้ม|เติบโต|ดีขึ้น|เทียบ|ยอดซื้อ|รีวิว|\bsales\b|\brevenue\b|"
        r"\borders?\b|\bbrands?\b|\bproducts?\b|\btrend\b|\bgrowth\b",
        re.IGNORECASE,
    )

    @classmethod
    def clarification_for(cls, question: str) -> Optional[str]:
        """Return a clarification prompt only for vague periods on historical metrics."""
        if not question or not cls.AMBIGUOUS_PERIOD.search(question):
            return None
        if cls.EXPLICIT_PERIOD.search(question) or not cls.HISTORICAL_METRIC.search(question):
            return None

        return (
            "ต้องการให้ตีความคำว่า ‘ช่วงนี้’ เป็นช่วงไหนครับ เช่น 30 วันล่าสุด, "
            "เดือนนี้ หรือระบุวันที่เริ่มต้น–สิ้นสุดเอง? ผมจะค้นข้อมูลตามช่วงที่เลือก"
        )
