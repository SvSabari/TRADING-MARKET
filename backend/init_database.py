"""
Database Table Initializer Script.
Run this script to explicitly create all required tables in MySQL:
    python backend/init_database.py
"""
import sys
import os
import asyncio

# Ensure backend directory is in python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db import init_db, engine, Base
import models  # noqa: F401

async def main():
    print(f"Connecting to MySQL engine ({engine.url.render_as_string(hide_password=True)})...")
    print(f"Discovered {len(Base.metadata.sorted_tables)} tables in models:")
    for t in Base.metadata.sorted_tables:
        print(f"  - {t.name}")
    print("\nCreating tables if they do not exist...")
    await init_db()
    print("[SUCCESS] All MySQL database tables created/verified successfully!")

if __name__ == "__main__":
    asyncio.run(main())
