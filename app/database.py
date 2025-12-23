"""
Database Connection and Session Management

Handles async database connections using SQLAlchemy with asyncpg driver.
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool
from sqlalchemy import text
from sqlalchemy.exc import OperationalError, DBAPIError
import os
import logging
import asyncio
from typing import AsyncGenerator, Optional
from datetime import datetime

from models import Base

# Configure logging
logger = logging.getLogger(__name__)

# Get database URL from environment
DATABASE_URL = os.getenv(
    "DB_URL",
    "postgresql+asyncpg://postgres:postgres@nuq-postgres:5432/postgres"
)

# Create async engine
engine = create_async_engine(
    DATABASE_URL,
    echo=False,  # Set to True for SQL query logging
    pool_pre_ping=True,  # Verify connections before using
    pool_size=10,  # Connection pool size
    max_overflow=20,  # Max overflow connections
    pool_recycle=3600,  # Recycle connections after 1 hour
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def init_db():
    """
    Initialize database by creating all tables.
    
    This function creates the crawl_jobs and crawl_results tables
    if they don't already exist. It also creates necessary indexes
    and runs migrations automatically.
    """
    try:
        logger.info("Initializing database...")
        
        async with engine.begin() as conn:
            # Create all tables defined in Base metadata
            await conn.run_sync(Base.metadata.create_all)
            
            # Run migrations - Add data_key and data_value columns if they don't exist
            logger.info("Running database migrations...")
            
            # Check if columns exist
            result = await conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'crawl_results' 
                AND column_name IN ('data_key', 'data_value')
            """))
            
            existing_columns = [row[0] for row in result.fetchall()]
            
            # Add data_key column if it doesn't exist
            if 'data_key' not in existing_columns:
                logger.info("Adding data_key column to crawl_results table...")
                await conn.execute(text("""
                    ALTER TABLE crawl_results 
                    ADD COLUMN data_key TEXT
                """))
                logger.info("✓ Added data_key column")
            
            # Add data_value column if it doesn't exist
            if 'data_value' not in existing_columns:
                logger.info("Adding data_value column to crawl_results table...")
                await conn.execute(text("""
                    ALTER TABLE crawl_results 
                    ADD COLUMN data_value TEXT
                """))
                logger.info("✓ Added data_value column")
            
            if existing_columns and len(existing_columns) == 2:
                logger.info("✓ Migration columns already exist, skipping")
            
            # Add tags column if it doesn't exist
            result = await conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'crawl_jobs' 
                AND column_name = 'tags'
            """))
            
            tags_column_exists = result.fetchone() is not None
            
            if not tags_column_exists:
                logger.info("Adding tags column to crawl_jobs table...")
                await conn.execute(text("""
                    ALTER TABLE crawl_jobs 
                    ADD COLUMN tags TEXT DEFAULT '[]'
                """))
                logger.info("✓ Added tags column")
            else:
                logger.info("✓ Tags column already exists, skipping")
            
            # Create indexes for performance
            # Note: Indexes are defined in the model, but we can add custom ones here
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_crawl_jobs_status 
                ON crawl_jobs(status);
            """))
            
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_crawl_jobs_created_at 
                ON crawl_jobs(created_at DESC);
            """))
            
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_crawl_results_job_id 
                ON crawl_results(job_id);
            """))
            
        logger.info("Database initialized successfully")
        
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise


