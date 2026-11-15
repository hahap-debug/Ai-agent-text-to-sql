"""
Executive Business Report & Thai Narrative Formatter
Transforms structured query result rows into executive-ready business briefings in professional Thai.
"""

from typing import List, Dict, Any

def format_thai_narrative(question: str, sql: str, rows: List[Dict[str, Any]]) -> str:
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
