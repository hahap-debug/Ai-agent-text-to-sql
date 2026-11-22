"""
TiDB Cloud Importer Script
Executes data/ecommerce_tidb.sql directly into your TiDB Cloud Serverless cluster.
"""

import os
import sys
import pymysql

SQL_FILE = os.path.join(os.path.dirname(__file__), "data", "ecommerce_tidb.sql")

# Read defaults from .env
DEFAULT_HOST = os.getenv("DB_HOST", "127.0.0.1")
DEFAULT_PORT = int(os.getenv("DB_PORT", "4000"))
DEFAULT_USER = os.getenv("DB_USER", "root")
DEFAULT_PASSWORD = os.getenv("DB_PASSWORD", "")
DEFAULT_DB = os.getenv("DB_NAME", "ecommerce_db")

def main():
    print("=" * 65)
    print(" TiDB Cloud Data Importer")
    print("=" * 65)

    host = os.getenv("TIDB_HOST") or DEFAULT_HOST
    port = int(os.getenv("TIDB_PORT") or DEFAULT_PORT)
    user = os.getenv("TIDB_USER") or DEFAULT_USER
    password = os.getenv("TIDB_PASSWORD") or DEFAULT_PASSWORD
    database = os.getenv("TIDB_DB") or DEFAULT_DB

    print(f"\nTarget Database: {database}")
    print(f"Connecting to TiDB at {host}:{port} as user '{user}'...")
    
    try:
        # Connect with SSL enabled (Required by TiDB Cloud)
        connection = pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            ssl_verify_cert=True,
            ssl_verify_identity=True,
            autocommit=True,
            charset='utf8mb4'
        )
        print(" Connected successfully to TiDB Cloud!")
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return

    print(f"\nReading SQL file: {SQL_FILE}...")
    with open(SQL_FILE, 'r', encoding='utf-8') as f:
        sql_content = f.read()

    # Split statements safely by semicolon
    statements = []
    current = []

    for line in sql_content.splitlines():
        trimmed = line.strip()
        if not trimmed or trimmed.startswith("--"):
            continue
        current.append(line)
        if trimmed.endswith(";"):
            statements.append("\n".join(current))
            current = []

    print(f"Total statements to execute: {len(statements)}")
    print("Starting execution...\n")

    success_count = 0
    with connection.cursor() as cursor:
        for idx, stmt in enumerate(statements, 1):
            first_words = " ".join(stmt.strip().split()[:4])
            try:
                cursor.execute(stmt)
                success_count += 1
                if idx % 10 == 0 or idx == len(statements):
                    print(f"[{idx:2d}/{len(statements)}] Executed: {first_words}...")
            except Exception as e:
                print(f"❌ Error at [{idx}/{len(statements)}] ({first_words}): {e}")

    print("\n" + "=" * 65)
    print(f" Import Completed! Successfully executed {success_count}/{len(statements)} statements.")
    print("=" * 65)
    connection.close()

if __name__ == "__main__":
    main()
