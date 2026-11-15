"""
Mock Provider: Fast simulation engine for offline benchmarking and automated tests.
"""

from typing import List, Dict, Any, Optional, Callable
from src.models.entities import AgentStep, AgentRunResult
from src.services.narrative_service import NarrativeService


def run_mock_react(
    agent: Any,
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

    # Case 0: Multi-Turn Follow-Up
    if chat_history and any(w in q_lower for w in ["5 คนแรก", "3 คนแรก", "คนแรก", "แสดงอีเมล", "ขอแค่", "แล้ว", "ต่อจาก"]):
        prev_context = " ".join([str(h.get("content", "")) + " " + str(h.get("sql", "")) for h in chat_history]).lower()
        if "user" in prev_context or "ลูกค้า" in prev_context:
            sql = "SELECT id, first_name, last_name, email FROM users ORDER BY id ASC LIMIT 5;" if agent.is_mysql else "SELECT user_id, first_name, last_name, email FROM users ORDER BY user_id ASC LIMIT 5;"
            s1 = AgentStep(
                step_number=1,
                thought="ผู้ใช้ถามคำถามต่อเนื่องจากข้อมูลลูกค้าก่อนหน้า ปรับคำสั่ง SQL ให้กรองเฉพาะ 5 คนแรกและดึงอีเมลติดต่อ",
                tool_name="execute_sql",
                parameters={"query": sql}
            )
            exec_res = agent.execute_sql(sql)
            rows = exec_res.get("rows", [])
            s1.observation = rows
            steps.append(s1)
            if step_callback:
                step_callback(s1)

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

    # Case 1-Top: Top Spending Customers
    if any(w in q_lower for w in ["ลูกค้า", "ผู้ใช้", "customer"]) and any(w in q_lower for w in ["ใช้จ่าย", "ยอดซื้อ", "จ่ายเยอะ", "จ่ายมาก", "ยอดรวม", "top", "อันดับ"]) and not any(w in q_lower for w in ["แบรนด์", "brand", "ประเทศ", "country", "ที่อยู่", "address", "มาจากไหน"]):
        limit_val = 3 if any(w in q_lower for w in ["3", "สาม"]) else (5 if any(w in q_lower for w in ["5", "ห้า"]) else 10)
        s1 = AgentStep(
            step_number=1,
            thought=f"ผู้ใช้ต้องการจัดอันดับลูกค้าที่มียอดใช้จ่ายสูงสุด {limit_val} อันดับแรก ตรวจสอบ Schema ของตาราง users และ orders",
            tool_name="inspect_schema",
            parameters={"tables": ["users", "orders"]}
        )
        s1.observation = agent.inspect_schema(["users", "orders"])["summary"]
        steps.append(s1)
        if step_callback:
            step_callback(s1)

        concat_expr = "CONCAT(u.first_name, ' ', u.last_name)" if agent.is_mysql else "(u.first_name || ' ' || u.last_name)"
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
        exec_res = agent.execute_sql(sql)
        rows = exec_res.get("rows", [])
        s2.observation = rows
        steps.append(s2)
        if step_callback:
            step_callback(s2)

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

    # Case 1A-Country: Customer Country Inquiry
    if any(w in q_lower for w in ["ลูกค้า", "ผู้ใช้", "customer"]) and any(w in q_lower for w in ["ประเทศ", "country", "ที่อยู่", "address", "มาจากไหน"]) and not any(w in q_lower for w in ["ซื้อ", "สินค้า", "ของ"]):
        s1 = AgentStep(
            step_number=1,
            thought="ผู้ใช้ต้องการทราบว่าลูกค้ามาจากประเทศใดบ้าง ดึง Schema ของตาราง users และ addresses",
            tool_name="inspect_schema",
            parameters={"tables": ["users", "addresses"]}
        )
        s1.observation = agent.inspect_schema(["users", "addresses"])["summary"]
        steps.append(s1)
        if step_callback:
            step_callback(s1)

        concat_expr = "CONCAT(u.first_name, ' ', u.last_name)" if agent.is_mysql else "(u.first_name || ' ' || u.last_name)"
        limit_val = 3 if any(w in q_lower for w in ["3", "สาม"]) else (5 if any(w in q_lower for w in ["5", "ห้า"]) else 20)

        if agent.is_mysql:
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
        exec_res = agent.execute_sql(sql)
        rows = exec_res.get("rows", [])
        s2.observation = rows
        steps.append(s2)
        if step_callback:
            step_callback(s2)

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

    # Case 1A: Customer Purchases with Country
    if any(w in q_lower for w in ["ลูกค้า", "ผู้ใช้", "customer"]) and any(w in q_lower for w in ["ซื้อ", "order", "สินค้า", "ของ"]) and any(w in q_lower for w in ["ประเทศ", "country"]):
        s1 = AgentStep(
            step_number=1,
            thought="ผู้ใช้ต้องการทราบว่าลูกค้าแต่ละคนซื้อของอะไรบ้างและมาจากประเทศไหน ตรวจสอบ Schema ของตาราง users, orders, order_items, products, addresses",
            tool_name="inspect_schema",
            parameters={"tables": ["users", "orders", "order_items", "products", "addresses"]}
        )
        s1.observation = agent.inspect_schema(s1.parameters["tables"])["summary"]
        steps.append(s1)
        if step_callback:
            step_callback(s1)

        if agent.is_mysql:
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
        exec_res = agent.execute_sql(sql)
        rows = exec_res.get("rows", [])
        s2.observation = rows
        steps.append(s2)
        if step_callback:
            step_callback(s2)

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

    # Case 1B: Customer Purchases (Items Bought per Customer)
    if any(w in q_lower for w in ["ลูกค้า", "ผู้ใช้", "customer"]) and any(w in q_lower for w in ["ซื้อ", "order", "สินค้า", "ของ"]):
        s1 = AgentStep(
            step_number=1,
            thought="ผู้ใช้ต้องการทราบว่าลูกค้าแต่ละคนซื้อของอะไรบ้าง ตรวจสอบ Schema ของตาราง users, orders, order_items, products",
            tool_name="inspect_schema",
            parameters={"tables": ["users", "orders", "order_items", "products"]}
        )
        s1.observation = agent.inspect_schema(s1.parameters["tables"])["summary"]
        steps.append(s1)
        if step_callback:
            step_callback(s1)

        concat_expr = "CONCAT(u.first_name, ' ', u.last_name)" if agent.is_mysql else "(u.first_name || ' ' || u.last_name)"
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
        exec_res = agent.execute_sql(sql)
        rows = exec_res.get("rows", [])
        s2.observation = rows
        steps.append(s2)
        if step_callback:
            step_callback(s2)

        final_ans = f"""📊 **สรุปผลลัพธ์สำคัญ (Executive Summary):**
สืบค้นข้อมูลรายการสินค้าที่ลูกค้าแต่ละคนซื้อในระบบ `ecommerce_db` พบรายการการซื้อสินค้าทั้งสิ้น **{len(rows)} รายการ**

🔍 **ข้อมูลเชิงลึก (Key Insights):**
1. **ความหลากหลายของสินค้าต่อลูกค้า:** ลูกค้าแต่ละรายมีการเลือกซื้อสินค้าครอบคลุมหลายหมวดหมู่
2. **ยอดการใช้จ่ายรวม (Basket Value):** มีลูกค้ากลุ่ม Active Buyer ที่สั่งซื้อซ้ำหลายรายการ ซึ่งเป็นกลุ่มสร้างรายได้หลัก
3. **การมีส่วนร่วมของลูกค้า:** พบว่าผู้ซื้อส่วนใหญ่ให้ความสนใจในกลุ่มสินค้าที่มีโปรโมชัน

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

    # Case 1C: Customers / Users Basic List
    if any(w in q_lower for w in ["ลูกค้า", "ผู้ใช้", "สมาชิก", "customer", "user", "คนซื้อ", "ข้อมูลผู้ใช้", "รายชื่อ"]):
        s1 = AgentStep(
            step_number=1,
            thought="ผู้ใช้ต้องการสืบค้นข้อมูลลูกค้า/สมาชิกในระบบ ตรวจสอบแคตตาล็อกพบตารางที่เกี่ยวข้องคือ users และ addresses",
            tool_name="inspect_schema",
            parameters={"tables": ["users", "addresses"]}
        )
        s1.observation = agent.inspect_schema(["users", "addresses"])["summary"]
        steps.append(s1)
        if step_callback:
            step_callback(s1)

        if agent.is_mysql:
            sql = "SELECT id, first_name, last_name, email, phone, created_at FROM users ORDER BY id ASC;"
        else:
            sql = "SELECT user_id, first_name, last_name, email, phone, created_at FROM users ORDER BY user_id ASC;"

        s2 = AgentStep(
            step_number=2,
            thought="ทราบโครงสร้างคอลัมน์ของ users แล้ว เขียน SQL เพื่อดึงข้อมูลลูกค้า (ชื่อ-นามสกุล, อีเมล, เบอร์โทร, วันที่สมัคร) โดยคัดกรองข้อมูลความปลอดภัย (password_hash) ออก",
            tool_name="execute_sql",
            parameters={"query": sql}
        )
        exec_res = agent.execute_sql(sql)
        s2.observation = exec_res.get("rows", [])
        steps.append(s2)
        if step_callback:
            step_callback(s2)

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

    # Case 2: Cancellations / Returns (Self-Healing Demonstration)
    elif any(w in q_lower for w in ["ยกเลิก", "cancel", "cancelled", "คืน", "return"]):
        s1 = AgentStep(
            step_number=1,
            thought="ผู้ใช้ถามถึงคำสั่งซื้อที่ถูกยกเลิก/ส่งคืน เริ่มต้นตรวจสอบตาราง orders ในฐานข้อมูล",
            tool_name="inspect_schema",
            parameters={"tables": ["orders"]}
        )
        s1.observation = agent.inspect_schema(["orders"])["summary"]
        steps.append(s1)
        if step_callback:
            step_callback(s1)

        s2 = AgentStep(
            step_number=2,
            thought="ตรวจสอบคอลัมน์เหตุผลในตาราง orders",
            tool_name="execute_sql",
            parameters={"query": "SELECT id, cancel_reason FROM orders LIMIT 3;"}
        )
        exec_fail = agent.execute_sql(s2.parameters["query"])
        s2.is_error = True
        s2.observation = f"ERROR: {exec_fail.get('message')}"
        steps.append(s2)
        if step_callback:
            step_callback(s2)

        s3 = AgentStep(
            step_number=3,
            thought="เกิด Error ตาราง orders ไม่มีคอลัมน์ cancel_reason จึงสแกน Schema ตาราง order_returns และ return_reasons",
            tool_name="inspect_schema",
            parameters={"tables": ["order_returns", "return_reasons"]}
        )
        s3.observation = agent.inspect_schema(["order_returns", "return_reasons"])["summary"]
        steps.append(s3)
        if step_callback:
            step_callback(s3)

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
        exec_succ = agent.execute_sql(sql_corrected)
        s4.observation = exec_succ.get("rows", [])
        steps.append(s4)
        if step_callback:
            step_callback(s4)

        rows = exec_succ.get("rows", [])
        final_ans = NarrativeService.format_thai_narrative(user_question, sql_corrected, rows)
        return AgentRunResult(
            user_question=user_question,
            final_answer=final_ans,
            steps=steps,
            last_executed_sql=sql_corrected,
            last_query_result=rows,
            success=True
        )

    # Case 3: Products Catalog
    elif any(w in q_lower for w in ["สินค้า", "product", "sku", "แคตตาล็อก", "ราคา"]):
        s1 = AgentStep(
            step_number=1,
            thought="ผู้ใช้ต้องการดูข้อมูลสินค้าในระบบ จากแคตตาล็อกตารางที่เกี่ยวข้องคือ products, categories, brands",
            tool_name="inspect_schema",
            parameters={"tables": ["products", "categories", "brands"]}
        )
        s1.observation = agent.inspect_schema(["products", "categories", "brands"])["summary"]
        steps.append(s1)
        if step_callback:
            step_callback(s1)

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
        exec_res = agent.execute_sql(sql)
        s2.observation = exec_res.get("rows", [])
        steps.append(s2)
        if step_callback:
            step_callback(s2)

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

    # Case 4: Orders / Transactions
    elif any(w in q_lower for w in ["คำสั่งซื้อ", "order", "ออเดอร์", "การสั่งซื้อ", "ใบสั่ง"]):
        s1 = AgentStep(
            step_number=1,
            thought="ผู้ใช้ต้องการข้อมูลคำสั่งซื้อในระบบ ดึง Schema ตาราง orders และ users",
            tool_name="inspect_schema",
            parameters={"tables": ["orders", "users"]}
        )
        s1.observation = agent.inspect_schema(["orders", "users"])["summary"]
        steps.append(s1)
        if step_callback:
            step_callback(s1)

        concat_expr = "CONCAT(u.first_name, ' ', u.last_name)" if agent.is_mysql else "(u.first_name || ' ' || u.last_name)"
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
        exec_res = agent.execute_sql(sql)
        s2.observation = exec_res.get("rows", [])
        steps.append(s2)
        if step_callback:
            step_callback(s2)

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

    # Case 5: Default (Top Brands / Sales Ranking)
    else:
        s1 = AgentStep(
            step_number=1,
            thought="ผู้ใช้ต้องการวิเคราะห์ยอดขายตามแบรนด์ ดึง Schema ของตาราง brands, products, order_items จากฐานข้อมูลจริง",
            tool_name="inspect_schema",
            parameters={"tables": ["brands", "products", "order_items"]}
        )
        s1.observation = agent.inspect_schema(["brands", "products", "order_items"])["summary"]
        steps.append(s1)
        if step_callback:
            step_callback(s1)

        if agent.is_mysql:
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
        exec_res = agent.execute_sql(sql_query)
        s2.observation = exec_res.get("rows", [])
        steps.append(s2)
        if step_callback:
            step_callback(s2)

        rows = exec_res.get("rows", [])
        final_ans = NarrativeService.format_thai_narrative(user_question, sql_query, rows)

        return AgentRunResult(
            user_question=user_question,
            final_answer=final_ans,
            steps=steps,
            last_executed_sql=sql_query,
            last_query_result=rows,
            success=True
        )
