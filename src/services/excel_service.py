"""
Excel Service: Enterprise-grade Multi-Worksheet Excel Generator.
Formats and exports high-fidelity corporate Excel (.xlsx) workbooks with multiple dynamic
worksheets, executive theme palettes, freeze panes, auto-fit columns, accounting number formats,
and automatic summary audit rows. Saves directly to the user's Desktop by default.
"""

from pathlib import Path
import re
from typing import List, Dict, Any, Optional
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter


THEME_PALETTES = {
    "navy": {
        "header_fill": "1F4E79",  # Corporate Navy (Overview / Audit)
        "header_font": "FFFFFF",
        "tab_color": "1F4E79",
        "zebra_fill": "F2F5F9",
    },
    "blue": {
        "header_fill": "2E75B6",  # Business Blue (Sales / Performance)
        "header_font": "FFFFFF",
        "tab_color": "2E75B6",
        "zebra_fill": "EDF4FB",
    },
    "green": {
        "header_fill": "375623",  # Profit / Customer / VIP Green
        "header_font": "FFFFFF",
        "tab_color": "375623",
        "zebra_fill": "F2F7F2",
    },
    "amber": {
        "header_fill": "C65911",  # Alert / Inventory Amber
        "header_font": "FFFFFF",
        "tab_color": "C65911",
        "zebra_fill": "FDF6F2",
    },
    "red": {
        "header_fill": "C00000",  # Risk / Cancel / Return Red
        "header_font": "FFFFFF",
        "tab_color": "C00000",
        "zebra_fill": "FDF2F2",
    },
    "slate": {
        "header_fill": "595959",  # Neutral Slate Gray
        "header_font": "FFFFFF",
        "tab_color": "595959",
        "zebra_fill": "F7F7F7",
    }
}

DEFAULT_PALETTE_ORDER = ["navy", "blue", "green", "amber", "red", "slate"]


