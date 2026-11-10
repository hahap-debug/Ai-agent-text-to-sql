# 🚀 E-Commerce AI Data Analytics Agent (Powered by Google Gemini & MCP)

> **ระบบเอเจนต์วิเคราะห์ข้อมูลอัจฉริยะระดับองค์กร ขับเคลื่อนด้วยขุมพลัง Google Gemini**  
> ออกแบบมาเพื่อแปลงคำถามภาษาธรรมชาติ (Natural Language) ให้เป็นคำสั่ง MySQL 8.x ที่แม่นยำ ปลอดภัย และนำข้อมูลมาวิเคราะห์สรุปเป็นรายงานเชิงกลยุทธ์ภาษาไทยสำหรับผู้บริหาร พร้อมมาตรฐาน **Model Context Protocol (MCP)** สำหรับเชื่อมต่อกับ Claude Desktop, Cursor และ AI Platform ภายนอก

---

## 🎯 ขอบเขตการทำงานของระบบ (System Scope & Boundaries for Viewers)

เพื่อให้ผู้ประเมินและผู้ใช้งานเข้าใจจุดประสงค์ ขอบเขต และข้อจำกัดของระบบอย่างชัดเจน ระบบนี้ถูกกำหนดขอบเขตการทำงาน (System Scope) ไว้ดังนี้:

```
+---------------------------------------------------------------------------------------------------------+
|                                      🎯 SYSTEM SCOPE & BOUNDARIES                                       |
+---------------------------------------------------------------------------------------------------------+
|  ✅ สิ่งที่ระบบทำได้ (IN-SCOPE)                          |  ❌ สิ่งที่อยู่นอกเหนือขอบเขต (OUT-OF-SCOPE)           |
|----------------------------------------------------------|------------------------------------------------------|
| • ขับเคลื่อนหลักด้วย **Google Gemini (Primary Engine)**   | • ห้ามแก้ไข ดัดแปลง หรือลบข้อมูลทุกกรณี               |
|   (รองรับ Gemini 3.5 Flash, 3.5 Flash-Lite, Pro)         |   (ไม่มีคำสั่ง INSERT, UPDATE, DELETE, DROP, ALTER)  |
| • เชื่อมต่อฐานข้อมูล **MySQL 8.x (`ecommerce_db`)**      | • ไม่อนุญาตให้รัน Stored Procedure, Trigger, DDL     |
| • สแกนโครงสร้างและ Foreign Key Graph แบบ Dynamic          | • ไม่เข้าถึงระบบไฟล์ (OS Files) หรือฐานข้อมูลอื่น    |
| • รันคำสั่งคิวรีแบบ Read-Only ผ่าน AST Safety Guard      | • ไม่ใช่งาน Machine Learning / Predictive Modeling   |
| • ซ่อมแซมคำสั่ง SQL อัตโนมัติ (Self-Healing Loop)        | • จำกัดปริมาณข้อมูลสูงสุดไม่เกิน 100 แถว/คิวรี       |
| • สรุปรายงานธุรกิจภาษาไทย 3 มิติ (ผู้บริหาร/Insight/แผน) | • ไม่รองรับงานประมวลผลข้อมูลก้อนใหญ่แบบ ETL          |
| • รองรับ 3 ช่องทาง: Web Dashboard, MCP Server, และ CLI   |                                                      |
+---------------------------------------------------------------------------------------------------------+
```

