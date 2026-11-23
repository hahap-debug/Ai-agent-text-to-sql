"""
Agent Service (Brain Orchestrator): Coordinates ReAct loops, multi-turn memory,
schema inspection, and safe query execution across Gemini, Ollama, and Mock engines.
"""

from typing import List, Dict, Any, Optional, Callable
from src.config import Config
from src.repositories import DatabaseConnection, QueryRepository, SchemaRepository
from src.models.entities import AgentStep, AgentRunResult
from src.services.sql_guard_service import SQLGuardService
from src.services.narrative_service import NarrativeService
from src.services.insight_context_service import InsightContextService
from src.services.coreference_service import CoreferenceService
from src.services.llm import (
    run_gemini_react,
    run_nvidia_react,
    run_ollama_react,
    run_mock_react,
)


class AgentService:
    """
    Autonomous ReAct Database Agent Orchestrator for ecommerce_db.
    """

    # Static method bindings for backward compatibility and test access
    filter_display_fields = staticmethod(SQLGuardService.filter_display_fields)
    sanitize_sql_limits = staticmethod(SQLGuardService.sanitize_sql_limits)
    _is_quota_error = staticmethod(SQLGuardService.is_quota_error)
    _format_thai_narrative = staticmethod(NarrativeService.format_thai_narrative)

    def __init__(
        self,
        db: Optional[DatabaseConnection] = None,
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        max_steps: int = Config.MAX_REACT_STEPS
    ):
        self.db = db or DatabaseConnection()
        self.provider = (provider or Config.LLM_PROVIDER).lower()
        if self.provider == "nvidia":
            self.api_key = api_key or Config.NVIDIA_API_KEY
            self.model_name = model_name or Config.NVIDIA_MODEL
        elif self.provider == "gemini":
            self.api_key = api_key or Config.GEMINI_API_KEY
            self.model_name = model_name or Config.GEMINI_MODEL
        else:
            self.api_key = api_key
            self.model_name = model_name or Config.OLLAMA_MODEL
        self.max_steps = max_steps
        self.gemini_client = None
        self.nvidia_client = None
        self._init_providers()

    def _init_providers(self):
        """Initializes Gemini and NVIDIA clients if configured."""
        if self.provider == "gemini" and self.api_key and self.api_key != "your_gemini_api_key_here":
            try:
                from google import genai
                self.gemini_client = genai.Client(api_key=self.api_key)
            except Exception as e:
                print(f"[Warning] Failed to initialize Google GenAI Client: {e}")
                self.gemini_client = None
        elif self.provider == "nvidia" and self.api_key and self.api_key != "your_nvidia_api_key_here":
            try:
                from openai import OpenAI
                self.nvidia_client = OpenAI(
                    base_url=Config.NVIDIA_BASE_URL,
                    api_key=self.api_key
                )
            except Exception as e:
                print(f"[Warning] Failed to initialize NVIDIA Client: {e}")
                self.nvidia_client = None

    @property
    def is_mysql(self) -> bool:
        return self.db.is_mysql

    def inspect_schema(self, tables: List[str]) -> Dict[str, Any]:
        """Tool 1: Inspect exact columns and keys for specified tables."""
        raw_schema = self.db.inspect_schema(tables) 
        return {
            "summary": self.db.format_schema_summary(raw_schema),
            "raw": raw_schema
        }

    def execute_sql(self, query: str) -> Dict[str, Any]:
        """Tool 2: Execute read-only SQL query on ecommerce_db."""
        return self.db.execute_read_only(query)

    def create_multi_sheet_excel(
        self,
        file_name: str,
        sheets: List[Dict[str, Any]],
        user_question: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Stream complete read-only query results to a workbook without the chat result cap."""
        from src.services.excel_service import ExcelService
        import json
        import tempfile

        sheets_data = []
        sheet_results = []
        temp_files = []
        try:
            for sheet in sheets:
                sheet_name = sheet.get("sheet_name", "Sheet")
                query = sheet.get("query", "")
                clean_query = SQLGuardService.sanitize_sql_limits(query, user_question or "")
                required_fields = sheet.get("required_fields") or []
                if isinstance(required_fields, str):
                    required_fields = [required_fields]
                row_grain = sheet.get("row_grain")
                if row_grain is not None:
                    row_grain = str(row_grain).strip().lower()
                    if row_grain not in {"entity", "aggregate", "detail"}:
                        return {"status": "error", "error": f"Sheet '{sheet_name}' has unsupported row_grain '{row_grain}'."}
                unique_by = sheet.get("unique_by") or []
                if isinstance(unique_by, str):
                    unique_by = [unique_by]
                if row_grain in {"entity", "aggregate"} and not unique_by:
                    return {
                        "status": "error",
                        "error": f"Sheet '{sheet_name}' declares row_grain='{row_grain}' and requires unique_by.",
                    }

                spool = tempfile.TemporaryFile(mode="w+t", encoding="utf-8")
                temp_files.append(spool)
                sample_rows = []
                row_count = 0

                with self.db.stream_read_only(clean_query) as query_stream:
                    columns = query_stream["columns"]
                    visible_columns = SQLGuardService.filter_display_fields(
                        [{column: None for column in columns}], preserve_fields=columns
                    )[0].keys() if columns else []
                    visible_columns = list(visible_columns)

                    output_columns = {str(column).casefold(): column for column in columns}
                    resolved_required = [
                        output_columns.get(str(field).casefold()) for field in required_fields
                    ]
                    missing_fields = [
                        field for field, resolved in zip(required_fields, resolved_required)
                        if resolved is None
                    ]
                    if missing_fields:
                        return {
                            "status": "error",
                            "error": (
                                f"Sheet '{sheet_name}' declares required_fields={required_fields}, but the query "
                                f"does not return: {missing_fields}. Select these fields with matching output aliases."
                            ),
                        }
                    visible_names = {str(column).casefold() for column in visible_columns}
                    protected_required = [
                        field for field, resolved in zip(required_fields, resolved_required)
                        if resolved is not None and str(resolved).casefold() not in visible_names
                    ]
                    if protected_required:
                        return {"status": "error", "error": f"Sheet '{sheet_name}' requires protected fields: {protected_required}."}

                    output_columns = {str(column).casefold(): column for column in visible_columns}
                    resolved_keys = [output_columns.get(str(key).casefold()) for key in unique_by]
                    missing_keys = [key for key, resolved in zip(unique_by, resolved_keys) if resolved is None]
                    if missing_keys:
                        return {
                            "status": "error",
                            "error": f"Sheet '{sheet_name}' declares unique_by={unique_by}, but the query omits {missing_keys}.",
                        }

                    seen = set()
                    for row_count, row in enumerate(query_stream["rows"], start=1):
                        empty_fields = [
                            field for field, resolved in zip(required_fields, resolved_required)
                            if row.get(resolved) is None
                            or (isinstance(row.get(resolved), str) and not row.get(resolved).strip())
                        ]
                        if empty_fields:
                            return {
                                "status": "error",
                                "error": f"Sheet '{sheet_name}' has missing required data in {empty_fields} at data row {row_count}.",
                            }

                        if unique_by:
                            key_value = tuple(row.get(key) for key in resolved_keys)
                            null_count = sum(value is None for value in key_value)
                            if null_count:
                                if row_grain == "detail" and null_count == len(key_value):
                                    pass
                                else:
                                    return {
                                        "status": "error",
                                        "error": f"Sheet '{sheet_name}' has an incomplete key from unique_by={unique_by} at data row {row_count}.",
                                    }
                            elif key_value in seen:
                                return {
                                    "status": "error",
                                    "error": f"Sheet '{sheet_name}' found a duplicate key from unique_by={unique_by} at data row {row_count}.",
                                }
                            else:
                                seen.add(key_value)

                        filtered_row = SQLGuardService.filter_display_fields([row], preserve_fields=columns)[0]
                        spool.write(json.dumps(filtered_row, ensure_ascii=False, default=str))
                        spool.write("\n")
                        if len(sample_rows) < InsightContextService.MAX_AGGREGATE_ROWS:
                            sample_rows.append(filtered_row)

                spool.flush()
                spool.seek(0)

                def iter_spooled_rows(file_obj=spool):
                    for line in file_obj:
                        if line.strip():
                            yield json.loads(line)

                sampled = row_count > len(sample_rows)
                insight_context = InsightContextService.build(
                    query=clean_query,
                    rows=sample_rows,
                    columns=visible_columns,
                    sampled=sampled,
                    dialect="mysql" if self.is_mysql else "sqlite",
                )
                insight_context["row_count"] = row_count
                if sampled:
                    insight_context["sampled_row_count"] = len(sample_rows)

                sheets_data.append({
                    "sheet_name": sheet_name,
                    "columns": visible_columns,
                    "rows": iter_spooled_rows(),
                    "theme_color": sheet.get("theme_color"),
                })
                sheet_results.append({
                    "sheet_name": sheet_name,
                    "row_count": row_count,
                    "truncated": False,
                    "row_limit": None,
                    "insight_context": insight_context,
                })

            result = ExcelService.create_streaming_workbook(file_name=file_name, sheets=sheets_data)
            if result.get("status") == "success":
                writer_results = result.get("sheet_results", [])
                result["sheet_results"] = [
                    {**(writer_results[index] if index < len(writer_results) else {}), **sheet_result}
                    for index, sheet_result in enumerate(sheet_results)
                ]
                result["insight_context"] = [
                    {"sheet_name": sheet["sheet_name"], **sheet["insight_context"]}
                    for sheet in sheet_results
                ]
            return result
        except Exception as exc:
            return {"status": "error", "error": str(exc)}
        finally:
            for temp_file in temp_files:
                temp_file.close()

    def reformulate_query_with_context(
        self,
        current_question: str,
        chat_history: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """
        Uses LLM Coreference Resolution to reformulate ambiguous or pronoun-dropped
        follow-up questions into standalone self-contained questions.
        """
        return CoreferenceService.reformulate_query_with_context(
            current_question=current_question,
            chat_history=chat_history,
            provider=self.provider,
            model_name=self.model_name,
            gemini_client=self.gemini_client,
            nvidia_client=self.nvidia_client
        )

    def _run_nvidia_react(
        self,
        user_question: str,
        step_callback: Optional[Callable[[AgentStep], None]] = None,
        chat_history: Optional[List[Dict[str, Any]]] = None
    ) -> AgentRunResult:
        return run_nvidia_react(self, user_question, step_callback, chat_history)

    def _run_ollama_react(
        self,
        user_question: str,
        step_callback: Optional[Callable[[AgentStep], None]] = None,
        chat_history: Optional[List[Dict[str, Any]]] = None
    ) -> AgentRunResult:
        return run_ollama_react(self, user_question, step_callback, chat_history)

    def _run_gemini_react(
        self,
        user_question: str,
        step_callback: Optional[Callable[[AgentStep], None]] = None,
        chat_history: Optional[List[Dict[str, Any]]] = None
    ) -> AgentRunResult:
        return run_gemini_react(self, user_question, step_callback, chat_history)

    def _run_mock_react(
        self,
        user_question: str,
        step_callback: Optional[Callable[[AgentStep], None]] = None,
        chat_history: Optional[List[Dict[str, Any]]] = None
    ) -> AgentRunResult:
        return run_mock_react(self, user_question, step_callback, chat_history)

    def run(
        self,
        user_question: str,
        step_callback: Optional[Callable[[AgentStep], None]] = None,
        chat_history: Optional[List[Dict[str, Any]]] = None
    ) -> AgentRunResult:
        """
        Executes the ReAct loop for the given business question with Multi-Turn Context Memory & Coreference Resolution.
        """
        active_question = user_question
        expanded = None

        # [TEMPORARILY DISABLED] Coreference Resolution (Context Expansion)
        # if chat_history and len(chat_history) > 0:
        #     expanded = self.reformulate_query_with_context(user_question, chat_history) #string
        #     if expanded and expanded != user_question:
        #         active_question = expanded

        if self.provider == "nvidia":
            if self.nvidia_client is not None:
                res = self._run_nvidia_react(active_question, step_callback, chat_history)
                if not res.success and self.gemini_client is not None:
                    print("[Dynamic Fallback] NVIDIA API request failed. Trying fallback to Gemini...")
                    fallback_res = self._run_gemini_react(active_question, step_callback, chat_history)
                    if fallback_res.success:
                        res = fallback_res
            else:
                res = AgentRunResult(
                    user_question=user_question,
                    final_answer="❌ **ไม่พบคีย์ NVIDIA API Key หรือยังไม่ได้ตั้งค่า:** กรุณาตรวจสอบค่า `NVIDIA_API_KEY` ในไฟล์ `.env`",
                    success=False,
                    error_message="NVIDIA API Key missing"
                )
        elif self.provider == "ollama":
            res = self._run_ollama_react(active_question, step_callback, chat_history)
        elif self.provider == "gemini":
            if self.gemini_client is not None:
                res = self._run_gemini_react(active_question, step_callback, chat_history)
                # Dynamic Quota Fallback: If Gemini quota exhausted, dynamically fallback to Ollama
                if not res.success:
                    err_str = str(res.error_message or "").lower()
                    ans_str = str(res.final_answer or "").lower()
                    if any(k in err_str or k in ans_str for k in ["quota", "429", "resource_exhausted", "ran out of quota"]):
                        print("[Dynamic Fallback] Gemini quota reached (429 / RESOURCE_EXHAUSTED). Dynamically switching to Local Ollama (qwen2.5-coder:7b)...")
                        fallback_res = self._run_ollama_react(active_question, step_callback, chat_history)
                        if fallback_res.success:
                            notice = (
                                "> ⚠️ **แจ้งเตือนโควตา (Quota Exceeded):** โควตา Google Gemini API เต็มชั่วคราว "
                                "— ระบบได้สลับมาประมวลผลผ่าน **Local Ollama (`qwen2.5-coder:7b`)** ให้โดยอัตโนมัติ 🔄\n\n"
                            )
                            fallback_res.final_answer = notice + fallback_res.final_answer
                            res = fallback_res
            else:
                print("[Dynamic Fallback] Gemini API Key missing. Falling back to Local Ollama...")
                fallback_res = self._run_ollama_react(active_question, step_callback, chat_history)
                if fallback_res.success:
                    notice = "> 💡 **คำแนะนำ:** ไม่พบ Gemini API Key ในระบบ — สลับมาประมวลผลผ่าน **Local Ollama (`qwen2.5-coder:7b`)** โดยอัตโนมัติ\n\n"
                    fallback_res.final_answer = notice + fallback_res.final_answer
                    res = fallback_res
                else:
                    return AgentRunResult(
                        user_question=user_question,
                        final_answer="❌ **ไม่ได้ระบุ Gemini API Key:** กรุณาใส่ API Key ใน Sidebar หรือในไฟล์ `.env`",
                        success=False,
                        error_message="Gemini API Key missing"
                    )
        elif self.provider == "mock":
            res = self._run_mock_react(active_question, step_callback, chat_history)
        else:
            res = self._run_ollama_react(active_question, step_callback, chat_history)

        res.user_question = user_question
        res.expanded_question = expanded if (expanded and expanded != user_question) else None

        # Retry workbook creation from the original query, not its capped chat observation.
        if (
            not getattr(res, "excel_file_path", None)
            and res.last_executed_sql
            and res.last_query_result is not None
        ):
            import re
            clean_q = re.sub(r'[^a-zA-Z0-9_\s]', '', user_question).strip().replace(' ', '_')[:30]
            auto_fname = f"BI_Data_Report_{clean_q}.xlsx" if clean_q else "Executive_BI_Report.xlsx"
            excel_out = self.create_multi_sheet_excel(
                file_name=auto_fname,
                sheets=[{"sheet_name": "Data_Export", "query": res.last_executed_sql, "theme_color": "navy"}],
                user_question=user_question,
            )
            if excel_out.get("status") == "success":
                res.excel_file_path = excel_out.get("file_path")
                res.excel_file_name = excel_out.get("file_name")
                res.excel_sheets = excel_out.get("sheets")

        if res.last_query_result:
            res.last_query_result = self.filter_display_fields(res.last_query_result)

        return res


# Backward compatibility alias
DatabaseAgent = AgentService
