# 🧪 Natural Language to SQL Agent (PoC & Experimental Demo)

> ⚠️ **คำชี้แจง (Disclaimer):**  
> โปรเจกต์นี้จัดทำขึ้นเป็น **การทดลอง / พิสูจน์แนวคิด (Proof of Concept - PoC)** เพื่อศึกษาความเป็นไปได้ในการใช้ **AI Agent (ReAct Loop)** ร่วมกับ LLM ในการแปลงคำถามภาษาไทยเป็นคำสั่ง SQL สำหรับวิเคราะห์ข้อมูล E-Commerce **ยังไม่ใช่ระบบที่พร้อมใช้งานบน Production** ความแม่นยำของคำตอบและ SQL ที่สร้างขึ้นอาจมีความคลาดเคลื่อนขึ้นอยู่กับความสามารถของโมเดลภาษาและความซับซ้อนของคำถาม

---

## 📌 ที่มาและเป้าหมายของโปรเจกต์ (Overview)

ในการดึงข้อมูลหรือทำรายงานสรุป มักต้องอาศัยผู้ที่เข้าใจภาษา SQL และโครงสร้างตารางข้อมูล โปรเจกต์นี้จึงทดลองสร้าง **Data Agent** ต้นแบบ ที่รับคำถามเป็นภาษาไทย แล้วลองให้ Agent ทำหน้าที่:
1. ค้นหา Schema และตารางที่น่าจะเกี่ยวข้อง
2. เขียนคำสั่ง SQL (`SELECT`) ขึ้นมา
3. ตรวจสอบความปลอดภัยเบื้องต้น (คัดกรองคำสั่งแก้ไขข้อมูล)
4. ทดลองรันคำสั่ง และลองแก้คำสั่งเอง (Self-Correction) หากเกิด Error
5. นำตัวเลขที่ได้มาสรุปเป็นภาษาไทยเบื้องต้น พร้อมส่งออกเป็นไฟล์ Excel

---

## ⚙️ สถาปัตยกรรมและการทำงาน (Workflow)

กระบวนการทำงานหลักของตัว Agent ใช้แนวคิด ReAct (Thought -> Action -> Observation):

```text
[ ผู้ใช้ส่งคำถามภาษาไทย ]
          │
          ▼
[ 1. Analyze & Inspect Schema ]
  Agent เลือกตารางที่เกี่ยวข้อง และเรียกดูคอลัมน์จาก Database จริง
          │
          ▼
[ 2. Generate SQL & Safety Validation ]
  สร้างคำสั่ง SELECT และตรวจสอบผ่าน AST Validator (SQLGlot)
  *บล็อกคำสั่งกลุ่ม INSERT, UPDATE, DELETE, DROP, ALTER
          │
          ▼
[ 3. Execute & Self-Correction ]
  รันคำสั่งกับฐานข้อมูล (MySQL / TiDB / SQLite)
  *หากเกิดข้อผิดพลาดจากไวยากรณ์หรือชื่อฟิลด์ Agent จะพยายามปรับแก้ SQL แล้วลองใหม่
          │
          ▼
[ 4. Output Generation ]
  - แสดงผลตารางข้อมูลและ SQL ที่ใช้จริง
  - สรุปภาพรวมและข้อสังเกตเบื้องต้น (Executive Summary & Insights)
  - สร้างไฟล์ .xlsx (Multi-sheet) พร้อมจัดรูปแบบตาราง
```

---

## 🛠️ ความสามารถที่มีใน Demo ปัจจุบัน (Current Features)

- **Natural Language to SQL:** รองรับการตั้งคำถามภาษาไทยพื้นฐานเกี่ยวกับยอดขาย สินค้า ลูกค้า และสต็อก
- **Basic Safety Filter:** มีระบบตรวจจับ Abstract Syntax Tree (AST) ด้วย `sqlglot` เพื่อป้องกันการยิงคำสั่งประเภท Data Manipulation หรือ DDL
- **Self-Healing Loop (เบื้องต้น):** หากฐานข้อมูลคืนค่า Error เช่น หาคอลัมน์ไม่เจอ Agent จะนำ Error message กลับไปปรับปรุงคำสั่งใหม่
- **Excel Auto-Export:** ส่งออกผลลัพธ์เป็นไฟล์ `.xlsx` (จัดสไตล์และแบ่ง Sheet ข้อมูล / ข้อมูลสรุป)
- **Multi-Engine Support:** มีโค้ดรองรับเชื่อมต่อ Provider ต่างๆ:
  - NVIDIA API (OpenAI-compatible)
  - Google Gemini API
  - Local Ollama
  - Mock Engine (สำหรับทดสอบ Unit Test)
- **Web Interface:** มีหน้าจอทดลองใช้งานผ่าน Streamlit (`streamlit_app.py`) และมี CLI (`cli.py`)

---

## ⚠️ ข้อจำกัดและความเป็นจริงของระบบ (Known Limitations)

เพื่อให้เข้าใจตรงกันตามความเป็นจริง Demo นี้ยังมีข้อจำกัดที่ควรทราบ:

1. **ความถูกต้องของ SQL ไม่ใช่ 100% (Hallucination Risk):**
   - คำถามที่มีเงื่อนไขธุรกิจซับซ้อน มีการคำนวณหลายชั้น หรือคำถามที่กำกวม LLM อาจตีความผิด หรือสร้างคำสั่ง SQL ที่รันผ่านแต่ผลลัพธ์ไม่ตรงกับความเป็นจริง (False Logic)