### 1. ขอบเขตโมเดลประมวลผลหลัก (Primary AI Engine: Google Gemini)
* **แกนกลางของระบบ (Core Intelligence):** ระบบถูกออกแบบและปรับแต่งขึ้นมาสำหรับ **Google Gemini** โดยเฉพาะ ใช้สถาปัตยกรรม **Gemini Function Calling (Tools API)** ร่วมกับวงจร **ReAct Reasoning (Thought ➔ Action ➔ Observation)**
* **โมเดลที่กำหนดเป็นค่าเริ่มต้น (Primary Default):**
  * 🌟 **`gemini-3.5-flash` (Primary Production Model):** เป็นโมเดลหลักที่ใช้ในการสืบค้น มีความสามารถในการวิเคราะห์ Foreign Key ซับซ้อน (3–4 ตาราง), เข้าใจ Subquery/Window Function, และสร้างบทวิเคราะห์ภาษาไทยได้อย่างลึกซึ้ง
  * ⚡ **`gemini-3.5-flash-lite` (High-Throughput Alternative):** รองรับการสลับใช้งานสำหรับงานที่ต้องการความเร็วสูงระดับเสี้ยววินาที หรือกรณีใช้งานภายใต้โควตา Free Tier
  * 🧠 **`gemini-pro` (Deep Analytical Reasoning):** รองรับการเลือกใช้งานสำหรับโจทย์กลยุทธ์ทางธุรกิจที่มีเงื่อนไขซับซ้อนสูง

### 2. ขอบเขตข้อมูลและความปลอดภัย (Data & Security Scope)
* **อ่านข้อมูลได้อย่างเดียว 100% (Strictly Read-Only):**
  * เชื่อมต่อผ่านบัญชีผู้ใช้ `ecommerce_reader` บนฐานข้อมูล MySQL 8.x
  * มี **AST Security Guardrail (`sqlglot`)** สกัดกั้นคำสั่งดัดแปลงข้อมูล (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `TRUNCATE`) และบล็อก Stacked Query (การต่อคำสั่งด้วย `;`) ทันที 100%
* **ครอบคลุม 18 ตารางมาตรฐานในแคตตาล็อก `ecommerce_db`:**
  * **ลูกค้าและที่อยู่:** `users`, `addresses`
  * **สินค้า หมวดหมู่ และแบรนด์:** `products`, `categories`, `brands`
  * **คลังสินค้าและสต็อก:** `warehouses`, `inventory`
  * **ธุรกรรมคำสั่งซื้อและรายการย่อย:** `orders`, `order_items`
  * **การชำระเงินและช่องทางขนส่ง:** `payments`, `payment_methods`, `shipping_methods`
  * **การส่งเสริมการขาย:** `coupons`, `order_coupons`
  * **บริการหลังการขายและการคืนสินค้า:** `product_reviews`, `support_tickets`, `order_returns`, `return_reasons`

### 3. ขอบเขตการให้บริการแก่ผู้ใช้ (Target Audience & Interfaces)
ระบบเปิดให้บริการผ่าน 3 รูปแบบตามบทบาทของผู้ใช้งาน:
1. **ผู้บริหารและผู้จัดการธุรกิจ (Business Executives & Managers):** ใช้งานผ่าน **Streamlit Web Dashboard** ถามคำถามภาษาไทย ดูตารางข้อมูล กราฟสถิติ และรายงานสรุปเชิงกลยุทธ์
2. **นักพัฒนาและ AI แพลตฟอร์มอื่น (Developers & External AI):** ใช้งานผ่าน **Model Context Protocol (MCP Server)** เพื่อให้ Claude Desktop, Cursor, หรือ Windsurf เข้ามาดึงข้อมูลไปทำงานต่อได้ทันที
3. **วิศวกรข้อมูลและ QA (Data Engineers & QA):** ใช้งานผ่าน **Terminal CLI** (`test_query.py`, `cli.py`) และชุดทดสอบ `pytest`

---

## 📌 สถาปัตยกรรมและการทำงาน (Architecture & Key Features)