class ExcelService:
    """Enterprise-grade Multi-Worksheet Excel Generator for Business Intelligence."""

    @staticmethod
    def sanitize_sheet_name(name: str) -> str:
        """
        Excel sheet names cannot exceed 31 chars and cannot contain \\ / ? * [ ] :
        """
        if not name:
            return "Sheet1"
        cleaned = re.sub(r'[\\/*?:\[\]]', '_', str(name)).strip()
        cleaned = re.sub(r'\s+', '_', cleaned)
        if len(cleaned) > 31:
            cleaned = cleaned[:31]
        return cleaned or "Sheet1"

    @staticmethod
    def sanitize_file_name(name: str) -> str:
        """Sanitizes filename and ensures .xlsx extension."""
        if not name:
            name = "Business_Data_Report.xlsx"
        cleaned = re.sub(r'[\\/*?:"<>|]', '_', str(name)).strip()
        if not cleaned.lower().endswith('.xlsx'):
            cleaned += ".xlsx"
        return cleaned

    @classmethod
    def get_number_format(cls, col_name: str, sample_val: Any) -> Optional[str]:
        """Detects whether a column represents currency, integer quantity, or percentage."""
        lower_col = col_name.lower()
        if any(term in lower_col for term in [
            "amount", "sales", "price", "revenue", "cost", "unit_price",
            "discount", "total_spent", "avg_spend", "total_sales", "subtotal"
        ]):
            return "฿#,##0.00"
        if any(term in lower_col for term in ["rate", "pct", "percent", "margin", "ratio"]):
            return "0.0%"
        if any(term in lower_col for term in [
            "quantity", "units", "count", "orders", "total_orders", "stock",
            "sold", "total_units", "items", "views"
        ]):
            return "#,##0"
        if isinstance(sample_val, float):
            return "#,##0.00"
        if isinstance(sample_val, int) and not any(term in lower_col for term in [
            "id", "code", "zip", "phone", "year", "number"
        ]):
            return "#,##0"
        return None

    @classmethod
    def create_workbook(
        cls,
        file_name: str,
        sheets: List[Dict[str, Any]],
        target_dir: Optional[Path] = None
    ) -> Dict[str, Any]:
        """
        Creates a styled Excel workbook with multiple sheets.
        
        Args:
            file_name: Output filename (e.g. 'Brand_Sales_and_Customers_Audit.xlsx')
            sheets: List of sheet configurations:
                [
                    {
                        "sheet_name": "Top_Brands",
                        "columns": ["brand_name", "total_sales", "units_sold"],
                        "rows": [{"brand_name": "Apple", "total_sales": 1450000, "units_sold": 45}, ...],
                        "theme_color": "navy" (optional: navy, blue, green, amber, red, slate)
                    },
                    ...
                ]
            target_dir: Optional directory to save the file. Defaults to user's Desktop.
        """
        target_directory = target_dir or (Path.home() / "Desktop")
        try:
            target_directory.mkdir(parents=True, exist_ok=True)
        except Exception:
            # Fallback to local workspace if desktop is not directly accessible
            target_directory = Path("reports")
            target_directory.mkdir(parents=True, exist_ok=True)

        safe_filename = cls.sanitize_file_name(file_name)
        file_path = target_directory / safe_filename

        wb = openpyxl.Workbook()
        used_sheet_names = set()
        created_sheets = []

        thin_border = Border(
            left=Side(style='thin', color='D9D9D9'),
            right=Side(style='thin', color='D9D9D9'),
            top=Side(style='thin', color='D9D9D9'),
            bottom=Side(style='thin', color='D9D9D9')
        )
        double_bottom_border = Border(
            left=Side(style='thin', color='D9D9D9'),
            right=Side(style='thin', color='D9D9D9'),
            top=Side(style='thin', color='A6A6A6'),
            bottom=Side(style='double', color='333333')
        )

        for i, s_cfg in enumerate(sheets):
            raw_title = s_cfg.get("sheet_name", f"Sheet{i+1}")
            s_name = cls.sanitize_sheet_name(raw_title)
            
            # Ensure unique sheet names
            base_s_name = s_name
            counter = 1
            while s_name in used_sheet_names:
                suffix = f"_{counter}"
                s_name = base_s_name[:31 - len(suffix)] + suffix
                counter += 1
            used_sheet_names.add(s_name)

            if i == 0:
                ws = wb.active
                ws.title = s_name
            else:
                ws = wb.create_sheet(title=s_name)

            created_sheets.append(s_name)

            # Palette determination
            theme_key = s_cfg.get("theme_color") or DEFAULT_PALETTE_ORDER[i % len(DEFAULT_PALETTE_ORDER)]
            palette = THEME_PALETTES.get(theme_key, THEME_PALETTES["navy"])
            ws.sheet_properties.tabColor = palette["tab_color"]

            columns = s_cfg.get("columns", [])
            rows_data = s_cfg.get("rows", [])

            # Extract columns from rows if columns not explicitly provided
            if not columns and rows_data and isinstance(rows_data[0], dict):
                columns = list(rows_data[0].keys())

            # Header Styling
            header_fill = PatternFill(start_color=palette["header_fill"], end_color=palette["header_fill"], fill_type="solid")
            header_font = Font(name="Segoe UI", size=11, bold=True, color=palette["header_font"])
            header_align = Alignment(horizontal="center", vertical="center", wrap_text=False)

            # Data Styling
            zebra_fill = PatternFill(start_color=palette["zebra_fill"], end_color=palette["zebra_fill"], fill_type="solid")
            white_fill = PatternFill(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid")
            data_font = Font(name="Segoe UI", size=10)

            # Write Headers (Row 1)
            ws.row_dimensions[1].height = 28
            for col_idx, col_name in enumerate(columns, 1):
                cell = ws.cell(row=1, column=col_idx, value=col_name)
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = header_align
                cell.border = thin_border

            # Detect number formats per column
            col_formats = {}
            for col_idx, col_name in enumerate(columns, 1):
                sample_val = None
                if rows_data:
                    first_row = rows_data[0]
                    sample_val = first_row.get(col_name) if isinstance(first_row, dict) else (first_row[col_idx - 1] if col_idx - 1 < len(first_row) else None)
                fmt = cls.get_number_format(col_name, sample_val)
                if fmt:
                    col_formats[col_idx] = fmt

            # Write Rows (Row 2 .. N)
            numeric_sums = {col_idx: 0.0 for col_idx in col_formats.keys()}
            has_numeric_row = False

            for r_idx, row in enumerate(rows_data, 2):
                ws.row_dimensions[r_idx].height = 20
                row_fill = zebra_fill if (r_idx % 2 == 1) else white_fill

                for col_idx, col_name in enumerate(columns, 1):
                    val = row.get(col_name) if isinstance(row, dict) else (row[col_idx - 1] if col_idx - 1 < len(row) else None)
                    cell = ws.cell(row=r_idx, column=col_idx, value=val)
                    cell.font = data_font
                    cell.fill = row_fill
                    cell.border = thin_border

                    # Alignment and format
                    if col_idx in col_formats:
                        cell.number_format = col_formats[col_idx]
                        cell.alignment = Alignment(horizontal="right", vertical="center")
                        if isinstance(val, (int, float)):
                            numeric_sums[col_idx] += float(val)
                            has_numeric_row = True
                    else:
                        cell.alignment = Alignment(horizontal="left", vertical="center")

            # Optional Summary Row (If rows > 1 and numeric columns exist)
            if len(rows_data) > 1 and has_numeric_row:
                tot_row_idx = len(rows_data) + 2
                ws.row_dimensions[tot_row_idx].height = 24
                tot_fill = PatternFill(start_color="E9ECEF", end_color="E9ECEF", fill_type="solid")
                tot_font = Font(name="Segoe UI", size=10, bold=True)

                for col_idx, col_name in enumerate(columns, 1):
                    cell = ws.cell(row=tot_row_idx, column=col_idx)
                    cell.fill = tot_fill
                    cell.font = tot_font
                    cell.border = double_bottom_border

                    if col_idx == 1:
                        cell.value = "Total (รวม)"
                        cell.alignment = Alignment(horizontal="left", vertical="center")
                    elif col_idx in col_formats and numeric_sums[col_idx] > 0:
                        cell.value = numeric_sums[col_idx]
                        cell.number_format = col_formats[col_idx]
                        cell.alignment = Alignment(horizontal="right", vertical="center")
                    else:
                        cell.value = ""

            # Freeze Panes
            ws.freeze_panes = "A2"

            # Auto-fit column widths
            for col_idx, col_name in enumerate(columns, 1):
                max_len = len(str(col_name))
                for row in rows_data[:100]:  # sample up to 100 rows for speed
                    val = row.get(col_name) if isinstance(row, dict) else (row[col_idx - 1] if col_idx - 1 < len(row) else None)
                    if val is not None:
                        val_str = str(val)
                        if len(val_str) > max_len:
                            max_len = len(val_str)
                col_letter = get_column_letter(col_idx)
                ws.column_dimensions[col_letter].width = max(min(max_len + 4, 60), 14)

        try:
            wb.save(file_path)
        except PermissionError:
            # If writing to Desktop was blocked by environment sandbox, fallback to local reports
            fallback_dir = Path("reports")
            fallback_dir.mkdir(parents=True, exist_ok=True)
            file_path = fallback_dir / safe_filename
            wb.save(file_path)

        total_rows = sum(len(s.get("rows", [])) for s in sheets)
        return {
            "status": "success",
            "file_path": str(file_path.resolve()),
            "file_name": safe_filename,
            "sheets": created_sheets,
            "total_sheets": len(created_sheets),
            "total_rows": total_rows,
            "desktop_saved": str(file_path.resolve())
        }
