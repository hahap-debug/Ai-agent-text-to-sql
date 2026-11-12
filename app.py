"""
Streamlit Web Dashboard for E-Commerce AI Data Analytics Agent
Interactive ReAct trace visualization, dynamic schema explorer, visual charts, and executive reports.
"""

import streamlit as st
import json
import pandas as pd
import importlib
import src.config
import src.database
import src.prompts
import src.agent
import src.test_sets

# Auto-reload project modules on Streamlit script re-run
importlib.reload(src.config)
importlib.reload(src.database)
importlib.reload(src.prompts)
importlib.reload(src.agent)
importlib.reload(src.test_sets)

from src.config import Config
from src.database import DatabaseConnection
from src.agent import DatabaseAgent, AgentStep
from src.test_sets import TEST_SET

# Page Configuration
st.set_page_config(
    page_title="AI Data Analytics Agent",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for styling
st.markdown("""
<style>
    .report-card {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 20px;
        margin-top: 15px;
        margin-bottom: 20px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2);
    }
    .metric-badge {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 0.85rem;
        font-weight: 600;
        margin-right: 8px;
    }
    .badge-success { background-color: #065f46; color: #6ee7b7; }
    .badge-info { background-color: #1e3a8a; color: #93c5fd; }
    .badge-warn { background-color: #854d0e; color: #fde047; }
</style>
""", unsafe_allow_html=True)

# Initialize Session State
if "messages" not in st.session_state:
    st.session_state.messages = []
if "db" not in st.session_state:
    st.session_state.db = DatabaseConnection()
if "selected_provider" not in st.session_state:
    st.session_state.selected_provider = "ollama"

db = st.session_state.db

# ----------------- SIDEBAR -----------------
with st.sidebar:
    st.title("⚙️ การตั้งค่าระบบ (Settings)")
    
    # DB Status
    st.subheader("ฐานข้อมูล (Database)")
    is_connected, db_msg = db.test_connection()
    if is_connected:
        st.success(f"✅ {db_msg}")
    else:
        st.error(f"❌ {db_msg}")
        st.info("ตรวจสอบค่าการเชื่อมต่อใน `.env`")

    st.divider()

    # LLM Settings
    st.subheader("สมองกล AI (LLM Provider)")
    provider_choice = st.radio(
        "เลือก Engine ในการประมวลผล:",
        ["ollama", "gemini"],
        index=0,
        format_func=lambda x: {
            "ollama": "🖥️ Local Ollama (qwen2.5-coder:7b)",
            "gemini": "☁️ Google Gemini (gemini-3.5-flash)"
        }.get(x, x),
        key="selected_provider"
    )

    if provider_choice == "ollama":
        model_choice = "qwen2.5-coder:7b"
        api_key_input = None
    else:
        model_choice = "gemini-3.5-flash"
        api_key_input = Config.GEMINI_API_KEY

    # Current Active Model indicator
    st.info(f"🤖 **โมเดลที่ใช้งานอยู่ (Active Model):**\n\n`{model_choice}`")

    st.divider()
    if st.button("🗑️ ล้างประวัติการแชต (Clear Chat)"):
        st.session_state.messages = []
        st.rerun()

# ----------------- MAIN CONTENT -----------------
st.title("🤖 E-Commerce AI Data Analytics Agent")
st.markdown("""
ระบบเอเจนต์วิเคราะห์ข้อมูลอัจฉริยะสำหรับฐานข้อมูล **`ecommerce_db`**  
ขับเคลื่อนด้วย **ReAct Reasoning (Thought ➔ Action ➔ Observation)** • **AST-Safe Read-Only Guard** • **Self-Correction Loop**
""")

# Quick Stat Badges
# ----------------- MAIN CONTENT LAYOUT -----------------
st.title("🤖 E-Commerce AI Data Analytics Agent")
st.markdown("""
ระบบเอเจนต์วิเคราะห์ข้อมูลอัจฉริยะสำหรับฐานข้อมูล **`ecommerce_db`**
ขับเคลื่อนด้วย **ReAct Reasoning** (Thought ➔ Action ➔ Observation) • **AST‑Safe Read‑Only Guard** • **Self‑Correction Loop**
""")

# สถิติสำคัญ
col_m1, col_m2 = st.columns(2)
with col_m1:
    st.metric(label="ฐานข้อมูล", value="ecommerce_db", delta="Active (MySQL)")
with col_m2:
    st.metric(label="โหมดการทำงาน", value=provider_choice.upper(), delta=model_choice)

# ขอบเขต Business Domain ที่สามารถถามได้
with st.expander("🧭 ขอบเขตข้อมูลเชิงธุรกิจที่ระบบสามารถตอบได้ (Business Domains - ครอบคลุม 31 ตาราง)", expanded=True):
    d_col1, d_col2, d_col3 = st.columns(3)
    with d_col1:
        st.markdown("""
        **🛍️ ยอดขาย & คำสั่งซื้อ**
        * มูลค่ายอดขายรวม, สินค้าขายดี
        * สถานะออเดอร์, ประวัติการซื้อ
        
        **👥 ข้อมูลลูกค้า**
        * รายชื่อลูกค้า, ที่อยู่/ประเทศ
        * พฤติกรรมการสั่งซื้อ, ลูกค้าประจำ
        
        **🏢 ซัพพลายเออร์ & ผู้ผลิต**
        * ข้อมูลคู่ค้า, ผู้จัดหาสินค้า
        """)
    with d_col2:
        st.markdown("""
        **📦 สินค้า & สต็อก**
        * สเปกสินค้า, รูปภาพ, แบรนด์, หมวดหมู่
        * ระดับสต็อกคงเหลือในแต่ละคลัง
        
        **🚚 ส่งของ & จัดส่ง**
        * ผู้ให้บริการขนส่ง, เลข Tracking
        * วิธีการจัดส่ง, ค่าจัดส่ง
        
        **🛒 ตะกร้าสินค้า & Wishlist**
        * สินค้าที่ค้างในตะกร้า, สินค้าที่อยากได้
        """)
    with d_col3:
        st.markdown("""
        **⭐ รีวิว & ความพึงพอใจ**
        * คะแนนดาว (1-5 ดาว), ข้อเสนอแนะ
        
        **🔄 การคืนสินค้า & เคลม**
        * สินค้าที่ถูกคืน, เหตุผลการยกเลิก
        
        **🎟️ คูปอง, ภาษี & การเงิน**
        * การใช้ส่วนลด, ช่องทางชำระเงิน, อัตราภาษี
        
        **💬 ฝ่ายบริการลูกค้า**
        * ตั๋วแจ้งปัญหา, ข้อความประสานงาน
        """)

st.write("")

# Quick prompt chips
st.write("💡 **ตัวอย่างคำถามวิเคราะห์ธุรกิจยอดนิยม (คลิกเพื่อทดสอบทันที):**")
btn_col1, btn_col2, btn_col3, btn_col4 = st.columns(4)
quick_prompt = None

if btn_col1.button("👥 ข้อมูลลูกค้าทั้งหมด", use_container_width=True):
    quick_prompt = "ขอข้อมูลลูกค้าทั้งหมดหน่อย"

if btn_col2.button("🏆 แบรนด์ยอดขายสูงสุด", use_container_width=True):
    quick_prompt = "ช่วงนี้สินค้าแบรนด์ไหนขายดีที่สุด 5 อันดับแรก และมียอดขายรวมเท่าไหร่"

if btn_col3.button("🛍️ ลูกค้าแต่ละคนซื้ออะไร", use_container_width=True):
    quick_prompt = "ลูกค้าแต่ละคน ซื้อของอะไรบ้าง"

if btn_col4.button("🌍 ซื้ออะไร & มาจากประเทศไหน", use_container_width=True):
    quick_prompt = "ลูกค้าแต่ละคน ซื้อของอะไรบ้าง และมาจากประเทศไหน"

# Benchmark Test Set Expander
with st.expander("🧪 ชุดคำถามทดสอบระบบมาตรฐาน (Benchmark Test Set 10 ข้อ)", expanded=False):
    st.write("เลือกคำถามทดสอบความแม่นยำของ ReAct Agent ตามสเปก:")
    selected_bench = st.selectbox(
        "เลือกคำถามทดสอบ:",
        ["-- กรุณาเลือกคำถาม --"] + [f"ข้อ {i}: {q}" for i, q in enumerate(TEST_SET, 1)],
        key="bench_test_select"
    )
    if st.button("🚀 ทดสอบคำถามนี้ทันที", use_container_width=False):
        if selected_bench != "-- กรุณาเลือกคำถาม --":
            quick_prompt = selected_bench.split(": ", 1)[1]

# Display chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg.get("expanded_question"):
            st.caption(f"🔗 **บริบทคำถามต่อเนื่อง:** *\"{msg['expanded_question']}\"*")
        st.markdown(msg["content"])
        
        # SQL Code Expander
        if "sql" in msg and msg["sql"]:
            with st.expander("📄 คำสั่ง SQL ที่รันบน MySQL"):
                st.code(msg["sql"], language="sql")

        # Visual Table & Chart
        if "rows" in msg and msg["rows"]:
            df = pd.DataFrame(msg["rows"])
            with st.expander(f"📊 ดูตารางข้อมูล ({len(df)} แถว)", expanded=False):
                st.dataframe(df, use_container_width=True)
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 ดาวน์โหลดข้อมูลเป็น CSV",
                    data=csv,
                    file_name="query_result.csv",
                    mime="text/csv",
                    key=f"dl_{hash(msg.get('sql', ''))}"
                )
                
                # Auto-Chart if applicable
                text_cols = [c for c in df.columns if df[c].dtype == 'object']
                num_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
                if text_cols and num_cols:
                    st.bar_chart(df.set_index(text_cols[0])[num_cols[0]])

        # ReAct Trace Expander
        if "steps" in msg and msg["steps"]:
            with st.expander(f"🔍 วงจรคิด ReAct และการแก้ปัญหา ({len(msg['steps'])} ขั้นตอน)"):
                for s in msg["steps"]:
                    st.markdown(f"**Step {s['step_number']}**")
                    if s.get("thought"):
                        st.markdown(f"🧠 *Thought:* {s['thought']}")
                    if s.get("tool_name"):
                        st.markdown(f"⚡ *Action:* `{s['tool_name']}` ({json.dumps(s.get('parameters', {}), ensure_ascii=False)})")
                    if s.get("is_error"):
                        st.error(f"❌ *Observation (Error Triggered):* {s.get('observation')}")
                        st.caption("🔄 *Agent กำลังวิเคราะห์ Error และเข้าสู่วงจร Self-Correction เพื่อแก้ปัญหา...*")
                    else:
                        st.info(f"👁️ *Observation:* {s.get('observation')}")
                    st.divider()

