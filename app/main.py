"""
FastAPI Web Scraping Backend - Main Application
"""
from fastapi import FastAPI, Depends, HTTPException, status, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import ValidationError
import logging
import httpx
from uuid import UUID
import re
from datetime import datetime
from typing import List, Dict, Optional

from database import init_db, close_db, check_db_connection, get_db, create_job, update_job_status, get_job_by_id, create_result
from config import settings
from auth import verify_api_key
from schemas import CrawlRequest, CrawlResponse, CrawlStatusResponse, ResultItem, ErrorResponse
from regex_extractor import get_extractor, extract_with_regex
from nested_scraper import get_nested_scraper
from document_extractor import get_document_extractor

# Configure logging
logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events.
    
    Handles database initialization on startup and cleanup on shutdown.
    """
    # Startup
    logger.info("Starting up application...")
    logger.info(f"Environment: {settings.app_name} v{settings.app_version}")
    logger.info(f"Database URL: {settings.db_url.split('@')[1] if '@' in settings.db_url else 'configured'}")
    logger.info(f"Firecrawl URL: {settings.firecrawl_api_url}")
    
    try:
        await init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down application...")
    try:
        await close_db()
        logger.info("Database connections closed")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


# Initialize FastAPI app with lifespan
app = FastAPI(
    title=settings.app_name,
    description="A scalable web scraping service using FastAPI and Firecrawl",
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=settings.cors_allow_methods,
    allow_headers=settings.cors_allow_headers,
)


@app.get("/")
async def root():
    """Root endpoint - API information"""
    return {
        "message": settings.app_name,
        "version": settings.app_version,
        "status": "running",
        "docs": "/docs",
        "health": "/health",
        "readiness": "/readiness"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint for Docker healthcheck"""
    return {
        "status": "healthy",
        "service": "fastapi-app"
    }


@app.get("/readiness")
async def readiness_check():
    """
    Readiness check - verifies all dependencies are available.
    
    Returns 200 if ready, 503 if not ready.
    """
    # Check database connectivity
    db_status = await check_db_connection()
    
    if not db_status:
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "database": "unavailable",
                "firecrawl": "not_checked"
            }
        )
    
    return {
        "status": "ready",
        "database": "connected",
        "firecrawl": "not_implemented"
    }


@app.post(
    "/crawl",
    response_model=CrawlResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        202: {"description": "Crawl job accepted and started"},
        400: {"model": ErrorResponse, "description": "Invalid request"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    },
    tags=["Crawl"]
)
async def submit_crawl_job(
    request: CrawlRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """
    Submit a new crawl job.
    
    Creates a new crawl job to scrape the specified URL and search for the keyword
    in all crawled pages. The job is processed asynchronously in the background.
    
    Args:
        request: Crawl request with URL and keyword
        background_tasks: FastAPI background tasks
        db: Database session
        api_key: Validated API key
        
    Returns:
        CrawlResponse with job_id and status
        
    Raises:
        HTTPException: 400 if URL is invalid, 500 if job creation fails
    """
    try:
        logger.info(f"Received crawl request for URL: {request.url}")
        
        # Validate URL format (Pydantic HttpUrl already validates basic format)
        url_str = str(request.url)
        if not url_str.startswith(('http://', 'https://')):
            logger.warning(f"Invalid URL scheme: {url_str}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="URL must start with http:// or https://"
            )
        
        # Create new crawl job in database with status "pending"
        job = await create_job(db, url_str, request.keyword)
        logger.info(f"Created crawl job with ID: {job.id}")
        
        # Add background task to process the crawl
        background_tasks.add_task(
            process_crawl_job,
            job_id=str(job.id),
            url=url_str,
            keyword=request.keyword,
            follow_nested=request.follow_nested_urls,
            max_depth=request.max_depth,
            current_depth=0
        )
        
        # Return job_id and status "started"
        return CrawlResponse(
            job_id=job.id,
            status="started"
        )
        
    except HTTPException:
        raise
    except ValidationError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid request: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error creating crawl job: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create crawl job"
        )