async def get_db_with_retry(max_retries: int = 3) -> AsyncSession:
    """
    Get database session with retry logic.
    
    Attempts to create a database session with exponential backoff retry logic.
    
    Args:
        max_retries: Maximum number of retry attempts
        
    Returns:
        AsyncSession: Database session
        
    Raises:
        Exception: If all retry attempts fail
    """
    for attempt in range(max_retries):
        try:
            session = AsyncSessionLocal()
            # Test the connection
            await session.execute(text("SELECT 1"))
            return session
        except (OperationalError, DBAPIError) as e:
            logger.warning(f"Database connection attempt {attempt + 1}/{max_retries} failed: {e}")
            if attempt < max_retries - 1:
                # Exponential backoff: 1s, 2s, 4s
                wait_time = 2 ** attempt
                logger.info(f"Retrying in {wait_time} seconds...")
                await asyncio.sleep(wait_time)
            else:
                logger.error(f"Database connection failed after {max_retries} attempts")
                raise
        except Exception as e:
            logger.error(f"Unexpected error connecting to database: {e}")
            raise


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency function to get database session with retry logic.
    
    Yields an async database session and ensures it's closed after use.
    Use this with FastAPI's Depends() for automatic session management.
    
    Example:
        @app.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db)):
            result = await db.execute(select(Item))
            return result.scalars().all()
    """
    session = None
    try:
        session = await get_db_with_retry(max_retries=3)
        yield session
    except (OperationalError, DBAPIError) as e:
        logger.error(f"Database unavailable: {e}")
        # Re-raise as a more specific error that can be caught by FastAPI
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service is temporarily unavailable. Please try again later."
        )
    finally:
        if session:
            await session.close()


async def check_db_connection() -> bool:
    """
    Check if database connection is working.
    
    Returns:
        bool: True if connection is successful, False otherwise
    """
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("Database connection check: OK")
        return True
    except Exception as e:
        logger.error(f"Database connection check failed: {e}")
        return False


async def close_db():
    """
    Close database connections.
    
    Call this during application shutdown to properly close
    all database connections in the pool.
    """
    try:
        await engine.dispose()
        logger.info("Database connections closed")
    except Exception as e:
        logger.error(f"Error closing database connections: {e}")
        raise


# Database utility functions for common operations

async def get_job_by_id(db: AsyncSession, job_id: str):
    """
    Get a crawl job by ID.
    
    Args:
        db: Database session
        job_id: UUID of the job
        
    Returns:
        CrawlJob object or None if not found
    """
    from models import CrawlJob
    from sqlalchemy import select
    
    result = await db.execute(
        select(CrawlJob).where(CrawlJob.id == job_id)
    )
    return result.scalar_one_or_none()


async def get_results_by_job_id(db: AsyncSession, job_id: str):
    """
    Get all results for a crawl job.
    
    Args:
        db: Database session
        job_id: UUID of the job
        
    Returns:
        List of CrawlResult objects
    """
    from models import CrawlResult
    from sqlalchemy import select
    
    result = await db.execute(
        select(CrawlResult)
        .where(CrawlResult.job_id == job_id)
        .order_by(CrawlResult.created_at)
    )
    return result.scalars().all()


async def create_job(db: AsyncSession, input_url: str, keyword: str):
    """
    Create a new crawl job.
    
    Args:
        db: Database session
        input_url: URL to crawl
        keyword: Keyword to search for
        
    Returns:
        Created CrawlJob object
    """
    from models import CrawlJob
    
    job = CrawlJob(
        input_url=input_url,
        keyword=keyword,
        status='pending'
    )
    
    db.add(job)
    await db.commit()
    await db.refresh(job)
    
    return job


async def update_job_status(
    db: AsyncSession,
    job_id: str,
    status: str,
    error: str = None,
    firecrawl_job_id: str = None
):
    """
    Update job status and related fields.
    
    Args:
        db: Database session
        job_id: UUID of the job
        status: New status value
        error: Error message (optional)
        firecrawl_job_id: Firecrawl job ID (optional)
    """
    from models import CrawlJob
    from sqlalchemy import select, update
    from datetime import datetime
    
    stmt = (
        update(CrawlJob)
        .where(CrawlJob.id == job_id)
        .values(status=status)
    )
    
    if error:
        stmt = stmt.values(error=error)
    
    if firecrawl_job_id:
        stmt = stmt.values(firecrawl_job_id=firecrawl_job_id)
    
    if status in ['completed', 'failed']:
        stmt = stmt.values(completed_at=datetime.utcnow())
    
    await db.execute(stmt)
    await db.commit()


async def create_result(
    db: AsyncSession,
    job_id: str,
    page_url: str,
    page_title: str,
    content_snippet: str,
    data_key: str = None,
    data_value: str = None,
    raw_llm_output: str = None,
    normalized_data: str = None,
    extraction_method: str = None
):
    """
    Create a new crawl result.
    
    Args:
        db: Database session
        job_id: UUID of the parent job
        page_url: URL of the page
        page_title: Title of the page
        content_snippet: Content containing the keyword
        data_key: Key/title of extracted data (optional)
        data_value: Value of extracted data (optional)
        raw_llm_output: Raw JSON output from LLM before normalization (optional)
        normalized_data: Normalized JSON data matching schema (optional)
        extraction_method: Method used for extraction: 'bedrock', 'regex', or 'keyword' (optional)
        
    Returns:
        Created CrawlResult object
    """
    from models import CrawlResult
    
    result = CrawlResult(
        job_id=job_id,
        page_url=page_url,
        page_title=page_title,
        content_snippet=content_snippet,
        data_key=data_key,
        data_value=data_value,
        raw_llm_output=raw_llm_output,
        normalized_data=normalized_data,
        extraction_method=extraction_method
    )
    
    db.add(result)
    await db.commit()
    await db.refresh(result)
    
    return result


async def get_jobs_by_date_range(
    db: AsyncSession,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
):
    """
    Get list of crawl jobs filtered by date range, ordered by creation time (newest first).
    
    Args:
        db: Database session
        start_date: Filter jobs created on or after this date (optional)
        end_date: Filter jobs created on or before this date (optional)
        
    Returns:
        Tuple of (jobs_list, total_count)
    """
    from models import CrawlJob
    from sqlalchemy import select, func, and_
    
    # Build query with date filters
    conditions = []
    
    if start_date:
        conditions.append(CrawlJob.created_at >= start_date)
    
    if end_date:
        conditions.append(CrawlJob.created_at <= end_date)
    
    # Get total count
    if conditions:
        count_stmt = select(func.count()).select_from(CrawlJob).where(and_(*conditions))
    else:
        count_stmt = select(func.count()).select_from(CrawlJob)
    
    total_result = await db.execute(count_stmt)
    total_count = total_result.scalar()
    
    # Get jobs
    if conditions:
        stmt = (
            select(CrawlJob)
            .where(and_(*conditions))
            .order_by(CrawlJob.created_at.desc())
        )
    else:
        stmt = (
            select(CrawlJob)
            .order_by(CrawlJob.created_at.desc())
        )
    
    result = await db.execute(stmt)
    jobs = result.scalars().all()
    
    return jobs, total_count


async def get_jobs_paginated(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20
):
    """
    Get paginated list of crawl jobs ordered by creation time (newest first).
    
    DEPRECATED: Use get_jobs_by_date_range instead.
    
    Args:
        db: Database session
        page: Page number (1-indexed)
        page_size: Number of items per page
        
    Returns:
        Tuple of (jobs_list, total_count)
    """
    from models import CrawlJob
    from sqlalchemy import select, func
    
    # Calculate offset
    offset = (page - 1) * page_size
    
    # Get total count
    count_stmt = select(func.count()).select_from(CrawlJob)
    total_result = await db.execute(count_stmt)
    total_count = total_result.scalar()
    
    # Get paginated jobs
    stmt = (
        select(CrawlJob)
        .order_by(CrawlJob.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    
    result = await db.execute(stmt)
    jobs = result.scalars().all()
    
    return jobs, total_count


async def delete_job_by_id(db: AsyncSession, job_id: str):
    """
    Delete a crawl job by ID (cascade deletes associated results).
    
    Args:
        db: Database session
        job_id: UUID of the job to delete
        
    Returns:
        True if job was deleted, False if job not found
        
    Raises:
        ValueError: If job is in 'in_progress' status
    """
    from models import CrawlJob
    from sqlalchemy import select, delete
    
    # First check if job exists and get its status
    job = await get_job_by_id(db, job_id)
    
    if not job:
        return False
    
    # Prevent deletion of in-progress jobs
    if job.status == 'in_progress':
        raise ValueError("Cannot delete job that is currently in progress")
    
    # Delete the job (cascade will delete associated results)
    stmt = delete(CrawlJob).where(CrawlJob.id == job_id)
    await db.execute(stmt)
    await db.commit()
    
    return True

