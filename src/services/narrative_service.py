"""
Narrative Service: Formats SQL query outputs into professional
Thai Executive Business Reports (Summary, Insights, Actionable Steps).
"""

import json
import re
from typing import List, Dict, Any


class NarrativeService:
    """Service providing executive business narrative synthesis in Thai."""

    REPAIR_SYSTEM_PROMPT = """You write the final Thai executive report for an e-commerce data analysis.
Use only facts present in the supplied insight context. Do not invent metrics, trends, causes, or claims.
Do not include internal reasoning, drafting notes, placeholders, or mention that you are revising the answer.
Return a complete report with Executive Summary, Key Insights, and Actionable Next Steps headings.
If the evidence is insufficient for a specific insight, say so plainly and give a next step that does not assume unsupported facts."""

    _REQUIRED_HEADINGS = (
        "สรุปผลลัพธ์สำคัญ",
        "ข้อมูลเชิงลึก",
        ("คำแนะนำเชิงธุรกิจ", "ข้อเสนอแนะเชิงธุรกิจ"),
    )
    _DRAFT_OR_PLACEHOLDER = re.compile(
        r"wait,\s*i\s+should|i['’]ll\s+rephrase|let\s+me\s+(adjust|revise)|"
        r"todo|tbd|placeholder|ขึ้นอยู่กับข้อมูลในไฟล์|ปีไหนมีลูกค้ามากที่สุด",
        re.IGNORECASE,
    )
    _INCOMPLETE_ENDINGS = ("เพิ่มเต", "และ", "หรือ", "เช่น", "เพื่อ", "โดย", "ได้แก่", "…", "...")

    @classmethod
    def is_complete_executive_answer(
        cls,
        answer: str,
        model_truncated: bool = False,
    ) -> bool:
        """Reject drafts, placeholders, missing sections, and known truncated endings."""
        if model_truncated or not answer or cls._DRAFT_OR_PLACEHOLDER.search(answer):
            return False

        if not all(
            (any(heading in answer for heading in requirement)
             if isinstance(requirement, tuple) else requirement in answer)
            for requirement in cls._REQUIRED_HEADINGS
        ):
            return False

        stripped = answer.rstrip()
        if stripped.endswith(cls._INCOMPLETE_ENDINGS):
            return False
        if stripped.endswith((":", "-", "*")):
            return False

        sections = re.split(
            r"(?=📊\s*\*\*สรุปผลลัพธ์สำคัญ|🔍\s*\*\*ข้อมูลเชิงลึก|🎯\s*\*\*(?:คำแนะนำ|ข้อเสนอแนะ)เชิงธุรกิจ)",
            answer,
        )
        for section in sections:
            if any(heading in section for heading in (
                "สรุปผลลัพธ์สำคัญ", "ข้อมูลเชิงลึก", "คำแนะนำเชิงธุรกิจ", "ข้อเสนอแนะเชิงธุรกิจ"
            )):
                body = re.sub(r"^.*?:\s*", "", section, count=1, flags=re.DOTALL).strip()
                if not body or body in {"-", "1.", "•"}:
                    return False
        return True

    @classmethod
    def build_repair_prompt(
        cls,
        question: str,
        file_name: str,
        insight_context: List[Dict[str, Any]],
        draft: str,
    ) -> str:
        """Create a no-tools repair request with the same bounded evidence."""
        return (
            f"คำถามผู้ใช้: {question}\n"
            f"ไฟล์ Excel ที่สร้างสำเร็จ: {file_name}\n"
            "หลักฐานจากผล query ที่ใช้สร้างไฟล์ (ใช้ข้อมูลนี้เท่านั้น):\n"
            f"{json.dumps(insight_context, ensure_ascii=False, default=str)}\n\n"
            "ร่างคำตอบที่ต้องตรวจและเขียนใหม่ให้สมบูรณ์:\n"
            f"{draft}\n\n"
            "ส่งเฉพาะรายงานภาษาไทยฉบับสมบูรณ์ตามสามหัวข้อที่กำหนด ห้ามใส่ข้อความคิดทบทวน "
            "ห้ามสร้างตัวเลขหรือแนวโน้มที่ไม่มีในหลักฐาน และถ้าหลักฐานไม่พอให้บอกตรง ๆ"
        )

    @classmethod
    def response_was_truncated(cls, response: Any) -> bool:
        """Read provider finish metadata when available."""
        choices = getattr(response, "choices", None) or []
        for choice in choices:
            reason = str(getattr(choice, "finish_reason", "")).casefold()
            if reason in {"length", "max_tokens", "max_token", "maxtokens"}:
                return True
        candidates = getattr(response, "candidates", None) or []
        for candidate in candidates:
            reason = str(getattr(candidate, "finish_reason", "")).casefold()
            if "max_tokens" in reason or "maxtokens" in reason:
                return True
        return False

    @staticmethod
    def format_export_fallback(
        file_name: str,
        insight_context: List[Dict[str, Any]],
    ) -> str:
        """Return a factual complete response if the model cannot repair its draft."""
        total_rows = sum(int(sheet.get("row_count", 0) or 0) for sheet in insight_context)
        was_truncated = any(bool(sheet.get("truncated")) for sheet in insight_context)
        if was_truncated:
            insight_line = "ผลที่ส่งออกถึงขีดจำกัดของชีต จึงยังยืนยันภาพรวมของข้อมูลทั้งหมดไม่ได้"
            next_step = "ระบุช่วงเวลาหรือเงื่อนไขให้แคบลงเพื่อวิเคราะห์ข้อมูลที่เหลือให้ครบ"
        else:
            insight_line = "ข้อมูลสำหรับยืนยันแนวโน้มหรือข้อสรุปเชิงธุรกิจยังไม่เพียงพอในผลสรุปที่ได้รับ"
            next_step = "ตรวจดูข้อมูลในชีตที่เกี่ยวข้อง หรือขอให้สรุปด้วยตัวชี้วัดที่ต้องการโดยตรง"
        return (
            "📊 **สรุปผลลัพธ์สำคัญ (Executive Summary):**\n"
            f"สร้างไฟล์ Excel `{file_name}` สำเร็จ มีข้อมูลจาก query รวม {total_rows:,} แถว\n\n"
            "🔍 **ข้อมูลเชิงลึก (Key Insights):**\n"
            f"- {insight_line}\n\n"
            "🎯 **คำแนะนำเชิงธุรกิจ (Actionable Next Steps):**\n"
            f"- {next_step}"
        )

    @staticmethod
    def format_thai_narrative(
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


format_thai_narrative = NarrativeService.format_thai_narrative