# Input box
user_input = st.chat_input("พิมพ์คำถามทางธุรกิจ เช่น 'แบรนด์ไหนขายดีที่สุด'...")
prompt_to_run = quick_prompt or user_input

if prompt_to_run:
    # Append user question
    st.session_state.messages.append({"role": "user", "content": prompt_to_run})
    with st.chat_message("user"):
        st.markdown(prompt_to_run)

    # Run agent
    agent = DatabaseAgent(
        db=db,
        provider=provider_choice,
        api_key=api_key_input if api_key_input else None,
        model_name=model_choice
    )

    with st.chat_message("assistant"):
        # Real-time ReAct progress with animated spinner & status updater
        with st.status("🧠 AI Agent กำลังเริ่มประมวลผลคำถาม...", expanded=True) as status_box:
            def live_step_callback(step: AgentStep):
                tool_label = f"เครื่องมือ `{step.tool_name}`" if step.tool_name else "วิเคราะห์ข้อมูล"
                status_box.update(
                    label=f"🔄 [Step {step.step_number}] กำลังเรียก {tool_label}...",
                    state="running"
                )
                st.markdown(f"**Step {step.step_number}**")
                if step.thought:
                    st.markdown(f"🧠 **Thought:** {step.thought}")
                if step.tool_name:
                    st.markdown(f"⚡ **Action:** `{step.tool_name}` with `{json.dumps(step.parameters, ensure_ascii=False)}`")
                if step.is_error:
                    st.error(f"❌ **Error Triggered:** {step.observation}")
                    st.caption("🔄 *Agent กำลังวิเคราะห์ Error และเข้าสู่วงจร Self-Correction เพื่อแก้ปัญหา...*")
                else:
                    if step.tool_name == "execute_sql" and isinstance(step.observation, list):
                        st.success(f"👁️ **Observation:** ได้รับข้อมูล {len(step.observation)} รายการจาก `ecommerce_db`")
                    else:
                        obs_str = str(step.observation)
                        if len(obs_str) > 300: obs_str = obs_str[:300] + "... [truncated]"
                        st.info(f"👁️ **Observation:**\n\n```\n{obs_str}\n```")
                st.divider()

            result = agent.run(
                prompt_to_run,
                step_callback=live_step_callback,
                chat_history=st.session_state.messages[:-1] if len(st.session_state.messages) > 1 else None
            )
            
            if result.success:
                status_box.update(
                    label=f"✅ วิเคราะห์ข้อมูลสำเร็จ ({len(result.steps)} ขั้นตอน)!",
                    state="complete",
                    expanded=False
                )
            else:
                is_quota = "quota" in (result.error_message or "").lower() or "ran out of quota" in (result.final_answer or "").lower()
                status_box.update(
                    label="⚠️ Gemini API: Ran out of quota (โควตาเต็ม)" if is_quota else "⚠️ สิ้นสุดการประมวลผล",
                    state="error",
                    expanded=True
                )

        # Show SQL
        if result.last_executed_sql:
            with st.expander("📄 คำสั่ง SQL ที่ผ่านการตรวจสอบ AST Safety"):
                st.code(result.last_executed_sql, language="sql")

        # Show Data Table & Chart
        if result.last_query_result:
            df = pd.DataFrame(result.last_query_result)
            with st.expander(f"📊 ผลลัพธ์ข้อมูลดิบจากฐานข้อมูล ({len(df)} แถว)", expanded=True):
                st.dataframe(df, use_container_width=True)
                
                # Chart
                text_cols = [c for c in df.columns if df[c].dtype == 'object']
                num_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
                if text_cols and num_cols:
                    st.subheader("📈 แผนภูมิเปรียบเทียบข้อมูล")
                    st.bar_chart(df.set_index(text_cols[0])[num_cols[0]])

        # Show Final Business Report
        if result.expanded_question:
            st.caption(f"🔗 **บริบทคำถามต่อเนื่อง:** *\"{result.expanded_question}\"*")
        st.markdown(result.final_answer)

        # Record to chat history
        st.session_state.messages.append({
            "role": "assistant",
            "content": result.final_answer,
            "sql": result.last_executed_sql,
            "rows": result.last_query_result,
            "expanded_question": result.expanded_question,
            "steps": [
                {
                    "step_number": s.step_number,
                    "thought": s.thought,
                    "tool_name": s.tool_name,
                    "parameters": s.parameters,
                    "observation": str(s.observation)[:300],
                    "is_error": s.is_error
                } for s in result.steps
            ]
        })
