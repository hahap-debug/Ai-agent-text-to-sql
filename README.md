<<<<<<< HEAD
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

## 📌 สถาปัตยกรรมระดับองค์กร (N-Tier Enterprise Architecture)

ระบบได้รับการออกแบบตามมาตรฐาน **4-Tier Architecture** เพื่อแยกส่วนความรับผิดชอบ (Separation of Concerns), เพิ่มความปลอดภัย และรองรับการขยายตัว (Scalability):

```text
+---------------------------------------------------------------------------------------------------+
|  [TIER 1: PRESENTATION LAYER (Clients & Interfaces)]                                              |
|  • Streamlit Web Dashboard (Port 8501)       • Interactive Terminal CLI (cli.py)                  |
|  • External AI Agents via MCP Server         • AgentAPIClient Python SDK (src/api/client.py)       |
+---------------------------------------------------------------------------------------------------+
                                                  |
                     (HTTP REST / Server-Sent Events / SSE Streaming / stdio)
                                                  v
+---------------------------------------------------------------------------------------------------+
|  [TIER 2: APPLICATION SERVICE & API GATEWAY LAYER] (FastAPI Port 8000)                             |
|  • OpenAPI / Swagger UI (/docs)              • Server-Sent Events (SSE) Live Reasoning Stream     |
|  • Pydantic Request/Response DTO Validation  • Cross-Origin Resource Sharing (CORS) Middleware    |
+---------------------------------------------------------------------------------------------------+
                                                  |
                                                  v
+---------------------------------------------------------------------------------------------------+
|  [TIER 3: DOMAIN LOGIC & AI AGENT CORE] (src/agent/)                                               |
|  • ReAct Loop Orchestrator (core.py)         • Google GenAI & Local Ollama Engines                |
|  • Coreference Multi-turn Memory             • Business Narrative & Thai Executive Reporter       |
|  • Privacy Guards & Limit Sanitization Rules • sqlglot AST SQL Safety Validator (Read-Only Guard) |
+---------------------------------------------------------------------------------------------------+
                                                  |
                                                  v
+---------------------------------------------------------------------------------------------------+
|  [TIER 4: DATA ACCESS LAYER & PERSISTENCE] (src/database.py & MySQL / SQLite)                     |
|  • DatabaseConnection Pool Manager           • Automatic Port Probe & Resilient Failover          |
|  • MySQL 8.x (Primary: ecommerce_db)         • Local SQLite Fallback (Offline Benchmark Dev)      |
+---------------------------------------------------------------------------------------------------+
```

### ฟีเจอร์เด่นระดับโปรดักชัน:
1. **N-Tier Decoupling:** แยกชั้น Presentation ออกจาก Agent Core อย่างสมบูรณ์ผ่าน FastAPI REST/SSE Tier รองรับการเชื่อมต่อจาก Web, Mobile, Line/Slack Bot หรือระบบภายนอก
2. **Real-Time SSE Streaming:** รองรับ Server-Sent Events (`/api/v1/query/stream`) ส่งความคืบหน้าของ Agent Thought และ Tool Action กลับมาแสดงผลบน Client แบบเรียลไทม์
3. **Native Gemini Tool Calling:** ทำงานร่วมกับ API ของ Google GenAI โดยตรง ไม่ใช่การตัดต่อข้อความ ทำให้การเรียกใช้เครื่องมือเสถียรและรวดเร็ว
4. **Entity Preservation & De-duplication:** Prompts ถูกออกแบบให้เข้าใจความสัมพันธ์ 1-to-Many โดยใช้ `LEFT JOIN` และ `COALESCE` เพื่อรักษาข้อมูลที่ยังไม่ระบุ (เช่น ลูกค้าที่ยังไม่กรอกที่อยู่) และใช้ `DISTINCT` ป้องกันข้อมูลเบิ้ลซ้ำ
5. **Automated Self-Correction:** หากคิวรีติด Error หรือเจอตารางที่ซับซ้อน โมเดล Gemini จะนำ Error ไปวิเคราะห์และสร้าง SQL ชุดใหม่มาแก้ไขตัวเองทันทีภายใน 6 ขั้นตอน
6. **Interactive Multi-Platform Support:** ไม่ผูกขาดกับหน้าเว็บเดียว แต่เปิดเป็นทั้ง **FastAPI Service** และ **MCP Server มาตรฐาน** ให้โปรแกรมอย่าง Claude Desktop นำไปใช้ได้ด้วย

---

## 📂 โครงสร้างโปรเจกต์ (Project Structure)

