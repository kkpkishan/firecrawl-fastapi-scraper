"""
Pydantic Schemas for Request and Response Models

Defines data validation and serialization schemas for API endpoints.
"""
from pydantic import BaseModel, HttpUrl, Field, ConfigDict
from typing import List, Optional
from datetime import datetime
from uuid import UUID


class CrawlRequest(BaseModel):
    """
    Request schema for submitting a new crawl job.
    
    Attributes:
        url: The target URL to crawl (must be valid HTTP/HTTPS URL)
        keyword: The search keyword to find in crawled content
    """
    url: HttpUrl = Field(
        ...,
        description="Target URL to crawl (including subpages)",
        examples=["https://example.com"]
    )
    keyword: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Keyword or phrase to search for in crawled content",
        examples=["example", "search term"]
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "url": "https://example.com",
                "keyword": "example"
            }
        }
    )


class CrawlResponse(BaseModel):
    """
    Response schema for crawl job submission.
    
    Attributes:
        job_id: Unique identifier for the crawl job
        status: Current status of the job (typically "started")
    """
    job_id: UUID = Field(
        ...,
        description="Unique identifier for the crawl job"
    )
    status: str = Field(
        ...,
        description="Current status of the job",
        examples=["started", "pending"]
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "job_id": "123e4567-e89b-12d3-a456-426614174000",
                "status": "started"
            }
        }
    )


class ResultItem(BaseModel):
    """
    Schema for a single crawl result item.
    
    Represents a page that contains the search keyword.
    
    Attributes:
        page_url: URL of the page where keyword was found
        page_title: Title of the page (may be None)
        content_snippet: Content snippet or full markdown containing the keyword
    """
    page_url: str = Field(
        ...,
        description="URL of the page where keyword was found"
    )
    page_title: Optional[str] = Field(
        None,
        description="Title of the page (from metadata)"
    )
    content_snippet: str = Field(
        ...,
        description="Content snippet or full markdown containing the keyword"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "page_url": "https://example.com/about",
                "page_title": "About Us - Example",
                "content_snippet": "This is an example of content containing the keyword..."
            }
        }
    )


class CrawlStatusResponse(BaseModel):
    """
    Response schema for crawl job status query.
    
    Provides complete information about a crawl job including
    its status, results, and timing information.
    
    Attributes:
        job_id: Unique identifier for the crawl job
        url: The original URL that was crawled
        keyword: The search keyword
        status: Current status (pending, in_progress, completed, failed)
        results: List of pages containing the keyword (None if not completed)
        error: Error message if job failed (None otherwise)
        created_at: When the job was created
        completed_at: When the job completed (None if still in progress)
    """
    job_id: UUID = Field(
        ...,
        description="Unique identifier for the crawl job"
    )
    url: str = Field(
        ...,
        description="The original URL that was crawled"
    )
    keyword: str = Field(
        ...,
        description="The search keyword"
    )
    status: str = Field(
        ...,
        description="Current status of the job",
        examples=["pending", "in_progress", "completed", "failed"]
    )
    results: Optional[List[ResultItem]] = Field(
        None,
        description="List of pages containing the keyword (only for completed jobs)"
    )
    error: Optional[str] = Field(
        None,
        description="Error message if job failed"
    )
    created_at: datetime = Field(
        ...,
        description="When the job was created"
    )
    completed_at: Optional[datetime] = Field(
        None,
        description="When the job completed (success or failure)"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "job_id": "123e4567-e89b-12d3-a456-426614174000",
                "url": "https://example.com",
                "keyword": "example",
                "status": "completed",
                "results": [
                    {
                        "page_url": "https://example.com/about",
                        "page_title": "About Us",
                        "content_snippet": "Example content..."
                    }
                ],
                "error": None,
                "created_at": "2024-01-01T00:00:00",
                "completed_at": "2024-01-01T00:01:00"
            }
        }
    )


class ErrorResponse(BaseModel):
    """
    Standard error response schema.
    
    Attributes:
        error: Error code or type
        message: Human-readable error message
        details: Additional error details (optional)
    """
    error: str = Field(
        ...,
        description="Error code or type"
    )
    message: str = Field(
        ...,
        description="Human-readable error message"
    )
    details: Optional[dict] = Field(
        None,
        description="Additional error details"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "error": "invalid_url",
                "message": "The provided URL is not valid",
                "details": {"url": "invalid-url"}
            }
        }
    )


class HealthResponse(BaseModel):
    """
    Health check response schema.
    
    Attributes:
        status: Health status (healthy/unhealthy)
        service: Service name
    """
    status: str = Field(
        ...,
        description="Health status",
        examples=["healthy", "unhealthy"]
    )
    service: str = Field(
        ...,
        description="Service name"
    )


class ReadinessResponse(BaseModel):
    """
    Readiness check response schema.
    
    Attributes:
        status: Readiness status (ready/not_ready)
        database: Database connection status
        firecrawl: Firecrawl service status
    """
    status: str = Field(
        ...,
        description="Readiness status",
        examples=["ready", "not_ready"]
    )
    database: str = Field(
        ...,
        description="Database connection status",
        examples=["connected", "unavailable"]
    )
    firecrawl: str = Field(
        ...,
        description="Firecrawl service status",
        examples=["available", "unavailable", "not_implemented"]
    )
