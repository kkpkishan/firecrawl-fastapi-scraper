#!/usr/bin/env python3
"""
Database migration script for crawl_results table
Handles multiple migrations in sequence
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


async def migrate_data_key_value(conn):
    """Migration 1: Add data_key and data_value columns"""
    print("\n=== Migration 1: data_key and data_value columns ===")
    
    # Check if columns already exist
    result = await conn.fetch("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'crawl_results' 
        AND column_name IN ('data_key', 'data_value')
    """)
    
    existing_columns = [row['column_name'] for row in result]
    
    if 'data_key' in existing_columns and 'data_value' in existing_columns:
        print("✓ Columns already exist, skipping")
        return
    
    print("Adding columns...")
    
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
    
    print("✓ Migration 1 completed")


async def migrate_bedrock_fields(conn):
    """Migration 2: Add Bedrock LLM extraction fields"""
    print("\n=== Migration 2: Bedrock LLM extraction fields ===")
    
    # Check if columns already exist
    result = await conn.fetch("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'crawl_results' 
        AND column_name IN ('raw_llm_output', 'normalized_data', 'extraction_method')
    """)
    
    existing_columns = [row['column_name'] for row in result]
    
    if all(col in existing_columns for col in ['raw_llm_output', 'normalized_data', 'extraction_method']):
        print("✓ Bedrock columns already exist, skipping")
        return
    
    print("Adding Bedrock columns...")
    
    # Add raw_llm_output column
    if 'raw_llm_output' not in existing_columns:
        await conn.execute("""
            ALTER TABLE crawl_results 
            ADD COLUMN raw_llm_output TEXT
        """)
        await conn.execute("""
            COMMENT ON COLUMN crawl_results.raw_llm_output IS 
            'Raw JSON output from LLM before normalization'
        """)
        print("✓ Added raw_llm_output column")
    
    # Add normalized_data column
    if 'normalized_data' not in existing_columns:
        await conn.execute("""
            ALTER TABLE crawl_results 
            ADD COLUMN normalized_data TEXT
        """)
        await conn.execute("""
            COMMENT ON COLUMN crawl_results.normalized_data IS 
            'Normalized JSON data matching schema after validation and cleaning'
        """)
        print("✓ Added normalized_data column")
    
    # Add extraction_method column
    if 'extraction_method' not in existing_columns:
        await conn.execute("""
            ALTER TABLE crawl_results 
            ADD COLUMN extraction_method VARCHAR(20) DEFAULT 'bedrock'
        """)
        await conn.execute("""
            COMMENT ON COLUMN crawl_results.extraction_method IS 
            'Method used for extraction: bedrock (LLM), regex (pattern matching), or keyword (simple search)'
        """)
        print("✓ Added extraction_method column")
    
    # Add index on extraction_method
    index_exists = await conn.fetchval("""
        SELECT EXISTS (
            SELECT 1 FROM pg_indexes 
            WHERE tablename = 'crawl_results' 
            AND indexname = 'idx_crawl_results_extraction_method'
        )
    """)
    
    if not index_exists:
        await conn.execute("""
            CREATE INDEX idx_crawl_results_extraction_method 
            ON crawl_results(extraction_method)
        """)
        print("✓ Added index on extraction_method")
    else:
        print("✓ Index already exists")
    
    print("✓ Migration 2 completed")


async def verify_migrations(conn):
    """Verify all migrations were applied successfully"""
    print("\n=== Verifying migrations ===")
    
    result = await conn.fetch("""
        SELECT 
            column_name, 
            data_type, 
            is_nullable,
            column_default
        FROM information_schema.columns
        WHERE table_name = 'crawl_results'
        AND column_name IN (
            'data_key', 'data_value', 
            'raw_llm_output', 'normalized_data', 'extraction_method'
        )
        ORDER BY column_name
    """)
    
    print("\nCurrent schema:")
    for row in result:
        default = row['column_default'] or 'NULL'
        print(f"  - {row['column_name']}: {row['data_type']} (nullable: {row['is_nullable']}, default: {default})")
    
    # Check indexes
    indexes = await conn.fetch("""
        SELECT indexname, indexdef
        FROM pg_indexes
        WHERE tablename = 'crawl_results'
        AND indexname LIKE '%extraction_method%'
    """)
    
    if indexes:
        print("\nIndexes:")
        for idx in indexes:
            print(f"  - {idx['indexname']}")
    
    print("\n✓ All migrations verified")


async def migrate():
    """Run all database migrations"""
    print("=" * 60)
    print("Database Migration Script")
    print("=" * 60)
    print(f"Connecting to: {HOST}:{PORT}/{DATABASE}")
    
    conn = await asyncpg.connect(
        user=USER,
        password=PASSWORD,
        host=HOST,
        port=PORT,
        database=DATABASE
    )
    
    try:
        # Run migrations in sequence
        await migrate_data_key_value(conn)
        await migrate_bedrock_fields(conn)
        await verify_migrations(conn)
        
        print("\n" + "=" * 60)
        print("✓ All migrations completed successfully!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ Migration failed: {e}")
        raise
    finally:
        await conn.close()
        print("\nDatabase connection closed")


if __name__ == "__main__":
    asyncio.run(migrate())
