"""
Comprehensive Test Suite for AI Data Agent
Tests AST validation, schema inspection, read-only SQL execution, and ReAct self-correction.
"""

import pytest
from src.validator import validate_ast_safety, SQLSecurityError, SQLSyntaxError
from src.database import DatabaseConnection
from src.agent import DatabaseAgent

@pytest.fixture
def test_db():
    # Use SQLite for reliable, isolated local test suite
    return DatabaseConnection(db_type="sqlite")

@pytest.fixture
def agent(test_db):
    return DatabaseAgent(db=test_db, provider="mock")

# ----------------- 1. AST SAFETY & SECURITY TESTS -----------------

def test_ast_safe_select():
    query = "SELECT brand_name, COUNT(*) FROM brands GROUP BY brand_name;"
    ast = validate_ast_safety(query)
    assert ast is not None

def test_ast_safe_cte_select():
    query = "WITH top_brands AS (SELECT brand_id FROM brands LIMIT 5) SELECT * FROM top_brands;"
    ast = validate_ast_safety(query)
    assert ast is not None

def test_ast_blocks_drop_table():
    with pytest.raises(SQLSecurityError):
        validate_ast_safety("DROP TABLE users;")

def test_ast_blocks_delete():
    with pytest.raises(SQLSecurityError):
        validate_ast_safety("DELETE FROM orders WHERE order_id = 1;")

def test_ast_blocks_update():
    with pytest.raises(SQLSecurityError):
        validate_ast_safety("UPDATE products SET price = 0;")

def test_ast_blocks_insert():
    with pytest.raises(SQLSecurityError):
        validate_ast_safety("INSERT INTO users (username) VALUES ('hacker');")

def test_ast_blocks_stacked_queries():
    with pytest.raises(SQLSecurityError):
        validate_ast_safety("SELECT * FROM products; DROP TABLE products;")

def test_ast_syntax_error():
    with pytest.raises(SQLSyntaxError):
        validate_ast_safety("SELEC FROM WHERE ;;;")

# ----------------- 2. SCHEMA INSPECTION TESTS -----------------

def test_inspect_schema_valid_tables(test_db):
    schema = test_db.inspect_schema(["brands", "products"])
    assert "brands" in schema
    assert "products" in schema
    
    brand_cols = [c["name"] for c in schema["brands"]["columns"]]
    assert "brand_id" in brand_cols
    assert "brand_name" in brand_cols

def test_inspect_schema_nonexistent_table(test_db):
    schema = test_db.inspect_schema(["non_existent_table_xyz"])
    assert "error" in schema["non_existent_table_xyz"]

def test_format_schema_summary(test_db):
    schema = test_db.inspect_schema(["brands"])
    summary = test_db.format_schema_summary(schema)
    assert "Table `brands`" in summary
    assert "brand_id (PK)" in summary

# ----------------- 3. SQL EXECUTION TESTS -----------------

def test_execute_read_only_success(test_db):
    res = test_db.execute_read_only("SELECT brand_id, brand_name FROM brands ORDER BY brand_id ASC LIMIT 3;")
    assert res["status"] == "success"
    assert res["row_count"] >= 3
    assert res["rows"][0]["brand_name"] == "Apple"

def test_execute_read_only_blocks_mutation(test_db):
    res = test_db.execute_read_only("DROP TABLE users;")
    assert res["status"] == "error"
    assert "forbidden" in res["message"].lower() or "statement type" in res["message"].lower()

# ----------------- 4. AGENT REACT & SELF-HEALING TESTS -----------------

def test_agent_run_ranking_query(agent):
    result = agent.run("ช่วงนี้สินค้าแบรนด์ไหนขายดีที่สุด 5 อันดับแรก")
    assert result.success is True
    assert len(result.steps) >= 2
    assert "สรุปผลลัพธ์สำคัญ" in result.final_answer
    assert "ข้อมูลเชิงลึก" in result.final_answer
    assert "ข้อเสนอแนะเชิงธุรกิจ" in result.final_answer
    assert result.last_executed_sql is not None

