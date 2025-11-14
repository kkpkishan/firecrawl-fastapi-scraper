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

from database import init_db, close_db, check_db_connection, get_db, create_job, update_job_status, get_job_by_id, create_result
from config import settings
from auth import verify_api_key
from schemas import CrawlRequest, CrawlResponse, CrawlStatusResponse, ResultItem, ErrorResponse

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
            keyword=request.keyword
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


async def process_crawl_job(job_id: str, url: str, keyword: str):
    """
    Background task to process a crawl job.
    
    This function:
    1. Calls Firecrawl API to start the crawl
    2. Polls Firecrawl for completion
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
            
            # Call Firecrawl API to start crawl
            firecrawl_job_id = await start_firecrawl_job(url)
            
            if not firecrawl_job_id:
                logger.error(f"Failed to start Firecrawl job for {job_id}")
                await update_job_status(
                    db, job_id, "failed",
                    error="Failed to start Firecrawl job"
                )
                return
            
            # Store Firecrawl job ID
            await update_job_status(db, job_id, "in_progress", firecrawl_job_id=firecrawl_job_id)
            logger.info(f"Firecrawl job started with ID: {firecrawl_job_id}")
            
            # Poll Firecrawl for completion
            crawled_data = await poll_firecrawl_status(firecrawl_job_id)
            
            if not crawled_data:
                logger.error(f"Failed to retrieve crawl results for job {job_id}")
                await update_job_status(
                    db, job_id, "failed",
                    error="Failed to retrieve crawl results from Firecrawl"
                )
                return
            
            # Extract pages containing keyword
            await extract_and_store_results(db, job_id, crawled_data, keyword)
            
            # Mark job as completed
            await update_job_status(db, job_id, "completed")
            logger.info(f"Job {job_id} completed successfully")
            
        except Exception as e:
            logger.error(f"Error processing job {job_id}: {e}", exc_info=True)
            await update_job_status(
                db, job_id, "failed",
                error=f"Internal error: {str(e)}"
            )


async def start_firecrawl_job(url: str) -> str | None:
    """
    Start a Firecrawl crawl job.
    
    Args:
        url: URL to crawl
        
    Returns:
        Firecrawl job ID or None if failed
    """
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
                return data.get("id")
            else:
                logger.error(f"Firecrawl API error: {response.status_code} - {response.text}")
                return None
                
    except Exception as e:
        logger.error(f"Error calling Firecrawl API: {e}", exc_info=True)
        return None


async def poll_firecrawl_status(firecrawl_job_id: str) -> list | None:
    """
    Poll Firecrawl for job completion.
    
    Args:
        firecrawl_job_id: Firecrawl job ID
        
    Returns:
        List of crawled pages or None if failed/timeout
    """
    import asyncio
    from datetime import datetime, timedelta
    
    start_time = datetime.utcnow()
    timeout = timedelta(seconds=settings.crawl_timeout_seconds)
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            while True:
                # Check timeout
                if datetime.utcnow() - start_time > timeout:
                    logger.error(f"Crawl job {firecrawl_job_id} timed out")
                    return None
                
                # Poll Firecrawl status
                response = await client.get(
                    f"{settings.firecrawl_api_url}/v2/crawl/{firecrawl_job_id}"
                )
                
                if response.status_code != 200:
                    logger.error(f"Firecrawl status check failed: {response.status_code}")
                    await asyncio.sleep(settings.polling_interval_seconds)
                    continue
                
                data = response.json()
                status = data.get("status")
                
                if status == "completed":
                    logger.info(f"Firecrawl job {firecrawl_job_id} completed")
                    return data.get("data", [])
                elif status == "failed":
                    logger.error(f"Firecrawl job {firecrawl_job_id} failed")
                    return None
                
                # Still in progress, wait and poll again
                await asyncio.sleep(settings.polling_interval_seconds)
                
    except Exception as e:
        logger.error(f"Error polling Firecrawl status: {e}", exc_info=True)
        return None


async def extract_and_store_results(
    db: AsyncSession,
    job_id: str,
    crawled_data: list,
    keyword: str
):
    """
    Extract pages containing keyword and store results.
    
    Args:
        db: Database session
        job_id: Crawl job ID
        crawled_data: List of crawled pages from Firecrawl
        keyword: Keyword to search for
    """
    keyword_lower = keyword.lower()
    matches_found = 0
    
    for page in crawled_data:
        try:
            # Get page content and metadata
            markdown_content = page.get("markdown", "")
            metadata = page.get("metadata", {})
            page_url = metadata.get("sourceURL", "")
            page_title = metadata.get("title", "")
            
            # Case-insensitive keyword search
            if keyword_lower in markdown_content.lower():
                # Store the result
                await create_result(
                    db,
                    job_id=job_id,
                    page_url=page_url,
                    page_title=page_title,
                    content_snippet=markdown_content
                )
                matches_found += 1
                logger.debug(f"Found keyword in page: {page_url}")
                
        except Exception as e:
            logger.error(f"Error processing page: {e}", exc_info=True)
            continue
    
    logger.info(f"Job {job_id}: Found {matches_found} pages containing keyword '{keyword}'")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
