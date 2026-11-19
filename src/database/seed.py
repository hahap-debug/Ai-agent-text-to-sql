"""
SQLite Local DB Initializer (for offline test suite)
Seeds data/ecommerce.db without touching MySQL.
"""

import sqlite3
from pathlib import Path
from src.config import Config

BASE_DIR = Path(__file__).resolve().parent.parent

SQLITE_SCHEMA = """
-- 1. Brands
CREATE TABLE IF NOT EXISTS brands (
    brand_id INTEGER PRIMARY KEY AUTOINCREMENT,
    brand_name TEXT NOT NULL UNIQUE,
    country_of_origin TEXT,
    website TEXT
);

-- 2. Categories
CREATE TABLE IF NOT EXISTS categories (
    category_id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_name TEXT NOT NULL,
    parent_id INTEGER,
    slug TEXT UNIQUE,
    description TEXT,
    FOREIGN KEY (parent_id) REFERENCES categories(category_id)
);

-- 3. Products
CREATE TABLE IF NOT EXISTS products (
    product_id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_name TEXT NOT NULL,
    sku TEXT NOT NULL UNIQUE,
    category_id INTEGER,
    brand_id INTEGER,
    price REAL NOT NULL,
    cost_price REAL,
    status TEXT DEFAULT 'active',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (category_id) REFERENCES categories(category_id),
    FOREIGN KEY (brand_id) REFERENCES brands(brand_id)
);

-- 4. Users
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    first_name TEXT,
    last_name TEXT,
    phone TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- 5. Addresses
CREATE TABLE IF NOT EXISTS addresses (
    address_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    address_line1 TEXT NOT NULL,
    city TEXT NOT NULL,
    state TEXT,
    postal_code TEXT NOT NULL,
    country TEXT DEFAULT 'Thailand',
    address_type TEXT DEFAULT 'shipping',
    is_default INTEGER DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

-- 6. Warehouses
CREATE TABLE IF NOT EXISTS warehouses (
    warehouse_id INTEGER PRIMARY KEY AUTOINCREMENT,
    warehouse_name TEXT NOT NULL,
    location TEXT NOT NULL,
    capacity INTEGER DEFAULT 10000
);

-- 7. Inventory
CREATE TABLE IF NOT EXISTS inventory (
    inventory_id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    warehouse_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 0,
    reserved_quantity INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (product_id) REFERENCES products(product_id),
    FOREIGN KEY (warehouse_id) REFERENCES warehouses(warehouse_id)
);

-- 8. Orders
CREATE TABLE IF NOT EXISTS orders (
    order_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    order_status TEXT NOT NULL DEFAULT 'pending',
    total_amount REAL NOT NULL DEFAULT 0.00,
    shipping_fee REAL DEFAULT 0.00,
    tax_amount REAL DEFAULT 0.00,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    cancelled_at TEXT,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

-- 9. Order Items
CREATE TABLE IF NOT EXISTS order_items (
    order_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 1,
    unit_price REAL NOT NULL,
    discount_amount REAL DEFAULT 0.00,
    FOREIGN KEY (order_id) REFERENCES orders(order_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);

-- 10. Payment Methods
CREATE TABLE IF NOT EXISTS payment_methods (
    payment_method_id INTEGER PRIMARY KEY AUTOINCREMENT,
    method_name TEXT NOT NULL UNIQUE,
    is_active INTEGER DEFAULT 1
);

-- 11. Payments
CREATE TABLE IF NOT EXISTS payments (
    payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    payment_method_id INTEGER NOT NULL,
    amount REAL NOT NULL,
    payment_status TEXT NOT NULL DEFAULT 'pending',
    transaction_ref TEXT,
    paid_at TEXT,
    FOREIGN KEY (order_id) REFERENCES orders(order_id),
    FOREIGN KEY (payment_method_id) REFERENCES payment_methods(payment_method_id)
);

-- 12. Shipping Methods
CREATE TABLE IF NOT EXISTS shipping_methods (
    shipping_method_id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider_name TEXT NOT NULL,
    service_name TEXT NOT NULL,
    base_rate REAL NOT NULL DEFAULT 50.00,
    estimated_days INTEGER DEFAULT 3
);

-- 13. Coupons
CREATE TABLE IF NOT EXISTS coupons (
    coupon_id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    discount_type TEXT NOT NULL DEFAULT 'percentage',
    discount_value REAL NOT NULL,
    min_order_amount REAL DEFAULT 0.00,
    is_active INTEGER DEFAULT 1
);

-- 14. Order Coupons
CREATE TABLE IF NOT EXISTS order_coupons (
    order_coupon_id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    coupon_id INTEGER NOT NULL,
    discount_applied REAL NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders(order_id),
    FOREIGN KEY (coupon_id) REFERENCES coupons(coupon_id)
);

-- 15. Product Reviews
CREATE TABLE IF NOT EXISTS product_reviews (
    review_id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    rating INTEGER NOT NULL,
    review_text TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES products(product_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

-- 16. Support Tickets
CREATE TABLE IF NOT EXISTS support_tickets (
    ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    subject TEXT NOT NULL,
    severity TEXT DEFAULT 'medium',
    status TEXT DEFAULT 'open',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

-- 17. Return Reasons
CREATE TABLE IF NOT EXISTS return_reasons (
    reason_id INTEGER PRIMARY KEY AUTOINCREMENT,
    reason_name TEXT NOT NULL UNIQUE,
    reason_description TEXT
);

-- 18. Order Returns
CREATE TABLE IF NOT EXISTS order_returns (
    return_id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    return_reason_id INTEGER NOT NULL,
    return_status TEXT DEFAULT 'pending',
    refund_amount REAL DEFAULT 0.00,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (order_id) REFERENCES orders(order_id),
    FOREIGN KEY (return_reason_id) REFERENCES return_reasons(reason_id)
);
"""

