# 🔌 E-Commerce Database MCP Server (`ecommerce-db`)

> **Model Context Protocol (MCP) Server** สำหรับฐานข้อมูล `ecommerce_db`  
> ออกแบบโครงสร้างแยก Tool อิสระ (Modular) พร้อมระบบความปลอดภัย **AST Read-Only Guard**

---

## 🛠️ เครื่องมือที่ให้บริการ (Available Tools)

เซิร์ฟเวอร์นี้ให้บริการ 3 เครื่องมือที่แยกหน้าที่กันชัดเจน:

1. **`list_tables`**:  
   ดึงรายชื่อตารางทั้งหมดใน `ecommerce_db` พร้อมคำอธิบายทางธุรกิจ ช่วยให้ AI รู้ว่าควรค้นหาข้อมูลจากตารางใด
2. **`inspect_schema(tables: list[str])`**:  
   ตรวจสอบโครงสร้าง คอลัมน์, Data Types, Primary Key, และ Foreign Keys ของตารางที่ระบุ ป้องกัน AI คาดเดาชื่อฟิลด์ผิด
3. **`execute_sql(query: str)`**:  
   รันคำสั่ง MySQL 8.x `SELECT` เพื่อดึงข้อมูล  
   - มี **AST Security Guard** สกัดคำสั่งอันตราย (`DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`) ทันที 100%
   - บังคับใช้ `ONLY_FULL_GROUP_BY`
   - มีระบบจำกัดแถวผลลัพธ์ (`LIMIT 50`) อัตโนมัติ

---

## 🚀 วิธีนำไปเสียบใช้งาน (Configuration)

### 1. เชื่อมต่อกับ Claude Desktop
เปิดไฟล์ตั้งค่าของ Claude Desktop:
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
- **Mac:** `~/Library/Application Support/Claude/claude_desktop_config.json`

คัดลอก JSON ด้านล่างไปวาง:
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

### 2. เชื่อมต่อกับ Cursor / Windsurf / Antigravity
ในหน้าตั้งค่า Features -> MCP Servers ให้เพิ่มเซิร์ฟเวอร์ใหม่:
- **Name:** `ecommerce-db`
- **Type:** `command` (stdio)
- **Command:** `python C:\Users\ACER\Desktop\Agent_natural_langauge_to_sql\mcp_server\server.py`

---

## 🧪 การทดสอบเครื่องมือ (Testing)
สามารถทดสอบการทำงานของเครื่องมือทั้งหมดแบบ Standalone ได้ด้วยคำสั่ง:
```bash
python mcp_server/test_mcp.py
```
