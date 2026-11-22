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
config_settings_module = importlib.import_module("src.config.settings")
importlib.reload(config_settings_module)
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
    st.title("🤖 โมเดล AI ที่ใช้งานได้")

    # Metadata for all available models
    models_meta = {
        "nvidia": {
            "name": "⚡ NVIDIA Cloud (แนะนำ 🌟)",
            "model_id": getattr(Config, "NVIDIA_MODEL", "nvidia/nemotron-3.5-lightning-30b-a3b"),
            "context_window": "128,000 Tokens (~128K)",
            "best_for": "คำถามวิเคราะห์ธุรกิจที่มีความซับซ้อนสูง, Multi-Table JOINs หลายตาราง, การคำนวณขั้นสูง และต้องการความเร็วในการตอบสนองแบบทันใจ",
            "api_key": getattr(Config, "NVIDIA_API_KEY", "")
        },
        "gemini": {
            "name": "☁️ Google Gemini",
            "model_id": getattr(Config, "GEMINI_MODEL", "gemini-3.5-flash"),
            "context_window": "1,000,000 Tokens (~1M)",
            "best_for": "คำถามที่มีประวัติการคุยต่อเนื่องยาว (Long Conversation), การดึง Schema จำนวนมากพร้อมกัน และงานสรุปรายงานภาษาไทย",
            "api_key": getattr(Config, "GEMINI_API_KEY", "")
        },
        # "ollama": {
        #     "name": "🖥️ Local Ollama (Offline)",
        #     "model_id": getattr(Config, "OLLAMA_MODEL", "qwen2.5-coder:7b"),
        #     "context_window": "32,768 Tokens (~32K)",
        #     "best_for": "คำถาม Text-to-SQL ทั่วไป, ใช้งานแบบ Offline ในเครื่อง 100% ไม่ต้องต่อเน็ต และข้อมูลเป็นความลับสูงสุด",
        #     "api_key": None
        # }
    }

    provider_choice = st.radio(
        "เลือกโมเดลที่ต้องการใช้งาน:",
        ["nvidia", "gemini"],  # "ollama" commented out for web UI
        index=0,
        format_func=lambda x: models_meta[x]["name"],
        key="selected_provider"
    )

    current_meta = models_meta[provider_choice]
    model_choice = current_meta["model_id"]
    api_key_input = current_meta["api_key"]

    st.markdown(f"""
    <div style="background: rgba(30, 41, 59, 0.7); border: 1px solid #334155; border-radius: 8px; padding: 12px 14px; margin: 10px 0;">
        <div style="font-size: 0.82rem; color: #94a3b8; margin-bottom: 3px;">🏷️ <b>รุ่น (Model):</b></div>
        <div style="font-family: monospace; font-size: 0.85rem; color: #38bdf8; background: #0f172a; padding: 4px 8px; border-radius: 4px; word-break: break-all;">{model_choice}</div>
        <div style="font-size: 0.82rem; color: #94a3b8; margin-top: 8px; margin-bottom: 2px;">📏 <b>Context Window:</b></div>
        <div style="font-size: 0.88rem; color: #f8fafc; font-weight: 600;">{current_meta['context_window']}</div>
        <div style="font-size: 0.82rem; color: #94a3b8; margin-top: 8px; margin-bottom: 2px;">🎯 <b>เหมาะกับคำถาม:</b></div>
        <div style="font-size: 0.82rem; color: #cbd5e1; line-height: 1.4;">{current_meta['best_for']}</div>
    </div>
    """, unsafe_allow_html=True)

    with st.expander("📋 ดูเปรียบเทียบทุกโมเดล (All Models)"):
        for p_key, meta in models_meta.items():
            st.markdown(f"**{meta['name']}**")
            st.caption(f"• **รุ่น:** `{meta['model_id']}`\n• **Context Window:** {meta['context_window']}\n• **เหมาะสำหรับ:** {meta['best_for']}")
            st.write("")

    with st.expander("🧭 ขอบเขตข้อมูลธุรกิจที่สามารถามได้", expanded=False):
        st.markdown("""
        **🛍️ ยอดขาย & คำสั่งซื้อ**
        - ยอดขายรายวัน/เดือน/ปี
        - สินค้าขายดีและการจัดอันดับ
        - สถานะออเดอร์และประวัติการสั่งซื้อ

        **📦 สินค้า & สต็อกโกดัง**
        - รายละเอียดและหมวดหมู่สินค้า
        - ปริมาณสต็อกคงเหลือแยกโกดัง
        - สเปกและข้อมูลแบรนด์สินค้า

        **👥 ข้อมูลลูกค้า & พฤติกรรม**
        - โปรไฟล์ลูกค้าและช่องทางติดต่อ
        - ลูกค้า VIP ยอดสั่งซื้อสูงสุด
        - ที่อยู่และประเทศของลูกค้า

        **⭐ ความพึงพอใจ & การคืน**
        - คะแนนรีวิวสินค้า (1-5 ดาว)
        - อัตราและเหตุผลการคืนสินค้า
        - คูปองส่วนลดและการชำระเงิน
        """)

    st.divider()
    if st.button("🗑️ ล้างประวัติการแชต (Clear Chat)", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# ----------------- HERO HEADER -----------------
st.markdown("""
<div class="hero-container">
    <div class="hero-title">
        <span>📊 ผู้ช่วยวิเคราะห์ข้อมูลธุรกิจอัจฉริยะ (AI Data Assistant)</span>
    </div>
    <div class="hero-subtitle">
        ถามข้อมูลธุรกิจของคุณได้ง่ายๆ แค่พิมพ์เป็นภาษาไทย เหมือนคุยกับนักวิเคราะห์ข้อมูลส่วนตัว<br/>
        ไม่ว่าจะเป็น <strong>ยอดขาย, สินค้าขายดี, ข้อมูลลูกค้า, หรือสต็อกคงเหลือ</strong> ระบบจะสรุปคำตอบที่เข้าใจง่ายให้ทันที พร้อมดาวน์โหลดรายงาน Excel ได้ทันใจ
    </div>
    <div style="display: flex; gap: 10px; margin-top: 14px; flex-wrap: wrap;">
        <span style="background: rgba(56, 189, 248, 0.1); border: 1px solid rgba(56, 189, 248, 0.3); color: #38bdf8; font-size: 0.82rem; padding: 4px 10px; border-radius: 20px;">💬 ถามเป็นภาษาไทยง่ายๆ ไม่ต้องรู้โค้ด</span>
        <span style="background: rgba(52, 211, 153, 0.1); border: 1px solid rgba(52, 211, 153, 0.3); color: #34d399; font-size: 0.82rem; padding: 4px 10px; border-radius: 20px;">📈 สรุปข้อมูลยอดขายและสต็อกสดใหม่</span>
        <span style="background: rgba(168, 85, 247, 0.1); border: 1px solid rgba(168, 85, 247, 0.3); color: #c084fc; font-size: 0.82rem; padding: 4px 10px; border-radius: 20px;">📑 ดาวน์โหลดรายงานเป็น Excel ได้ทันที</span>
    </div>
</div>
""", unsafe_allow_html=True)

# ----------------- QUICK PROMPTS CHIPS -----------------
st.write("💡 **คำถามตัวอย่าง:**")
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

            if getattr(Config, "API_BASE_URL", ""):
                # Routed via FastAPI Endpoint
                from src.api.client import AgentAPIClient
                api_client = AgentAPIClient(base_url=Config.API_BASE_URL)
                result = api_client.query_stream(
                    question=prompt_to_run,
                    step_callback=live_step_callback,
                    provider=provider_choice,
                    model_name=model_choice,
                    chat_history=st.session_state.messages[:-1] if len(st.session_state.messages) > 1 else None
                )
            else:
                # Direct In-Process Execution
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