SQLITE_SEED = """
-- Brands
INSERT OR IGNORE INTO brands (brand_id, brand_name, country_of_origin, website) VALUES
(1, 'Apple', 'USA', 'https://www.apple.com'),
(2, 'Samsung', 'South Korea', 'https://www.samsung.com'),
(3, 'Sony', 'Japan', 'https://www.sony.com'),
(4, 'Xiaomi', 'China', 'https://www.mi.com'),
(5, 'Asus', 'Taiwan', 'https://www.asus.com');

-- Categories
INSERT OR IGNORE INTO categories (category_id, category_name, parent_id, slug, description) VALUES
(1, 'Electronics', NULL, 'electronics', 'Electronic devices'),
(2, 'Smartphones', 1, 'smartphones', 'Mobile phones'),
(3, 'Laptops', 1, 'laptops', 'Notebooks'),
(4, 'Audio', 1, 'audio', 'Headphones and speakers');

-- Products
INSERT OR IGNORE INTO products (product_id, product_name, sku, category_id, brand_id, price, cost_price, status) VALUES
(1, 'iPhone 15 Pro 128GB', 'APL-IP15P-128', 2, 1, 38900.00, 31000.00, 'active'),
(2, 'iPhone 15 128GB', 'APL-IP15-128', 2, 1, 31900.00, 25000.00, 'active'),
(3, 'MacBook Air M2 13-inch', 'APL-MBA-M2', 3, 1, 34900.00, 28000.00, 'active'),
(4, 'Galaxy S24 Ultra 256GB', 'SAM-S24U-256', 2, 2, 43900.00, 35000.00, 'active'),
(5, 'Galaxy A55 5G', 'SAM-A55-128', 2, 2, 13999.00, 10500.00, 'active'),
(6, 'Sony WH-1000XM5 Headphone', 'SNY-WH1000XM5', 4, 3, 14990.00, 11000.00, 'active'),
(7, 'PlayStation 5 Console', 'SNY-PS5-SLIM', 1, 3, 18690.00, 15000.00, 'active'),
(8, 'Redmi Note 13 Pro 5G', 'XIA-RN13P-256', 2, 4, 10990.00, 8500.00, 'active'),
(9, 'Xiaomi Smart Band 8', 'XIA-BAND8', 1, 4, 1490.00, 950.00, 'active'),
(10, 'ROG Zephyrus G14 Gaming Laptop', 'ASU-ROG-G14', 3, 5, 59900.00, 48000.00, 'active');

-- Users
INSERT OR IGNORE INTO users (user_id, username, email, password_hash, first_name, last_name, phone) VALUES
(1, 'somchai_k', 'somchai.k@example.com', 'hash_1', 'Somchai', 'Kitisak', '0812345678'),
(2, 'wanida_s', 'wanida.s@example.com', 'hash_2', 'Wanida', 'Sukcharoen', '0823456789'),
(3, 'anan_p', 'anan.p@example.com', 'hash_3', 'Anan', 'Prasert', '0834567890');

-- Return Reasons
INSERT OR IGNORE INTO return_reasons (reason_id, reason_name, reason_description) VALUES
(1, 'Defective Item', 'The product arrived broken or malfunctioning'),
(2, 'Changed Mind', 'Customer decided not to keep the product within 7 days');

-- Orders
INSERT OR IGNORE INTO orders (order_id, user_id, order_status, total_amount, shipping_fee, tax_amount) VALUES
(1001, 1, 'completed', 73800.00, 0.00, 4828.00),
(1002, 2, 'completed', 43900.00, 0.00, 2872.00),
(1003, 3, 'completed', 33680.00, 50.00, 2200.00),
(1004, 1, 'completed', 13970.00, 45.00, 910.00),
(1005, 2, 'completed', 59900.00, 0.00, 3918.00),
(1024, 1, 'cancelled', 38900.00, 0.00, 2544.00),
(1056, 3, 'cancelled', 14990.00, 50.00, 980.00);

-- Order Items (Apple: 1,450,000 / 45, Samsung: 980,000 / 60, Sony: 620,000 / 35, Xiaomi: 410,000 / 80, Asus: 350,000 / 20)
INSERT OR IGNORE INTO order_items (order_item_id, order_id, product_id, quantity, unit_price) VALUES
(1, 1001, 1, 25, 38900.00),
(2, 1001, 2, 10, 31900.00),
(3, 1001, 3, 10, 15850.00),
(4, 1002, 4, 15, 43900.00),
(5, 1002, 5, 45, 7144.44),
(6, 1003, 6, 20, 14990.00),
(7, 1003, 7, 15, 21346.67),
(8, 1004, 8, 20, 10990.00),
(9, 1004, 9, 60, 3170.00),
(10, 1005, 10, 20, 17500.00);

-- Order Returns
INSERT OR IGNORE INTO order_returns (return_id, order_id, return_reason_id, return_status, refund_amount) VALUES
(1, 1024, 1, 'approved', 38900.00),
(2, 1056, 2, 'approved', 14990.00);
"""

def seed_sqlite():
    db_path = Path(Config.SQLITE_DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    with conn:
        conn.executescript(SQLITE_SCHEMA)
        conn.executescript(SQLITE_SEED)
    print(f"SQLite database initialized and seeded successfully at: {db_path}")

if __name__ == "__main__":
    seed_sqlite()
