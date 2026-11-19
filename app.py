"""
Streamlit Web Dashboard for E-Commerce AI Data Analytics Agent
Executive Business Intelligence, Multi-Worksheet Excel Generation, and ReAct Reasoning.
"""

import streamlit as st
import json
from pathlib import Path
import pandas as pd
import importlib

import src.config
import src.config.settings
import src.database
import src.prompts.templates
import src.prompts
import src.services.excel_service
import src.services.agent_service
import src.services.llm.nvidia_provider
import src.services.coreference_service
import src.agent
import src.test_sets

# Auto-reload project modules on Streamlit script re-run
importlib.reload(src.config.settings)
importlib.reload(src.config)
importlib.reload(src.database)
importlib.reload(src.prompts.templates)
importlib.reload(src.prompts)
importlib.reload(src.services.excel_service)
importlib.reload(src.services.agent_service)
importlib.reload(src.services.llm.nvidia_provider)
importlib.reload(src.services.coreference_service)
importlib.reload(src.agent)
importlib.reload(src.test_sets)

from src.config import Config
from src.database import DatabaseConnection
from src.agent import DatabaseAgent, AgentStep
from src.test_sets import TEST_SET

# ----------------- PAGE CONFIG -----------------
st.set_page_config(
    page_title="AI Data Analytics & BI Agent",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ----------------- MODERN CUSTOM CSS -----------------
st.markdown("""
<style>
    /* Global modern typography and dark theme styling */
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    
    .hero-container {
        background-color: #1e293b;
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 22px 26px;
        margin-bottom: 20px;
    }
    
    .hero-title {
        font-size: 1.75rem;
        font-weight: 700;
        color: #f8fafc;
        margin-bottom: 6px;
        display: flex;
        align-items: center;
        gap: 10px;
    }
    
    .hero-subtitle {
        color: #94a3b8;
        font-size: 0.95rem;
        line-height: 1.5;
    }
    
    .stat-card {
        background: #1e293b;
        border: 1px solid #334155;
        border-radius: 10px;
        padding: 12px 16px;
        text-align: center;
    }
    
    .stat-label {
        font-size: 0.78rem;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        font-weight: 600;
        margin-bottom: 4px;
    }
    
    .stat-value {
        font-size: 1.05rem;
        font-weight: 700;
        color: #f8fafc;
    }
    
    .excel-download-card {
        background-color: #1e293b;
        border: 1px solid #334155;
        border-left: 4px solid #0284c7;
        border-radius: 8px;
        padding: 14px 18px;
        margin: 12px 0 14px 0;
    }
    
    .excel-card-title {
        font-weight: 600;
        font-size: 0.98rem;
        color: #f8fafc;
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 4px;
    }
    
    .excel-card-desc {
        color: #94a3b8;
        font-size: 0.85rem;
        margin-bottom: 6px;
    }
    
    .excel-badge {
        display: inline-block;
        font-family: 'Consolas', 'Courier New', monospace;
        background: #0f172a;
        border: 1px solid #334155;
        border-radius: 4px;
        padding: 3px 8px;
        font-size: 0.82rem;
        color: #38bdf8;
    }
</style>
""", unsafe_allow_html=True)

# ----------------- SESSION STATE -----------------
if "messages" not in st.session_state:
    st.session_state.messages = []
if "db" not in st.session_state:
    st.session_state.db = DatabaseConnection()
if "selected_provider" not in st.session_state:
    st.session_state.selected_provider = getattr(Config, "LLM_PROVIDER", "nvidia")

db = st.session_state.db

# ----------------- SIDEBAR -----------------
with st.sidebar:
    st.title("⚙️ การตั้งค่าระบบ (Settings)")
    
    # Database connection section
    st.subheader("ฐานข้อมูล (Database)")
    is_connected, db_msg = db.test_connection()
    if is_connected:
        st.success(f"✅ {db_msg}")
    else:
        st.error(f"❌ {db_msg}")
        st.info("ตรวจสอบค่าการเชื่อมต่อในไฟล์ `.env`")

    st.divider()

    # LLM Provider selection
    st.subheader("สมองกล AI (LLM Provider)")
    provider_choice = st.radio(
        "เลือก Engine ในการประมวลผล:",
        ["nvidia", "gemini", "ollama"],
        index=0,
        format_func=lambda x: {
            "nvidia": "⚡ NVIDIA Cloud (Nemotron-3.5-Lightning แนะนำ 🌟)",
            "gemini": "☁️ Google Gemini (Cloud + Dynamic Fallback)",
            "ollama": "🖥️ Local Ollama (Qwen2.5-Coder:7b ReAct)"
        }.get(x, x),
        key="selected_provider"
    )

    if provider_choice == "nvidia":
        model_choice = getattr(Config, "NVIDIA_MODEL", "nvidia/nemotron-3.5-lightning-30b-a3b")
        api_key_input = getattr(Config, "NVIDIA_API_KEY", "")
    elif provider_choice == "gemini":
        model_choice = getattr(Config, "GEMINI_MODEL", "gemini-3.5-flash")
        api_key_input = getattr(Config, "GEMINI_API_KEY", "")
    else:
        model_choice = getattr(Config, "OLLAMA_MODEL", "qwen2.5-coder:7b")
        api_key_input = None

    st.info(f"🤖 **โมเดลที่ใช้งานอยู่:**\n\n`{model_choice}`")

    st.divider()
    if st.button("🗑️ ล้างประวัติการแชต (Clear Chat)", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# ----------------- HERO HEADER -----------------
st.markdown("""
<div class="hero-container">
    <div class="hero-title">
        <span>📊 E-Commerce AI Data Analytics & BI Agent</span>
    </div>
    <div class="hero-subtitle">
        ระบบผู้ช่วยวิเคราะห์ข้อมูลธุรกิจอัจฉริยะสำหรับฐานข้อมูล <strong>ecommerce_db</strong><br/>
        แปลงภาษาธรรมชาติ (TH) ➔ สรุปบทวิเคราะห์ผู้บริหาร • สร้างรายงาน Excel หลายแท็บบันทึกตรงลง Desktop • ป้องกันความปลอดภัย 100% ด้วย AST Read-Only Guard
    </div>
</div>
""", unsafe_allow_html=True)

# ----------------- EXECUTIVE KPI METRIC CARDS -----------------
kpi_col1, kpi_col2, kpi_col3, kpi_col4 = st.columns(4)

with kpi_col1:
    st.markdown("""
    <div class="stat-card">
        <div class="stat-label">🗄️ ฐานข้อมูลหลัก</div>
        <div class="stat-value">ecommerce_db</div>
    </div>
    """, unsafe_allow_html=True)

with kpi_col2:
    st.markdown(f"""
    <div class="stat-card">
        <div class="stat-label">🤖 AI Engine</div>
        <div class="stat-value">{'NVIDIA Cloud' if provider_choice == 'nvidia' else ('Google Gemini' if provider_choice == 'gemini' else 'Local Ollama')}</div>
    </div>
    """, unsafe_allow_html=True)

with kpi_col3:
    st.markdown("""
    <div class="stat-card">
        <div class="stat-label">🛡️ SQL Security</div>
        <div class="stat-value">AST Read-Only Guard</div>
    </div>
    """, unsafe_allow_html=True)

with kpi_col4:
    st.markdown("""
    <div class="stat-card">
        <div class="stat-label">📑 BI Export Tool</div>
        <div class="stat-value">Multi-Sheet Excel</div>
    </div>
    """, unsafe_allow_html=True)

st.write("")

# ----------------- BUSINESS DOMAINS ACCORDION -----------------
with st.expander("🧭 ขอบเขตข้อมูลเชิงธุรกิจที่ระบบวิเคราะห์ได้ (Business Domains - ครอบคลุม 31 ตาราง)", expanded=False):
    d1, d2, d3, d4 = st.columns(4)
    with d1:
        st.markdown("""
        **🛍️ ยอดขาย & คำสั่งซื้อ**
        * ยอดขายรายวัน/เดือน/ปี
        * สินค้าขายดี & การจัดอันดับ
        * สถานะออเดอร์ & ประวัติการสั่งซื้อ
        """)
    with d2:
        st.markdown("""
        **📦 สินค้า & สต็อกโกดัง**
        * รายละเอียดและหมวดหมู่สินค้า
        * ปริมาณสต็อกคงเหลือแยกโกดัง
        * สเปกและข้อมูลแบรนด์สินค้า
        """)
    with d3:
        st.markdown("""
        **👥 ข้อมูลลูกค้า & พฤติกรรม**
        * โปรไฟล์ลูกค้า & ช่องทางติดต่อ
        * ลูกค้า VIP ยอดสั่งซื้อสูงสุด
        * ที่อยู่และประเทศของลูกค้า
        """)
    with d4:
        st.markdown("""
        **⭐ ความพึงพอใจ & การคืน**
        * คะแนนรีวิวสินค้า (1-5 ดาว)
        * อัตราและเหตุผลการคืนสินค้า
        * คูปองส่วนลดและการชำระเงิน
        """)

# ----------------- QUICK PROMPTS CHIPS -----------------
st.write("💡 **คำถามวิเคราะห์ธุรกิจยอดนิยม (คลิกเพื่อทดสอบทันที):**")
btn1, btn2, btn3, btn4, btn5 = st.columns(5)
quick_prompt = None

if btn1.button("🏆 5 แบรนด์ยอดขายสูงสุด", use_container_width=True):
    quick_prompt = "ช่วงนี้สินค้าแบรนด์ไหนขายดีที่สุด 5 อันดับแรก และมียอดขายรวมเท่าไหร่"

if btn2.button("👥 ข้อมูลลูกค้าทั้งหมด", use_container_width=True):
    quick_prompt = "ขอข้อมูลลูกค้าทั้งหมดหน่อย"

if btn3.button("🛍️ ลูกค้าแต่ละคนซื้ออะไร", use_container_width=True):
    quick_prompt = "ลูกค้าแต่ละคน ซื้อของอะไรบ้าง"

if btn4.button("📊 สรุปแบรนด์ + ลูกค้า (Excel)", use_container_width=True):
    quick_prompt = "สรุปยอดขาย 5 แบรนด์ดัง และแสดงลูกค้าที่มียอดซื้อสูงสุด 5 คนแรก พร้อมทำรายงาน Excel ให้ด้วย"

if btn5.button("🏢 สต็อกคงเหลือแยกโกดัง", use_container_width=True):
    quick_prompt = "ตอนนี้แต่ละโกดังมีของเหลืออยู่ทั้งหมดกี่ชิ้น สรุปยอดรวมแยกตามคลังให้หน่อย"

# ----------------- BENCHMARK SET EXPANDER -----------------
with st.expander("🧪 ชุดคำถามทดสอบมาตรฐาน (Benchmark Test Set 10 ข้อ)", expanded=False):
    selected_bench = st.selectbox(
        "เลือกคำถามทดสอบมาตรฐาน:",
        ["-- กรุณาเลือกคำถาม --"] + [f"ข้อ {i}: {q}" for i, q in enumerate(TEST_SET, 1)],
        key="bench_test_select"
    )
    if st.button("🚀 รันคำถามทดสอบนี้", use_container_width=False):
        if selected_bench != "-- กรุณาเลือกคำถาม --":
            quick_prompt = selected_bench.split(": ", 1)[1]

st.divider()

# ----------------- CHAT HISTORY DISPLAY -----------------
for msg in st.session_state.messages:
    avatar = "🧑‍💻" if msg["role"] == "user" else "🤖"
    with st.chat_message(msg["role"], avatar=avatar):
        if msg.get("expanded_question"):
            st.caption(f"🔗 **บริบทคำถามต่อเนื่อง:** *\"{msg['expanded_question']}\"*")
        
        # Display Final Answer Text
        st.markdown(msg["content"])
        
        # Excel Report Download Card
        if msg.get("excel_file_path"):
            fname = msg.get("excel_file_name") or Path(msg["excel_file_path"]).name
            st.markdown(f"""
            <div class="excel-download-card">
                <div class="excel-card-title">📑 รายงาน Excel (.xlsx) พร้อมดาวน์โหลด</div>
                <div class="excel-card-desc">จัดเตรียมข้อมูลและแยก Worksheets ให้เรียบร้อยแล้ว</div>
                <div class="excel-badge">📁 {fname}</div>
            </div>
            """, unsafe_allow_html=True)
            try:
                excel_bytes = Path(msg["excel_file_path"]).read_bytes()
                st.download_button(
                    label=f"📥 คลิกเพื่อดาวน์โหลดไฟล์ ({fname})",
                    data=excel_bytes,
                    file_name=fname,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key=f"dl_hist_{hash(msg['excel_file_path'])}"
                )
            except Exception:
                pass

        # SQL Code Expander
        if "sql" in msg and msg["sql"]:
            with st.expander("📄 คำสั่ง SQL ที่รันบนฐานข้อมูล"):
                st.code(msg["sql"], language="sql")

        # Visual Table & Chart (Omitted if Excel was generated)
        if "rows" in msg and msg["rows"] and not msg.get("excel_file_path"):
            df = pd.DataFrame(msg["rows"])
            with st.expander(f"📊 ดูตารางข้อมูล ({len(df)} แถว)", expanded=False):
                st.dataframe(df, use_container_width=True)
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 ดาวน์โหลดเป็น CSV",
                    data=csv,
                    file_name="query_result.csv",
                    mime="text/csv",
                    key=f"dl_csv_{hash(msg.get('sql', ''))}"
                )
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

# ----------------- CHAT INPUT & EXECUTION -----------------
user_input = st.chat_input("พิมพ์คำถามทางธุรกิจ เช่น 'ช่วงนี้สินค้าแบรนด์ไหนขายดีที่สุด'...")
prompt_to_run = quick_prompt or user_input

if prompt_to_run:
    st.session_state.messages.append({"role": "user", "content": prompt_to_run})
    with st.chat_message("user", avatar="🧑‍💻"):
        st.markdown(prompt_to_run)

    agent = DatabaseAgent(
        db=db,
        provider=provider_choice,
        api_key=api_key_input if api_key_input else None,
        model_name=model_choice
    )

    with st.chat_message("assistant", avatar="🤖"):
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
                    st.error(f"❌ **Error:** {step.observation}")
                    st.caption("🔄 *Agent กำลังวิเคราะห์ Error และเข้าสู่วงจร Self-Correction...*")
                else:
                    if step.tool_name == "execute_sql" and isinstance(step.observation, list):
                        st.success(f"👁️ **Observation:** ได้รับข้อมูล {len(step.observation)} รายการจาก `ecommerce_db`")
                    else:
                        obs_str = str(step.observation)
                        if len(obs_str) > 300:
                            obs_str = obs_str[:300] + "... [truncated]"
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

        # Show Excel Download Card
        if result.excel_file_path:
            fname = result.excel_file_name or Path(result.excel_file_path).name
            st.markdown(f"""
            <div class="excel-download-card">
                <div class="excel-card-title">📑 รายงาน Excel (.xlsx) พร้อมดาวน์โหลด</div>
                <div class="excel-card-desc">จัดเตรียมข้อมูลและแยก Worksheets ให้เรียบร้อยแล้ว</div>
                <div class="excel-badge">📁 {fname}</div>
            </div>
            """, unsafe_allow_html=True)
            try:
                excel_bytes = Path(result.excel_file_path).read_bytes()
                st.download_button(
                    label=f"📥 คลิกเพื่อดาวน์โหลดไฟล์ ({fname})",
                    data=excel_bytes,
                    file_name=fname,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key=f"dl_now_{hash(result.excel_file_path)}"
                )
            except Exception:
                pass

        # Show SQL Query
        if result.last_executed_sql:
            with st.expander("📄 คำสั่ง SQL ที่ผ่านการตรวจสอบ AST Safety"):
                st.code(result.last_executed_sql, language="sql")

        # Show Data Table & Chart (Omitted if an Excel report was created)
        if result.last_query_result and not result.excel_file_path:
            df = pd.DataFrame(result.last_query_result)
            with st.expander(f"📊 ผลลัพธ์ข้อมูลดิบจากฐานข้อมูล ({len(df)} แถว)", expanded=True):
                st.dataframe(df, use_container_width=True)
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
            "excel_file_path": result.excel_file_path,
            "excel_file_name": result.excel_file_name,
            "excel_sheets": result.excel_sheets,
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