```
+-----------------------------------------------------------------------------------+
|                        User Question (ภาษาธรรมชาติภาษาไทย)                          |
+-----------------------------------------------------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                           Google Gemini Brain (ReAct Loop)                        |
|                                                                                   |
|  1. Thought: วิเคราะห์เจตนาทางธุรกิจ เลือกตารางที่เกี่ยวข้องจาก Catalog                 |
|  2. Action: inspect_schema(tables=[...]) ตรวจสอบคอลัมน์และ Foreign Keys จริง      |
|  3. Observation: โครงสร้างคอลัมน์, Data Types, Primary & Foreign Keys             |
|  4. Thought: ร่าง MySQL Query 8.x ปลอดภัยตามกฎ ONLY_FULL_GROUP_BY                 |
|  5. Action: execute_sql(query="SELECT ...") ➔ ผ่าน AST Safety Guard              |
|  6. Observation: ผลลัพธ์ข้อมูลจาก MySQL (หรือ Error หากมี เพื่อทำ Self-Healing)    |
+-----------------------------------------------------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                         Final Executive Business Report                           |
|  📊 1. สรุปผลลัพธ์สำคัญ (Executive Summary): ตัวเลขหลักและประเด็นสำคัญ            |
|  🔍 2. ข้อมูลเชิงลึกและแนวโน้ม (Key Insights): วิเคราะห์ความหมายทางธุรกิจ          |
|  🎯 3. ข้อเสนอแนะเชิงกลยุทธ์ (Actionable Next Steps): สิ่งที่ควรดำเนินการต่อ       |
+-----------------------------------------------------------------------------------+
```

### ฟีเจอร์เด่นระดับโปรดักชัน:
1. **Native Gemini Tool Calling:** ทำงานร่วมกับ API ของ Google GenAI โดยตรง ไม่ใช่การตัดต่อข้อความ ทำให้การเรียกใช้เครื่องมือเสถียรและรวดเร็ว
2. **Entity Preservation & De-duplication:** Prompts ถูกออกแบบให้เข้าใจความสัมพันธ์ 1-to-Many โดยใช้ `LEFT JOIN` และ `COALESCE` เพื่อรักษาข้อมูลที่ยังไม่ระบุ (เช่น ลูกค้าที่ยังไม่กรอกที่อยู่) และใช้ `DISTINCT` ป้องกันข้อมูลเบิ้ลซ้ำ
3. **Automated Self-Correction:** หากคิวรีติด Error หรือเจอตารางที่ซับซ้อน โมเดล Gemini จะนำ Error ไปวิเคราะห์และสร้าง SQL ชุดใหม่มาแก้ไขตัวเองทันทีภายใน 6 ขั้นตอน
4. **Interactive Multi-Platform Support:** ไม่ผูกขาดกับหน้าเว็บเดียว แต่เปิดเป็น **MCP Server มาตรฐาน** ให้โปรแกรมอย่าง Claude Desktop นำไปใช้ได้ด้วย

---

## 📂 โครงสร้างโปรเจกต์ (Project Structure)

