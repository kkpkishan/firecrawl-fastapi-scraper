"""
Database Connection and Session Management

Handles async database connections using SQLAlchemy with asyncpg driver.
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool
from sqlalchemy import text
import os
import logging
from typing import AsyncGenerator

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
    if they don't already exist. It also creates necessary indexes.
    """
    try:
        logger.info("Initializing database...")
        
        async with engine.begin() as conn:
            # Create all tables defined in Base metadata
            await conn.run_sync(Base.metadata.create_all)
            
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


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency function to get database session.
    
    Yields an async database session and ensures it's closed after use.
    Use this with FastAPI's Depends() for automatic session management.
    
    Example:
        @app.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db)):
            result = await db.execute(select(Item))
            return result.scalars().all()
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
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
    content_snippet: str
):
    """
    Create a new crawl result.
    
    Args:
        db: Database session
        job_id: UUID of the parent job
        page_url: URL of the page
        page_title: Title of the page
        content_snippet: Content containing the keyword
        
    Returns:
        Created CrawlResult object
    """
    from models import CrawlResult
    
    result = CrawlResult(
        job_id=job_id,
        page_url=page_url,
        page_title=page_title,
        content_snippet=content_snippet
    )
    
    db.add(result)
    await db.commit()
    await db.refresh(result)
    
    return result
