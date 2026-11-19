"""
Unit and Integration Tests for Multi-Worksheet Excel Service and Agent Tool.
"""

from pathlib import Path
import pytest
import openpyxl
from src.services.excel_service import ExcelService
from src.services.agent_service import AgentService
from src.database.connection import DatabaseConnection


def test_sanitize_sheet_and_file_name():
    """Verifies that invalid characters and long names are safely sanitized."""
    raw_sheet = "Report: 2026/Q1 *Sales* [VIP]? \\All"
    sanitized = ExcelService.sanitize_sheet_name(raw_sheet)
    assert len(sanitized) <= 31
    for char in [":", "/", "*", "[", "]", "?", "\\"]:
        assert char not in sanitized

    long_sheet = "A" * 50
    assert len(ExcelService.sanitize_sheet_name(long_sheet)) == 31

    raw_file = 'Sales"Report*2026'
    sanitized_file = ExcelService.sanitize_file_name(raw_file)
    assert sanitized_file.endswith(".xlsx")
    assert "*" not in sanitized_file
    assert '"' not in sanitized_file


def test_number_format_detection():
    """Verifies that column names and sample values map to appropriate accounting formats."""
    assert ExcelService.get_number_format("total_sales", 15000.5) == "฿#,##0.00"
    assert ExcelService.get_number_format("unit_price", 99.0) == "฿#,##0.00"
    assert ExcelService.get_number_format("total_orders", 12) == "#,##0"
    assert ExcelService.get_number_format("profit_margin_pct", 0.25) == "0.0%"
    assert ExcelService.get_number_format("customer_id", 101) is None


def test_create_workbook_multi_sheets(tmp_path: Path):
    """Verifies generation of a multi-sheet Excel workbook with styling, freeze panes, and summary rows."""
    sheets_config = [
        {
            "sheet_name": "Top_Brands",
            "columns": ["brand_name", "total_sales", "units_sold"],
            "rows": [
                {"brand_name": "Apple", "total_sales": 1500000.0, "units_sold": 50},
                {"brand_name": "Samsung", "total_sales": 950000.0, "units_sold": 40},
            ],
            "theme_color": "blue"
        },
        {
            "sheet_name": "Top_Customers",
            "columns": ["customer_name", "total_spent", "orders_count"],
            "rows": [
                {"customer_name": "Alice Smith", "total_spent": 125000.0, "orders_count": 8},
                {"customer_name": "Bob Jones", "total_spent": 84000.0, "orders_count": 5},
            ],
            "theme_color": "green"
        }
    ]

    res = ExcelService.create_workbook(
        file_name="Executive_Audit_Test.xlsx",
        sheets=sheets_config,
        target_dir=tmp_path
    )

    assert res["status"] == "success"
    assert res["total_sheets"] == 2
    assert res["total_rows"] == 4
    
    file_path = Path(res["file_path"])
    assert file_path.exists()

    # Inspect openpyxl workbook
    wb = openpyxl.load_workbook(file_path)
    assert wb.sheetnames == ["Top_Brands", "Top_Customers"]

    ws1 = wb["Top_Brands"]
    assert ws1.freeze_panes == "A2"
    # Row 1 is header
    assert ws1.cell(row=1, column=1).value == "brand_name"
    # Data row
    assert ws1.cell(row=2, column=2).value == 1500000.0
    assert ws1.cell(row=2, column=2).number_format == "฿#,##0.00"
    # Total row (row 4)
    assert ws1.cell(row=4, column=1).value == "Total (รวม)"
    assert ws1.cell(row=4, column=2).value == 2450000.0


def test_agent_create_multi_sheet_excel(tmp_path: Path):
    """Verifies that AgentService can execute queries and generate an Excel workbook."""
    db = DatabaseConnection(db_type="sqlite")
    agent = AgentService(db=db, provider="mock")

    sheets = [
        {
            "sheet_name": "Active_Products",
            "query": "SELECT product_name, price, cost_price FROM products LIMIT 5;",
            "theme_color": "navy"
        },
        {
            "sheet_name": "Recent_Orders",
            "query": "SELECT order_id, total_amount, order_status FROM orders LIMIT 5;",
            "theme_color": "green"
        }
    ]

    # Save to tmp_path by monkeypatching target_dir or calling ExcelService directly
    res = agent.create_multi_sheet_excel("Agent_Report_Test.xlsx", sheets)
    assert res["status"] == "success"
    assert "Active_Products" in res["sheets"]
    assert "Recent_Orders" in res["sheets"]
    assert Path(res["file_path"]).exists()


def test_agent_run_excel_request_mock():
    """Verifies end-to-end ReAct flow for a multi-topic question requesting Excel in mock mode."""
    db = DatabaseConnection(db_type="sqlite")
    agent = AgentService(db=db, provider="mock")

    result = agent.run("ช่วยทำรายงาน Excel สรุปยอดขาย 5 แบรนด์ดัง และลูกค้าที่ซื้อเยอะที่สุด")
    assert result.success is True
    assert result.excel_file_path is not None
    assert result.excel_file_name.endswith(".xlsx")
    assert "Top_5_Brands" in result.excel_sheets
    assert "Top_5_Customers" in result.excel_sheets
    assert Path(result.excel_file_path).exists()


def test_agent_guarantees_excel_on_any_query():
    """Verifies that even a simple single-topic question automatically generates and exports an Excel file."""
    db = DatabaseConnection(db_type="sqlite")
    agent = AgentService(db=db, provider="mock")

    result = agent.run("ขอข้อมูลลูกค้าทั้งหมดหน่อย")
    assert result.success is True
    assert result.excel_file_path is not None
    assert Path(result.excel_file_path).exists()
    assert result.excel_file_name.endswith(".xlsx")