```text
Agent_natural_langauge_to_sql/
├── .env                         # ตั้งค่า Gemini API Key และ MySQL Credentials
├── AGENTS.md                    # ข้อกำหนดสถาปัตยกรรม ReAct Agent และ Specification
├── README.md                    # เอกสารคู่มือระบบและขอบเขตการทำงาน (ฉบับนี้)
├── requirements.txt             # รายการแพ็กเกจ Python ทั้งหมด
├── app.py                       # Web Dashboard (Streamlit) แสดงผล ReAct Trace และชาร์ต
├── cli.py                       # Interactive CLI สำหรับทดสอบถามตอบใน Terminal
├── test_query.py                # เครื่องมือรันคำถามเดี่ยวและ Benchmark 10 คำถาม
├── mcp_server/                  # 🔌 ระบบ MCP Server แยก Tool อิสระสำหรับ AI อื่น
│   ├── server.py                # จุดรัน FastMCP Server (stdio transport)
│   ├── config.py                # การตั้งค่า MySQL สำหรับ MCP Server
│   ├── db.py                    # Helper จัดการ MySQL Connection
│   ├── security.py              # AST Security Guardrail ป้องกันคำสั่งแก้ไขข้อมูล
│   ├── test_mcp.py              # สคริปต์ทดสอบ Tool ทั้ง 3 ตัวของ MCP Server
│   ├── claude_desktop_config.json # ไฟล์คอนฟิกพร้อมก๊อปปี้ไปวางใน Claude Desktop
│   ├── README.md                # คู่มือการใช้งาน MCP Server
│   └── tools/
│       ├── catalog.py           # [Tool 1]: list_tables (ดูรายชื่อตารางและคำอธิบาย)
│       ├── schema.py            # [Tool 2]: inspect_schema (ดูคอลัมน์, PK, FK)
│       └── query.py             # [Tool 3]: execute_sql (รัน SELECT ปลอดภัย)
├── src/
│   ├── config.py                # โหลดค่า Config และกำหนด Gemini เป็นโมเดลหลัก
│   ├── database.py              # ตัวเชื่อมต่อ MySQL พร้อม Foreign Key Graph Hints
│   ├── validator.py             # ตัวตรวจเช็กความปลอดภัย SQL ด้วย sqlglot AST
│   ├── prompts.py               # Master Prompts, Few-Shot และ Executive Narrative Schema
│   ├── agent.py                 # ReAct Agent Core Orchestrator ขับเคลื่อนด้วย Gemini
│   ├── test_sets.py             # ชุดคำถามทดสอบมาตรฐาน (Benchmark Test Set 10 ข้อ)
│   └── seed_db.py               # สคริปต์สร้างข้อมูลจำลอง SQLite (โหมด Offline Dev)
└── tests/
    └── test_agent.py            # Automated Test Suite (20 Test Cases ผ่าน 100%)
```

---

## 🛠️ การติดตั้งและตั้งค่าเริ่มต้น (Setup & Configuration)

### 1. ติดตั้ง Dependencies
```bash
pip install -r requirements.txt
```

### 2. ตั้งค่าไฟล์สภาพแวดล้อม (`.env`)
กำหนดค่าการเชื่อมต่อ Google Gemini และ MySQL ในไฟล์ `.env`:
```env
# กำหนด Google Gemini เป็น AI Engine หลัก
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_google_gemini_api_key_here
GEMINI_MODEL=gemini-3.5-flash

# การเชื่อมต่อฐานข้อมูล MySQL
DB_TYPE=mysql
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=ecommerce_reader
DB_PASSWORD=reader_pass123
DB_NAME=ecommerce_db
```

---

## 💻 วิธีการรันใช้งาน (Usage Channels)

### ช่องทางที่ 1: รันผ่าน Web Dashboard (Streamlit)
```bash
python -m streamlit run app.py
```
* เข้าใช้งานผ่านเบราว์เซอร์ที่ `http://localhost:8501`
* เลือกรันคำถามทดสอบด่วน หรือเลือกคำถามจากเมนู **Benchmark Test Set (10 ข้อ)** ได้ทันที
* แสดงผล SQL Query, ตารางผลลัพธ์, กราฟข้อมูล, รายงานสรุปธุรกิจภาษาไทย และ ReAct Execution Trace

### ช่องทางที่ 2: รันคำถามทดสอบผ่าน Terminal CLI (`test_query.py`)
```bash
# รันคำถามเดี่ยวแบบเห็นขั้นตอนคิด (ReAct Trace)
python test_query.py "ขอข้อมูลลูกค้าทั้งหมดหน่อย"
python test_query.py "แบรนด์ไหนขายดีที่สุด 5 อันดับแรก และมียอดขายรวมเท่าไหร่"

# รันเฉพาะข้อจากชุด Benchmark Test Set (ข้อ 1 ถึง 10)
python test_query.py 1
python test_query.py 5

# รันประเมินครบทั้ง 10 คำถามพร้อมตารางสรุปคะแนน
python test_query.py --all
```

---

## 🔌 การเชื่อมต่อผ่าน Model Context Protocol (MCP Server)

ระบบมาพร้อม MCP Server มาตรฐานสากล ช่วยให้ AI ค่ายอื่นๆ เช่น **Claude Desktop**, **Cursor**, หรือ **Windsurf** สามารถเชื่อมต่อเข้ามาดึงข้อมูลจาก `ecommerce_db` ไปวิเคราะห์ต่อได้ทันที:

