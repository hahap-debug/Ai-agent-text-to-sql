"""
Test Suite for Tier 2: FastAPI Application Layer.
Tests REST endpoints, health check, schema inspection, synchronous query, and SSE streaming.
"""

import pytest
from src.database import DatabaseConnection
import src.api.routes as routes
from src.api.schemas import (
    ChatRequest,
    SchemaInspectRequest,
    HealthResponse,
    ChatResponse,
    SchemaInspectResponse
)

@pytest.fixture(autouse=True)
def setup_test_db():
    routes._db_instance = DatabaseConnection(db_type="sqlite")

def test_api_health_endpoint():
    res = routes.check_health()
    assert isinstance(res, HealthResponse)
    assert res.status == "ok"
    assert res.database == "connected"
    assert res.version == "2.0.0"

def test_api_list_tables():
    tables = routes.list_tables()
    assert isinstance(tables, list)
    assert len(tables) > 0
    assert any("brand" in t or "user" in t for t in tables)

def test_api_schema_inspect_post():
    req = SchemaInspectRequest(tables=["brands", "products"])
    res = routes.inspect_schema_post(req)
    assert isinstance(res, SchemaInspectResponse)
    assert "brands" in res.tables
    assert "Table `brands`" in res.summary

def test_api_query_sync_mock():
    req = ChatRequest(
        question="ช่วงนี้สินค้าแบรนด์ไหนขายดีที่สุด 5 อันดับแรก",
        provider="mock"
    )
    res = routes.execute_query(req)
    assert isinstance(res, ChatResponse)
    assert res.success is True
    assert "สรุปผลลัพธ์สำคัญ" in res.final_answer
    assert len(res.steps) >= 2
    assert res.last_executed_sql is not None

def test_api_query_stream_mock():
    agent = routes.get_agent(provider="mock")
    chunks = list(routes.generate_sse_events(agent, "ขอลูกค้า 3 คนที่ใช้จ่ายเยอะที่สุด"))
    all_content = "".join(chunks)
    assert "event: step" in all_content
    assert "event: done" in all_content
    assert "สรุปผลลัพธ์สำคัญ" in all_content