2. **การป้องกันความปลอดภัยเป็นเพียงระดับ Application:**
   - แม้จะมี AST Validator สกัดกั้นคำสั่งอันตราย แต่ในทางปฏิบัติยังจำเป็นต้องจำกัดสิทธิ์ที่ตัว Database User ให้เป็น **Read-Only** อย่างแท้จริง ห้ามพึ่งพาการตรวจเช็คของ AI เพียงอย่างเดียว
3. **ประสิทธิภาพและ Latency:**
   - การทำงานแบบ ReAct มีหลายขั้นตอน (Inspect -> Generate -> Run -> Interpret) ส่งผลให้ใช้เวลาในการประมวลผลต่อหนึ่งคำถามพอสมควร และมีค่าใช้จ่าย Token ของ LLM
4. **ความแม่นยำของการสรุปผล (Narrative):**
   - ข้อความสรุปเชิงธุรกิจเป็นการวิเคราะห์ของโมเดลตามตัวเลขที่ได้มา ไม่สามารถนำไปใช้ตัดสินใจทางธุรกิจระดับวิกฤตได้โดยปราศจากการตรวจสอบซ้ำ (Human-in-the-loop)

---

## 💻 วิธีการติดตั้งและรัน Demo (Getting Started)

### 1. สภาพแวดล้อมที่รองรับ
- Python 3.10 หรือใหม่กว่า
- ฐานข้อมูล MySQL / TiDB / SQLite (ในโฟลเดอร์ `data/` มีฐานข้อมูลจำลอง `ecommerce.db` สำหรับทดสอบ)

### 2. ติดตั้ง Dependencies
```bash
pip install -r requirements.txt
```

### 3. ตั้งค่าสภาพแวดล้อม (.env)
คัดลอกไฟล์ `.env.example` เป็น `.env` และกำหนดค่าเชื่อมต่อ:
```bash
cp .env.example .env
```
กำหนดค่าที่จำเป็น เช่น:
```env
# เลือก Provider ที่ต้องการใช้: nvidia, gemini, หรือ ollama
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_api_key_here

# หรือหากใช้ NVIDIA
# LLM_PROVIDER=nvidia
# NVIDIA_API_KEY=your_nvidia_api_key_here
# NVIDIA_MODEL=nvidia/nemotron-3.5-lightning-30b-a3b

# ข้อมูลเชื่อมต่อ Database (หรือชี้ไปยัง SQLite สำหรับทดสอบในเครื่อง)
DB_HOST=127.0.0.1
DB_PORT=3306
DB_NAME=ecommerce_db
DB_USER=ecommerce_reader
DB_PASSWORD=your_password
```

### 4. รันระบบ

**รันผ่าน Streamlit Web UI:**
```bash
python -m streamlit run streamlit_app.py
```
เข้าใช้งานผ่านเบราว์เซอร์ที่ `http://localhost:8501`

**หรือรันผ่าน Command Line (CLI):**
```bash
python cli.py
```

---

## 💡 ตัวอย่างคำถามสำหรับทดสอบ (Test Prompts)

คำถามพื้นฐานที่โครงสร้างข้อมูลรองรับและเหมาะสำหรับทดสอบ Concept:
- *"สินค้า 5 อันดับแรกที่ราคาแพงที่สุดมีอะไรบ้าง"*
- *"มีสินค้าอะไรบ้างที่สต็อกในคลังเหลือน้อยกว่า 10 ชิ้น"*
- *"ขอดูข้อมูลลูกค้าทั้งหมด 10 คนแรก"*
- *"ช่วงนี้แบรนด์ไหนมียอดขายรวมสูงสุด 3 อันดับแรก"*

---

## 📁 โครงสร้างโปรเจกต์โดยย่อ (Project Structure)

```text
Agent_natural_langauge_to_sql/
├── data/                    # ข้อมูลจำลอง (SQLite, SQL DDL Script)
├── src/
│   ├── agent/               # ลอจิก Agent, Prompt, และตัวเชื่อมต่อ LLM แต่ละค่าย
│   ├── config/              # จัดการ Environment Variables และการตั้งค่า
│   ├── database/            # เชื่อมต่อ Database และดึง Schema
│   ├── services/            # Service ย่อย (Agent Orchestrator, Excel Generator, AST Guard)
│   └── validator/           # ตัวตรวจทานความปลอดภัยของ SQL (AST Validator)
├── tests/                   # ชุดทดสอบ Unit/Integration Tests
├── cli.py                   # ตัวรันแบบ CLI
├── streamlit_app.py         # ตัวรันแบบ Web Dashboard (Streamlit)
├── requirements.txt         # รายการแพ็กเกจที่ใช้งาน
└── README.md
```

---

## 📝 บันทึกการทดลองและก้าวต่อไป (Future Explorations)
- [ ] พัฒนา Few-shot Examples และ Schema Linking ให้แม่นยำขึ้นสำหรับคำถามที่มีการ JOIN หลายตาราง
- [ ] เพิ่มระบบยืนยันความถูกต้องของตัวเลข (Evaluation Benchmark) เทียบกับ Ground Truth SQL
- [ ] ปรับปรุงการจัดการ Context Window เมื่อฐานข้อมูลมีจำนวนตารางมากเกินไป (Schema Pruning)