### 1. การตั้งค่าใน Claude Desktop
เปิดไฟล์ `%APPDATA%\Claude\claude_desktop_config.json` แล้วเพิ่ม:
```json
{
  "mcpServers": {
    "ecommerce-db": {
      "command": "python",
      "args": [
        "C:\\Users\\ACER\\Desktop\\Agent_natural_langauge_to_sql\\mcp_server\\server.py"
      ],
      "env": {
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

### 2. การตั้งค่าใน Cursor / Antigravity
ในหน้า **Settings ➔ MCP Servers** เพิ่มเซิร์ฟเวอร์ใหม่:
* **Name:** `ecommerce-db`
* **Type:** `command` (stdio)
* **Command:** `python C:\Users\ACER\Desktop\Agent_natural_langauge_to_sql\mcp_server\server.py`

### 3. ทดสอบเครื่องมือ MCP Server
```bash
python mcp_server/test_mcp.py
```

---

## 🧪 การตรวจสอบและทดสอบระบบ (Verification Suite)

ระบบมีชุด Automated Unit Test ครอบคลุมการทำงานทั้งระบบ **20 การทดสอบ**:
```bash
python -m pytest tests/test_agent.py -v
```
**ผลการทดสอบผ่านครบ 100% (20/20 PASSED):**
* **AST Security:** บล็อกคำสั่งแก้ไข/ทำลายข้อมูลทุกรูปแบบ และบล็อก Stacked Query
* **Dynamic Inspection:** ดึง Schema คอลัมน์และ Foreign Key ถูกต้องตามจริง
* **Safe Execution:** รันคำสั่งอ่านข้อมูลและจำกัดจำนวนแถวได้ตามเกณฑ์
* **ReAct & Self-Healing:** วงจรคิดวิเคราะห์และซ่อมแซมคำสั่ง SQL ทำงานได้อย่างถูกต้อง

---

## ⚠️ ข้อควรทราบและการบริหารจัดการโควตา (Gemini API & Best Practices)

1. **การทำงานของ ReAct Loop กับจำนวน API Request:**  
   ในแต่ละคำถาม ระบบ ReAct Agent จะต้องส่งคำขอไปยัง Gemini API ประมาณ 2–3 รอบ (1. ตรวจสอบ Schema ➔ 2. รัน SQL ➔ 3. เขียนสรุปรายงานธุรกิจ)
2. **เพดานโควตาของ Google AI Studio Free Tier:**  
   * โมเดลหลัก **`gemini-3.5-flash`** บนแพ็กเกจ Free Tier มีการจำกัดจำนวนคำขอต่อวัน หากรันคำถามต่อเนื่องหลายข้ออาจพบข้อผิดพลาด `429 RESOURCE_EXHAUSTED` ชั่วคราว ซึ่งเป็นเพดานโควตาของคีย์ฟรี ไม่ใช่ข้อผิดพลาดของตรรกะในระบบ
   * **คำแนะนำ:** หากต้องการรันคิวรียาวๆ ในโหมดฟรี สามารถสลับไปใช้ **`gemini-3.5-flash-lite`** ซึ่งได้รับโควตารายวันสูงกว่ามาก หรือเปิดใช้งานแบบ Pay-as-you-go บน Google Cloud ซึ่งมีค่าบริการเฉลี่ยเพียงเศษสตางค์ต่อคำถาม
3. **หลัก Entity Preservation (ข้อมูลที่ไม่ระบุ):**  
   สำหรับลูกค้าที่ยังไม่ได้บันทึกที่อยู่ หรือยังไม่มีประวัติการซื้อของ ระบบจะแสดงผลเป็น `"ยังไม่ระบุ"` ตามข้อเท็จจริงในฐานข้อมูล เพื่อป้องกันไม่ให้ข้อมูลลูกค้าสูญหายจากรายงานสรุป