```text
Agent_natural_langauge_to_sql/
├── .env.example                 # แม่แบบการตั้งค่าสภาพแวดล้อม (Environment Template)
├── .env                         # ตั้งค่า Gemini API Key และ MySQL Credentials (ส่วนตัว)
├── .gitignore                   # กฎการละเว้นไฟล์ที่ไม่จำเป็นสำหรับ Git
├── AGENTS.md                    # ข้อกำหนดสถาปัตยกรรม ReAct Agent และ Specification
├── README.md                    # เอกสารคู่มือระบบและขอบเขตการทำงาน (ฉบับนี้)
├── requirements.txt             # รายการแพ็กเกจ Python ทั้งหมด
├── run_web.bat / run_web.ps1    # ทางลัดเปิด Streamlit Web Dashboard (Port 8501)
├── run_api.bat / run_api.ps1    # ทางลัดเปิด FastAPI Backend Service (Port 8000)
├── app.py                       # [Tier 1] Web Dashboard (Streamlit) แสดงผล ReAct Trace และชาร์ต
├── cli.py                       # [Tier 1] Interactive CLI สำหรับทดสอบถามตอบใน Terminal
│
├── data/                        # ฐานข้อมูลตัวอย่างและชุด Schema
│   ├── ecommerce.db             # ฐานข้อมูล SQLite จำลองสำหรับ Local Testing / Offline Dev
│   └── ecommerce_db.sql         # ไฟล์ SQL Dump โครงสร้างและข้อมูลตัวอย่าง 18 ตาราง
│
├── src/                         # 🧠 Core Application Package
│   ├── __init__.py              # Export โมดูลหลัก
│   ├── config.py                # โหลดค่า Config และกำหนดโมเดลหลัก
│   ├── database.py              # [Tier 4] ตัวเชื่อมต่อ MySQL/SQLite พร้อม Fast Socket Probe & Fallback
│   ├── validator.py             # [Tier 3] ตัวตรวจเช็กความปลอดภัย SQL ด้วย sqlglot AST Guardrail
│   ├── prompts.py               # [Tier 3] Master Prompts, Few-Shot และ Executive Narrative Schema
│   │
│   ├── api/                     # 🌐 [Tier 2: API Service Layer] (FastAPI REST & SSE)
│   │   ├── __init__.py          # API package initializer
│   │   ├── app.py               # FastAPI App instance พร้อม CORS Middleware
│   │   ├── routes.py            # Endpoints: /health, /tables, /schema, /query, /query/stream
│   │   ├── schemas.py           # Pydantic DTOs สำหรับ Request/Response
│   │   └── client.py            # Python SDK Client สำหรับเรียกใช้ API จาก Client ใดก็ได้
│   │
│   ├── agent/                   # 🤖 [Tier 3: Domain & Agent Core] (Modular Package)
│   │   ├── __init__.py          # Export DatabaseAgent, AgentStep, AgentRunResult
│   │   ├── core.py              # ReAct Agent Orchestrator เชื่อมต่อกับ Engines ต่างๆ
│   │   ├── models.py            # Dataclasses โครงสร้างข้อมูล (AgentStep, AgentRunResult)
│   │   ├── rules.py             # Privacy Field Filtering & Limit Sanitization Guards
│   │   ├── narrative.py         # ตัวสร้างสรุปรายงานธุรกิจภาษาไทย 3 มิติ (Executive Report)
│   │   ├── coreference.py       # ระบบวิเคราะห์และขยายความคำถามต่อเนื่องหลายเทิร์น
│   │   └── engines/             # ตัวขับเคลื่อน ReAct แยกตามผู้ให้บริการ
│   │       ├── __init__.py      # Export engines
│   │       ├── gemini_engine.py # Google GenAI SDK (Gemini 2.5 Flash / Tool Calling)
│   │       ├── ollama_engine.py # Local LLM Engine (qwen2.5-coder:7b)
│   │       └── mock_engine.py   # High-speed Simulation Engine สำหรับ Offline Benchmark
│   │
│   ├── test_sets.py             # ชุดคำถามทดสอบมาตรฐาน (Benchmark Test Set 10 ข้อ)
│   └── seed_db.py               # สคริปต์สร้างข้อมูลจำลอง SQLite (โหมด Offline Dev)
│
├── mcp_server/                  # 🔌 ระบบ MCP Server แยก Tool อิสระสำหรับ AI อื่น
│   ├── server.py                # จุดรัน FastMCP Server (stdio transport)
│   ├── tools/                   # Catalog, Schema, Query Tools
│   └── ...
│
└── tests/                       # 🧪 Automated Test Suite (29 Tests ผ่าน 100%)
    ├── test_agent.py            # ReAct Agent, Self-Correction & Privacy Guard Tests (24 ข้อ)
    ├── test_api.py              # FastAPI REST Endpoints & SSE Streaming Tests (5 ข้อ)
    └── test_query.py            # Benchmark Runner สรุปผลลัพธ์คำถามเดี่ยวและชุดทดสอบ
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

ระบบมีชุด Automated Unit Test ครอบคลุมการทำงานทั้งระบบ **24 การทดสอบ**:
```bash
python -m pytest tests/test_agent.py -v
```
**ผลการทดสอบผ่านครบ 100% (24/24 PASSED):**
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
=======
# custom-ai-agent
>>>>>>> bfc9e80df71ced6eb9446275ab62740e244ca277
