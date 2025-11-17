#!/usr/bin/env python3
"""
Database migration script to add data_key and data_value columns
"""
import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

# Get database connection details
DB_URL = os.getenv("DB_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/postgres")

# Parse connection string
# Format: postgresql+asyncpg://user:password@host:port/database
parts = DB_URL.replace("postgresql+asyncpg://", "").split("@")
user_pass = parts[0].split(":")
host_port_db = parts[1].split("/")
host_port = host_port_db[0].split(":")

USER = user_pass[0]
PASSWORD = user_pass[1]
HOST = host_port[0]
PORT = int(host_port[1])
DATABASE = host_port_db[1]


async def migrate():
    """Add data_key and data_value columns to crawl_results table"""
    print("Connecting to database...")
    conn = await asyncpg.connect(
        user=USER,
        password=PASSWORD,
        host=HOST,
        port=PORT,
        database=DATABASE
    )
    
    try:
        print("Checking if columns exist...")
        
        # Check if columns already exist
        result = await conn.fetch("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'crawl_results' 
            AND column_name IN ('data_key', 'data_value')
        """)
        
        existing_columns = [row['column_name'] for row in result]
        
        if 'data_key' in existing_columns and 'data_value' in existing_columns:
            print("✓ Columns already exist, no migration needed")
        else:
            print("Adding new columns...")
            
            if 'data_key' not in existing_columns:
                await conn.execute("""
                    ALTER TABLE crawl_results 
                    ADD COLUMN data_key TEXT
                """)
                print("✓ Added data_key column")
            
            if 'data_value' not in existing_columns:
                await conn.execute("""
                    ALTER TABLE crawl_results 
                    ADD COLUMN data_value TEXT
                """)
                print("✓ Added data_value column")
            
            print("✓ Migration completed successfully")
        
    except Exception as e:
        print(f"✗ Migration failed: {e}")
        raise
    finally:
        await conn.close()
        print("Database connection closed")


if __name__ == "__main__":
    asyncio.run(migrate())