@app.post(
    "/crawl/nested/{job_id}",
    response_model=CrawlResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        202: {"description": "Nested crawl job accepted"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        404: {"model": ErrorResponse, "description": "Parent job not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    },
    tags=["Crawl"]
)
async def crawl_nested_urls(
    job_id: UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """
    Crawl nested URLs found in a completed job's results.
    
    This endpoint extracts exam URLs from the results of a completed job
    and creates new crawl jobs for each nested URL to get more detailed information.
    
    Args:
        job_id: UUID of the parent crawl job
        background_tasks: FastAPI background tasks
        db: Database session
        api_key: Validated API key
        
    Returns:
        CrawlResponse with new job_id for nested crawling
    """
    try:
        logger.info(f"Nested crawl requested for parent job {job_id}")
        
        # Get parent job
        parent_job = await get_job_by_id(db, str(job_id))
        
        if not parent_job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Parent job {job_id} not found"
            )
        
        if parent_job.status != "completed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Parent job must be completed. Current status: {parent_job.status}"
            )
        
        # Get results and extract nested URLs
        from database import get_results_by_job_id
        results = await get_results_by_job_id(db, str(job_id))
        
        all_nested_urls = set()
        for result in results:
            urls = extract_urls_from_text(result.content_snippet, result.page_url)
            all_nested_urls.update(urls)
        
        if not all_nested_urls:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No nested exam URLs found in the results"
            )
        
        logger.info(f"Found {len(all_nested_urls)} nested URLs to crawl")
        
        # Create a new job for nested crawling
        # For now, we'll crawl the first nested URL as a demonstration
        first_url = list(all_nested_urls)[0]
        nested_job = await create_job(db, first_url, parent_job.keyword)
        
        # Add background task
        background_tasks.add_task(
            process_crawl_job,
            job_id=str(nested_job.id),
            url=first_url,
            keyword=parent_job.keyword
        )
        
        logger.info(f"Created nested crawl job {nested_job.id} for URL: {first_url}")
        
        return CrawlResponse(
            job_id=nested_job.id,
            status="started"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating nested crawl: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create nested crawl job"
        )