def test_agent_self_healing_cycle(agent):
    result = agent.run("แสดงคำสั่งซื้อที่ถูกยกเลิก พร้อมเหตุผลการยกเลิก")
    assert result.success is True
    # Verify that error was triggered and then corrected in later steps
    error_steps = [s for s in result.steps if s.is_error]
    assert len(error_steps) >= 1
    assert "cancel_reason" in str(error_steps[0].observation) or "no such column" in str(error_steps[0].observation).lower()
    
    # Verify that final answer still succeeded after self-correction
    assert "สรุปผลลัพธ์สำคัญ" in result.final_answer

def test_agent_customer_purchases(agent):
    """Test: ลูกค้าแต่ละคน ซื้อของอะไรบ้าง"""
    result = agent.run("ลูกค้าแต่ละคน ซื้อของอะไรบ้าง")
    assert result.success is True
    assert len(result.steps) >= 2
    assert "สรุปผลลัพธ์สำคัญ" in result.final_answer
    assert "orders" in result.last_executed_sql.lower()
    assert "products" in result.last_executed_sql.lower()
    assert len(result.last_query_result) > 0

def test_agent_customer_purchases_with_country(agent):
    """Test: ลูกค้าแต่ละคน ซื้อของอะไรบ้าง และมาจากประเทศไหน"""
    result = agent.run("ลูกค้าแต่ละคน ซื้อของอะไรบ้าง และมาจากประเทศไหน")
    assert result.success is True
    assert len(result.steps) >= 2
    assert "สรุปผลลัพธ์สำคัญ" in result.final_answer
    assert "orders" in result.last_executed_sql.lower()
    assert "addresses" in result.last_executed_sql.lower() or "country" in result.last_executed_sql.lower()
    assert len(result.last_query_result) > 0

def test_agent_multi_turn_followup(agent):
    """Test: Multi-turn conversational context memory drill-down"""
    # Turn 1: Initial query
    turn1_result = agent.run("ขอข้อมูลลูกค้าทั้งหมดหน่อย")
    assert turn1_result.success is True
    assert turn1_result.last_executed_sql is not None

    # Simulate chat history saved in UI session state
    chat_history = [
        {"role": "user", "content": "ขอข้อมูลลูกค้าทั้งหมดหน่อย"},
        {"role": "assistant", "content": turn1_result.final_answer, "sql": turn1_result.last_executed_sql}
    ]

    # Turn 2: Follow-up question relying on previous turn
    turn2_result = agent.run("ขอแค่ 5 คนแรกและแสดงอีเมล", chat_history=chat_history)
    assert turn2_result.success is True
    assert "limit 5" in turn2_result.last_executed_sql.lower()
    assert "email" in turn2_result.last_executed_sql.lower()
    assert len(turn2_result.last_query_result) <= 5
    assert "สรุปผลลัพธ์สำคัญ" in turn2_result.final_answer

def test_agent_top_spending_customers(agent):
    """Test: ขอลูกค้า 3 คนที่ใช้จ่ายเยอะที่สุด"""
    result = agent.run("ขอลูกค้า 3 คนที่ใช้จ่ายเยอะที่สุด")
    assert result.success is True
    assert len(result.steps) >= 2
    assert "สรุปผลลัพธ์สำคัญ" in result.final_answer
    assert "limit 3" in result.last_executed_sql.lower()
    assert "total_spent" in result.last_executed_sql.lower() or "total_amount" in result.last_executed_sql.lower()
    assert len(result.last_query_result) == 3

def test_agent_coreference_country_followup(agent):
    """Test: Coreference Resolution - ขอลูกค้า 3 คนที่ใช้จ่ายเยอะที่สุด -> มาจากประเทศไหนบ้าง"""
    # Turn 1
    t1 = agent.run("ขอลูกค้า 3 คนที่ใช้จ่ายเยอะที่สุด")
    assert t1.success is True

    chat_history = [
        {"role": "user", "content": "ขอลูกค้า 3 คนที่ใช้จ่ายเยอะที่สุด"},
        {"role": "assistant", "content": t1.final_answer, "sql": t1.last_executed_sql}
    ]

    # Turn 2: Follow-up question without subject
    t2 = agent.run("มาจากประเทศไหนบ้าง", chat_history=chat_history)
    assert t2.success is True
    assert t2.expanded_question is not None
    assert "ประเทศ" in t2.expanded_question
    assert "addresses" in t2.last_executed_sql.lower()
    assert "country" in t2.last_executed_sql.lower()
    assert "สรุปผลลัพธ์สำคัญ" in t2.final_answer


