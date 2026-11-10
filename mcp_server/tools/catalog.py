"""
Tool 1: Catalog Discovery
Allows AI to discover all tables in ecommerce_db and understand their business context.
"""

from typing import List, Dict, Any
from mcp_server.db import MCPDatabase

TABLE_CATALOG_INFO = {
    "users": "Customer accounts, registration dates, full name, email (password_hash must be omitted).",
    "addresses": "Customer shipping and billing addresses linked to users.",
    "products": "Product catalog, SKU, pricing, category_id, brand_id, status (active/inactive).",
    "categories": "Product category hierarchy.",
    "brands": "Product brands and manufacturers.",
    "warehouses": "Fulfillment centers and physical storage locations.",
    "inventory": "Current stock quantities per product per warehouse.",
    "orders": "Transactions, total amount, order status, creation timestamp.",
    "order_items": "Line items in each order: quantity, unit_price, product_id.",
    "payments": "Payment transactions, payment status, payment_method_id.",
    "payment_methods": "Lookup table of payment channels (PromptPay, Credit Card, etc.).",
    "shipping_methods": "Delivery carriers and shipping options.",
    "coupons": "Promotional discount codes, discount values, valid periods.",
    "order_coupons": "Mapping of coupons applied to specific orders.",
    "product_reviews": "Customer ratings (1-5 stars) and review text.",
    "support_tickets": "Customer inquiry tickets, severity, and resolution status.",
    "order_returns": "Product return requests, return status, and refund amounts.",
    "return_reasons": "Master lookup for why a customer returned an order/item."
}

def list_tables_handler() -> Dict[str, Any]:
    """
    Returns the complete list of authorized tables in ecommerce_db along with their business descriptions.
    """
    try:
        conn = MCPDatabase.get_connection()
        with conn.cursor() as cursor:
            cursor.execute("SHOW TABLES;")
            raw_tables = cursor.fetchall()
        conn.close()

        table_names = [list(row.values())[0] for row in raw_tables]
        
        tables_with_desc = []
        for name in table_names:
            desc = TABLE_CATALOG_INFO.get(name.lower(), "Table in ecommerce_db")
            tables_with_desc.append({
                "table_name": name,
                "description": desc
            })

        return {
            "status": "success",
            "database": "ecommerce_db",
            "total_tables": len(tables_with_desc),
            "tables": tables_with_desc
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to list tables: {str(e)}"
        }