@app.get(
    "/crawl/{job_id}",
    response_model=CrawlStatusResponse,
    responses={
        200: {"description": "Job status retrieved successfully"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        404: {"model": ErrorResponse, "description": "Job not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    },
    tags=["Crawl"]
)
async def get_crawl_status(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """
    Get the status and results of a crawl job.
    
    Retrieves the current status of a crawl job by its ID. If the job is completed,
    includes all pages that contain the search keyword.
    
    Args:
        job_id: UUID of the crawl job
        db: Database session
        api_key: Validated API key
        
    Returns:
        CrawlStatusResponse with job details and results (if completed)
        
    Raises:
        HTTPException: 404 if job not found, 500 if retrieval fails
    """
    try:
        logger.info(f"Retrieving status for job {job_id}")
        
        # Query job by ID
        job = await get_job_by_id(db, str(job_id))
        
        if not job:
            logger.warning(f"Job not found: {job_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job with ID {job_id} not found"
            )
        
        # Build response based on job status
        response_data = {
            "job_id": job.id,
            "url": job.input_url,
            "keyword": job.keyword,
            "status": job.status,
            "created_at": job.created_at,
            "completed_at": job.completed_at,
            "error": job.error
        }
        
        # If job is completed, include results
        if job.status == "completed":
            # Get results from database
            from database import get_results_by_job_id
            results = await get_results_by_job_id(db, str(job_id))
            
            # Convert results to ResultItem format
            response_data["results"] = [
                ResultItem(
                    page_url=result.page_url,
                    page_title=result.page_title,
                    content_snippet=result.content_snippet
                )
                for result in results
            ]
            logger.info(f"Job {job_id} completed with {len(results)} results")
        else:
            response_data["results"] = None
            logger.info(f"Job {job_id} status: {job.status}")
        
        return CrawlStatusResponse(**response_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving job status: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve job status"
        )


async def process_crawl_job(
    job_id: str, 
    url: str, 
    keyword: str,
    follow_nested: bool = False,
    max_depth: int = 1,
    current_depth: int = 0
):
    """
    Background task to process a crawl job with comprehensive error handling and nested crawling.
    
    This function:
    1. Calls Firecrawl API to start the crawl (with retries)
    2. Polls Firecrawl for completion (with timeout)
    3. Extracts pages containing the keyword
    4. Stores results in the database
    
    Args:
        job_id: UUID of the crawl job
        url: URL to crawl
        keyword: Keyword to search for
    """
    # Import here to avoid circular imports
    from database import AsyncSessionLocal
    
    async with AsyncSessionLocal() as db:
        try:
            logger.info(f"Starting background processing for job {job_id}")
            
            # Update job status to "in_progress"
            await update_job_status(db, job_id, "in_progress")
            
            # Call Firecrawl API to start crawl (with retry logic)
            firecrawl_job_id = await start_firecrawl_job(url, max_retries=3)
            
            if not firecrawl_job_id:
                error_msg = "Failed to start Firecrawl job after 3 retry attempts. Firecrawl service may be unavailable."
                logger.error(f"Job {job_id}: {error_msg}")
                await update_job_status(
                    db, job_id, "failed",
                    error=error_msg
                )
                return
            
            # Store Firecrawl job ID
            await update_job_status(db, job_id, "in_progress", firecrawl_job_id=firecrawl_job_id)
            logger.info(f"Firecrawl job started with ID: {firecrawl_job_id}")
            
            # Poll Firecrawl for completion (with timeout and error handling)
            crawled_data, error_message = await poll_firecrawl_status(firecrawl_job_id, job_id)
            
            if not crawled_data:
                error_msg = error_message or "Failed to retrieve crawl results from Firecrawl"
                logger.error(f"Job {job_id}: {error_msg}")
                await update_job_status(
                    db, job_id, "failed",
                    error=error_msg
                )
                return
            
            # Extract pages containing keyword (with nested scraping support)
            await extract_and_store_results(
                db, job_id, crawled_data, keyword,
                follow_nested, max_depth, current_depth
            )
            
            # Mark job as completed
            await update_job_status(db, job_id, "completed")
            logger.info(f"Job {job_id} completed successfully")
            
        except Exception as e:
            error_msg = f"Internal error: {str(e)}"
            logger.error(f"Error processing job {job_id}: {e}", exc_info=True)
            await update_job_status(
                db, job_id, "failed",
                error=error_msg
            )


async def process_nested_web_pages(
    db: AsyncSession,
    parent_job_id: str,
    nested_urls: List[str],
    keyword: str,
    follow_nested: bool,
    max_depth: int,
    current_depth: int
):
    """
    Process nested web page URLs by creating new crawl jobs.
    
    Args:
        db: Database session
        parent_job_id: ID of the parent job
        nested_urls: List of URLs to crawl
        keyword: Keyword to search for
        follow_nested: Whether to continue following nested URLs
        max_depth: Maximum crawling depth
        current_depth: Current depth level
    """
    try:
        logger.info(f"Creating crawl jobs for {len(nested_urls)} nested URLs (depth {current_depth + 1}/{max_depth})")
        
        for nested_url in nested_urls:
            try:
                # Check if already scraped
                nested_scraper = get_nested_scraper()
                if nested_scraper.is_url_scraped(nested_url):
                    logger.info(f"Skipping already scraped URL: {nested_url}")
                    continue
                
                # Create new job for nested URL
                nested_job = await create_job(db, nested_url, keyword)
                logger.info(f"Created nested job {nested_job.id} for URL: {nested_url}")
                
                # Mark as scraped
                nested_scraper.mark_url_scraped(nested_url)
                
                # Process the nested job
                await process_crawl_job_sync(
                    nested_job.id,
                    nested_url,
                    keyword,
                    follow_nested,
                    max_depth,
                    current_depth + 1
                )
                
            except Exception as e:
                logger.error(f"Error processing nested URL {nested_url}: {e}")
                continue
        
        logger.info(f"Completed processing nested web pages for job {parent_job_id}")
        
    except Exception as e:
        logger.error(f"Error in nested web page processing: {e}", exc_info=True)


async def process_nested_urls(
    db: AsyncSession,
    parent_job_id: str,
    keyword: str,
    follow_nested: bool,
    max_depth: int,
    current_depth: int
):
    """
    Process nested URLs found in crawl results automatically.
    
    DEPRECATED: This function is kept for backward compatibility.
    Use extract_and_store_results with follow_nested=True instead.
    
    Args:
        db: Database session
        parent_job_id: ID of the parent job
        keyword: Keyword to search for in nested pages
        follow_nested: Whether to continue following nested URLs
        max_depth: Maximum crawling depth
        current_depth: Current depth level
    """
    logger.warning("process_nested_urls is deprecated. Nested scraping is now handled in extract_and_store_results")


async def process_crawl_job_sync(
    job_id: UUID,
    url: str,
    keyword: str,
    follow_nested: bool,
    max_depth: int,
    current_depth: int
):
    """
    Synchronous version of process_crawl_job for nested crawling.
    
    This ensures nested jobs complete before moving to next level.
    """
    from database import AsyncSessionLocal
    
    async with AsyncSessionLocal() as db:
        try:
            logger.info(f"Processing nested job {job_id} at depth {current_depth}")
            
            await update_job_status(db, str(job_id), "in_progress")
            
            firecrawl_job_id = await start_firecrawl_job(url, max_retries=3)
            
            if not firecrawl_job_id:
                await update_job_status(db, str(job_id), "failed", error="Failed to start Firecrawl")
                return
            
            await update_job_status(db, str(job_id), "in_progress", firecrawl_job_id=firecrawl_job_id)
            
            crawled_data, error_message = await poll_firecrawl_status(firecrawl_job_id, str(job_id))
            
            if not crawled_data:
                await update_job_status(db, str(job_id), "failed", error=error_message or "Failed to retrieve data")
                return
            
            await extract_and_store_results(
                db, str(job_id), crawled_data, keyword,
                follow_nested, max_depth, current_depth
            )
            await update_job_status(db, str(job_id), "completed")
            
        except Exception as e:
            logger.error(f"Error in nested job {job_id}: {e}", exc_info=True)
            await update_job_status(db, str(job_id), "failed", error=str(e))


async def start_firecrawl_job(url: str, max_retries: int = 3) -> str | None:
    """
    Start a Firecrawl crawl job with retry logic.
    
    Args:
        url: URL to crawl
        max_retries: Maximum number of retry attempts
        
    Returns:
        Firecrawl job ID or None if failed
    """
    import asyncio
    
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{settings.firecrawl_api_url}/v2/crawl",
                    json={
                        "url": url,
                        "limit": 10000,
                        "scrapeOptions": {
                            "formats": ["markdown"]
                        }
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    job_id = data.get("id")
                    logger.info(f"Firecrawl job created successfully: {job_id}")
                    return job_id
                else:
                    logger.error(f"Firecrawl API error (attempt {attempt + 1}/{max_retries}): {response.status_code} - {response.text}")
                    if attempt < max_retries - 1:
                        wait_time = 2  # 2 seconds between retries
                        logger.info(f"Retrying Firecrawl API call in {wait_time} seconds...")
                        await asyncio.sleep(wait_time)
                    else:
                        return None
                    
        except httpx.ConnectError as e:
            logger.error(f"Firecrawl connection error (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                wait_time = 2
                logger.info(f"Retrying in {wait_time} seconds...")
                await asyncio.sleep(wait_time)
            else:
                logger.error(f"Firecrawl unreachable after {max_retries} attempts")
                return None
        except Exception as e:
            logger.error(f"Unexpected error calling Firecrawl API: {e}", exc_info=True)
            if attempt < max_retries - 1:
                await asyncio.sleep(2)
            else:
                return None
    
    return None


async def poll_firecrawl_status(firecrawl_job_id: str, job_id: str) -> tuple[list | None, str | None]:
    """
    Poll Firecrawl for job completion with timeout and error handling.
    
    Args:
        firecrawl_job_id: Firecrawl job ID
        job_id: Our internal job ID (for logging)
        
    Returns:
        Tuple of (crawled_data, error_message)
        - crawled_data: List of crawled pages or None if failed
        - error_message: Error description or None if successful
    """
    import asyncio
    from datetime import datetime, timedelta
    
    start_time = datetime.utcnow()
    timeout = timedelta(seconds=settings.crawl_timeout_seconds)
    retry_count = 0
    max_consecutive_errors = 5
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            while True:
                # Check timeout
                elapsed = datetime.utcnow() - start_time
                if elapsed > timeout:
                    error_msg = f"Crawl job timed out after {settings.crawl_timeout_seconds} seconds"
                    logger.error(f"Job {job_id}: {error_msg}")
                    return None, error_msg
                
                try:
                    # Poll Firecrawl status
                    response = await client.get(
                        f"{settings.firecrawl_api_url}/v2/crawl/{firecrawl_job_id}"
                    )
                    
                    if response.status_code == 200:
                        retry_count = 0  # Reset retry count on successful response
                        data = response.json()
                        status = data.get("status")
                        
                        if status == "completed":
                            logger.info(f"Firecrawl job {firecrawl_job_id} completed")
                            return data.get("data", []), None
                        elif status == "failed":
                            error_msg = data.get("error", "Firecrawl job failed")
                            logger.error(f"Firecrawl job {firecrawl_job_id} failed: {error_msg}")
                            return None, f"Firecrawl error: {error_msg}"
                        else:
                            # Still in progress
                            logger.debug(f"Job {job_id} still in progress (elapsed: {elapsed.seconds}s)")
                    else:
                        retry_count += 1
                        logger.warning(f"Firecrawl status check failed: {response.status_code} (retry {retry_count}/{max_consecutive_errors})")
                        
                        if retry_count >= max_consecutive_errors:
                            error_msg = f"Firecrawl status check failed {max_consecutive_errors} times consecutively"
                            logger.error(error_msg)
                            return None, error_msg
                
                except httpx.ConnectError as e:
                    retry_count += 1
                    logger.error(f"Firecrawl connection error (retry {retry_count}/{max_consecutive_errors}): {e}")
                    
                    if retry_count >= max_consecutive_errors:
                        error_msg = "Firecrawl service unreachable"
                        return None, error_msg
                
                except Exception as e:
                    logger.error(f"Error during status polling: {e}", exc_info=True)
                    retry_count += 1
                    
                    if retry_count >= max_consecutive_errors:
                        error_msg = f"Polling error: {str(e)}"
                        return None, error_msg
                
                # Wait before next poll
                await asyncio.sleep(settings.polling_interval_seconds)
                
    except Exception as e:
        error_msg = f"Fatal error polling Firecrawl: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return None, error_msg


def extract_urls_from_text(text: str, base_url: str) -> List[str]:
    """
    Extract ALL URLs from text content dynamically.
    
    No hardcoded keywords - extracts any URL found in the content.
    User's keyword will determine relevance during crawling.
    
    Args:
        text: Content to search for URLs
        base_url: Base URL of the website for relative URL resolution
        
    Returns:
        List of unique URLs found in the content
    """
    urls_found = set()
    from urllib.parse import urlparse
    
    base_parsed = urlparse(base_url)
    base_domain = base_parsed.netloc
    
    # Pattern for URLs in markdown links [text](url)
    markdown_pattern = r'\[([^\]]+)\]\(([^)]+)\)'
    for match in re.finditer(markdown_pattern, text):
        url = match.group(2)
        
        # Skip anchors, javascript, mailto, etc.
        if url.startswith(('#', 'javascript:', 'mailto:', 'tel:')):
            continue
            
        # Handle relative URLs
        if url.startswith('http'):
            # Only include URLs from same domain to avoid external links
            parsed = urlparse(url)
            if parsed.netloc == base_domain:
                urls_found.add(url)
        elif url.startswith('/'):
            full_url = f"{base_parsed.scheme}://{base_domain}{url}"
            urls_found.add(full_url)
    
    # Pattern for direct URLs in text
    url_pattern = r'https?://[^\s\)\]\"\'\<\>]+'
    for match in re.finditer(url_pattern, text):
        url = match.group(0)
        parsed = urlparse(url)
        # Only include URLs from same domain
        if parsed.netloc == base_domain:
            urls_found.add(url)
    
    return list(urls_found)


def extract_structured_patterns(text: str) -> List[Dict[str, str]]:
    """
    Extract structured patterns from text DYNAMICALLY.
    
    Finds common patterns like:
    - Dates (multiple formats)
    - Numbers with context
    - Structured data (key: value pairs)
    - Any repeated patterns
    
    Completely dynamic - no hardcoded assumptions about what to find.
    
    Returns:
        List of dictionaries with 'pattern', 'value', 'context', 'position'
    """
    patterns_found = []
    
    # Pattern 1: Date-like patterns (numbers with separators)
    # Matches: DD/MM/YYYY, DD-MM-YYYY, YYYY-MM-DD, etc.
    date_pattern = r'\b(\d{1,4}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})\b'
    for match in re.finditer(date_pattern, text):
        value = match.group(0)
        start = max(0, match.start() - 100)
        end = min(len(text), match.end() + 100)
        context = text[start:end].strip()
        patterns_found.append({
            'pattern': 'date_like',
            'value': value,
            'context': context,
            'position': match.start()
        })
    
    # Pattern 2: Month names with numbers (flexible date format)
    month_pattern = r'\b(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{2,4})\b'
    for match in re.finditer(month_pattern, text, re.IGNORECASE):
        value = match.group(0)
        start = max(0, match.start() - 100)
        end = min(len(text), match.end() + 100)
        context = text[start:end].strip()
        patterns_found.append({
            'pattern': 'date_with_month',
            'value': value,
            'context': context,
            'position': match.start()
        })
    
    # Pattern 3: Key-value pairs (e.g., "Date: 15/01/2025", "Post: Engineer")
    keyvalue_pattern = r'([A-Za-z\s]+):\s*([^\n\r]{3,50})'
    for match in re.finditer(keyvalue_pattern, text):
        key = match.group(1).strip()
        value = match.group(2).strip()
        start = max(0, match.start() - 50)
        end = min(len(text), match.end() + 50)
        context = text[start:end].strip()
        patterns_found.append({
            'pattern': 'key_value',
            'value': f"{key}: {value}",
            'context': context,
            'position': match.start()
        })
    
    # Pattern 4: Numbers with units or context (e.g., "100 posts", "5 years")
    number_context_pattern = r'\b(\d+)\s+([A-Za-z]+)\b'
    for match in re.finditer(number_context_pattern, text):
        value = match.group(0)
        # Only include if the word after number is meaningful (not just "a", "the", etc.)
        word = match.group(2).lower()
        if len(word) > 2 and word not in ['the', 'and', 'for', 'with']:
            start = max(0, match.start() - 100)
            end = min(len(text), match.end() + 100)
            context = text[start:end].strip()
            patterns_found.append({
                'pattern': 'number_with_context',
                'value': value,
                'context': context,
                'position': match.start()
            })
    
    # Sort by position and remove duplicates
    patterns_found.sort(key=lambda x: x['position'])
    unique_patterns = []
    seen_values = set()
    for pattern_info in patterns_found:
        if pattern_info['value'] not in seen_values:
            seen_values.add(pattern_info['value'])
            unique_patterns.append(pattern_info)
    
    return unique_patterns


def extract_content_near_patterns(text: str, patterns: List[Dict[str, str]]) -> List[Dict[str, any]]:
    """
    Extract meaningful content associated with patterns DYNAMICALLY.
    
    Works with ANY pattern (dates, numbers, key-values, etc.)
    No hardcoded assumptions about content type.
    
    Returns:
        List of dictionaries with 'title', 'value', 'pattern_type', and 'context'
    """
    results = []
    
    for pattern_info in patterns:
        value = pattern_info['value']
        pattern_type = pattern_info['pattern']
        position = pattern_info['position']
        
        # Look for title in surrounding text (200 chars before and after pattern)
        start = max(0, position - 200)
        end = min(len(text), position + 200)
        surrounding_text = text[start:end]
        
        # Extract potential title (look for lines or sentences near the pattern)
        lines = surrounding_text.split('\n')
        title_candidates = []
        
        for line in lines:
            line = line.strip()
            # Skip very short lines, lines that are just the value, or empty lines
            if len(line) < 10 or line == value or not line:
                continue
            # Skip lines that are just numbers or symbols
            if re.match(r'^[\d\s\-\.\,\|]+$', line):
                continue
            # Add meaningful lines as title candidates
            title_candidates.append(line)
        
        # Use the first meaningful title or extract from context
        if title_candidates:
            title = title_candidates[0]
        else:
            # Extract first meaningful sentence from context
            sentences = re.split(r'[.!?\n]+', surrounding_text)
            meaningful_sentences = [s.strip() for s in sentences if len(s.strip()) > 15]
            title = meaningful_sentences[0] if meaningful_sentences else surrounding_text[:100].strip()
        
        # Clean up the title
        title = re.sub(r'\s+', ' ', title)  # Remove extra whitespace
        title = title.replace('|', ' ').replace('*', '').strip()
        
        # Only add if we have a meaningful title
        if title and len(title) > 5:
            results.append({
                'title': title,
                'value': value,
                'pattern_type': pattern_type,
                'context': surrounding_text.strip()
            })
    
    return results


def extract_context_around_keyword(content: str, keyword: str, context_chars: int = 200) -> str:
    """
    Extract context around the keyword from content.
    
    Args:
        content: Full content text
        keyword: Keyword to find
        context_chars: Number of characters to include before and after keyword
        
    Returns:
        Content snippet with context around keyword
    """
    content_lower = content.lower()
    keyword_lower = keyword.lower()
    
    # Find all occurrences of the keyword
    positions = []
    start = 0
    while True:
        pos = content_lower.find(keyword_lower, start)
        if pos == -1:
            break
        positions.append(pos)
        start = pos + 1
    
    if not positions:
        return content[:500] if len(content) > 500 else content
    
    # Extract context around first occurrence
    first_pos = positions[0]
    start_pos = max(0, first_pos - context_chars)
    end_pos = min(len(content), first_pos + len(keyword) + context_chars)
    
    snippet = content[start_pos:end_pos]
    
    # Add ellipsis if truncated
    if start_pos > 0:
        snippet = "..." + snippet
    if end_pos < len(content):
        snippet = snippet + "..."
    
    # Add count if multiple occurrences
    if len(positions) > 1:
        snippet += f"\n\n[Found {len(positions)} occurrences of '{keyword}']"
    
    return snippet


def search_keyword_flexible(content: str, keyword: str) -> tuple[bool, list[str]]:
    """
    Flexible keyword search that handles multiple search patterns.
    
    Searches for:
    - Exact keyword match (case-insensitive)
    - Individual words from multi-word keywords
    - Partial matches
    
    Args:
        content: Content to search in
        keyword: Keyword or phrase to search for
        
    Returns:
        Tuple of (found: bool, matched_terms: list)
    """
    if not content or not keyword:
        return False, []
    
    content_lower = content.lower()
    keyword_lower = keyword.lower()
    matched_terms = []
    
    # 1. Check for exact keyword match
    if keyword_lower in content_lower:
        matched_terms.append(keyword)
        return True, matched_terms
    
    # 2. For multi-word keywords, check if all words are present
    words = keyword_lower.split()
    if len(words) > 1:
        all_words_found = all(word in content_lower for word in words if len(word) > 2)
        if all_words_found:
            matched_terms.extend([word for word in words if word in content_lower])
            return True, matched_terms
    
    # 3. Check for partial matches (at least 70% of keyword length)
    if len(keyword) > 5:
        # Split keyword into chunks and check
        chunk_size = max(4, int(len(keyword) * 0.7))
        for i in range(len(keyword_lower) - chunk_size + 1):
            chunk = keyword_lower[i:i + chunk_size]
            if chunk in content_lower:
                matched_terms.append(chunk)
                return True, matched_terms
    
    return False, []


async def extract_and_store_results(
    db: AsyncSession,
    job_id: str,
    crawled_data: list,
    keyword: str,
    follow_nested: bool = False,
    max_depth: int = 1,
    current_depth: int = 0
):
    """
    Extract pages containing keyword using dynamic regex patterns from .env.
    
    Features:
    - Uses regex patterns configured in .env file
    - Fully dynamic - no hardcoded extraction logic
    - Supports multiple regex patterns simultaneously
    - Extracts key-value pairs based on configured patterns
    - Automatically scrapes nested URLs found in regex matches
    - Extracts content from documents (.pdf, .xlsx, etc.)
    
    Args:
        db: Database session
        job_id: Crawl job ID
        crawled_data: List of crawled pages from Firecrawl
        keyword: Keyword or phrase to search for
        follow_nested: Whether to follow nested URLs
        max_depth: Maximum depth for nested scraping
        current_depth: Current depth level
    """
    matches_found = 0
    pages_processed = 0
    total_patterns_found = 0
    
    # Get extractor instances
    extractor = get_extractor()
    nested_scraper = get_nested_scraper()
    
    # Track all nested URLs found
    all_nested_web_pages = set()
    all_nested_documents = set()
    
    logger.info(f"Job {job_id}: Processing {len(crawled_data)} pages for keyword '{keyword}' (depth {current_depth}/{max_depth})")
    logger.info(f"Regex extraction enabled: {extractor.enabled}")
    logger.info(f"Nested scraping enabled: {follow_nested}")
    
    for page in crawled_data:
        try:
            pages_processed += 1
            
            # Get page content and metadata
            markdown_content = page.get("markdown", "")
            metadata = page.get("metadata", {})
            page_url = metadata.get("sourceURL", "")
            page_title = metadata.get("title", "")
            
            # Skip empty content
            if not markdown_content or len(markdown_content.strip()) < 10:
                logger.debug(f"Skipping page with no content: {page_url}")
                continue
            
            # Flexible keyword search
            found, matched_terms = search_keyword_flexible(markdown_content, keyword)
            
            if found:
                logger.info(f"✓ Keyword '{keyword}' found in: {page_url}")
                
                # Extract structured data using regex patterns from .env
                if extractor.enabled:
                    # Get raw matches for nested URL extraction
                    raw_extracted = extract_with_regex(markdown_content, output_format='raw')
                    extracted_data = extract_with_regex(markdown_content, output_format='keyvalue')
                    
                    # Extract nested URLs from regex matches if enabled
                    if follow_nested and current_depth < max_depth and raw_extracted.get('matches'):
                        nested_urls = nested_scraper.extract_urls_from_regex_matches(
                            raw_extracted['matches'],
                            page_url
                        )
                        all_nested_web_pages.update(nested_urls['web_pages'])
                        all_nested_documents.update(nested_urls['documents'])
                        
                        logger.info(f"  → Found {len(nested_urls['web_pages'])} nested pages and {len(nested_urls['documents'])} documents")
                    
                    if extracted_data.get('enabled') and extracted_data.get('data'):
                        key_value_pairs = extracted_data['data']
                        total_patterns_found += len(key_value_pairs)
                        
                        # Store each extracted key-value pair
                        for item in key_value_pairs:
                            data_key = item['key']
                            data_value = item['value']
                            pattern_type = item.get('pattern_type', 'unknown')
                            context = item.get('context', '')
                            
                            # Build content snippet for display
                            content_snippet = f"KEY: {data_key}\nVALUE: {data_value}\nTYPE: {pattern_type}"
                            if context:
                                content_snippet += f"\nCONTEXT: {context}"
                            
                            # Store as individual result with key-value pairs
                            await create_result(
                                db,
                                job_id=job_id,
                                page_url=page_url,
                                page_title=page_title or "No Title",
                                content_snippet=content_snippet,
                                data_key=data_key,
                                data_value=data_value
                            )
                            matches_found += 1
                        
                        logger.info(f"  → Extracted {len(key_value_pairs)} patterns using regex from .env")
                    else:
                        # No patterns matched, store keyword context
                        logger.info(f"  → No regex patterns matched, storing keyword context")
                        data_key = f"Keyword Match: {keyword}"
                        data_value = extract_context_around_keyword(markdown_content, keyword, context_chars=300)
                        
                        content_snippet = f"KEY: {data_key}\nVALUE: {data_value}"
                        
                        await create_result(
                            db,
                            job_id=job_id,
                            page_url=page_url,
                            page_title=page_title or "No Title",
                            content_snippet=content_snippet,
                            data_key=data_key,
                            data_value=data_value
                        )
                        matches_found += 1
                else:
                    # Regex extraction disabled, store keyword context only
                    logger.info(f"  → Regex extraction disabled, storing keyword context")
                    data_key = f"Keyword Match: {keyword}"
                    data_value = extract_context_around_keyword(markdown_content, keyword, context_chars=300)
                    
                    content_snippet = f"KEY: {data_key}\nVALUE: {data_value}"
                    
                    await create_result(
                        db,
                        job_id=job_id,
                        page_url=page_url,
                        page_title=page_title or "No Title",
                        content_snippet=content_snippet,
                        data_key=data_key,
                        data_value=data_value
                    )
                    matches_found += 1
            else:
                logger.debug(f"No keyword match in: {page_url}")
                
        except Exception as e:
            logger.error(f"Error processing page {page_url}: {e}", exc_info=True)
            continue
    
    logger.info(f"Job {job_id}: Processed {pages_processed} pages, found {matches_found} matches with {total_patterns_found} regex patterns extracted")
    
    # Process nested URLs if enabled
    if follow_nested and current_depth < max_depth:
        # Process documents first (they don't create new crawl jobs)
        if all_nested_documents:
            logger.info(f"Processing {len(all_nested_documents)} nested documents...")
            for doc_url in list(all_nested_documents)[:20]:  # Limit to 20 documents
                try:
                    await nested_scraper.process_document_url(
                        db, job_id, doc_url, keyword, ""
                    )
                except Exception as e:
                    logger.error(f"Error processing document {doc_url}: {e}")
                    continue
        
        # Process nested web pages (create new crawl jobs)
        if all_nested_web_pages:
            logger.info(f"Processing {len(all_nested_web_pages)} nested web pages...")
            await process_nested_web_pages(
                db, job_id, list(all_nested_web_pages)[:10],  # Limit to 10 pages
                keyword, follow_nested, max_depth, current_depth
            )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
