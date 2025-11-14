# Design Document

## Overview

The web scraping backend is a microservices-based system that enables users to submit URLs and keywords for crawling, then retrieve extracted content via a REST API. The architecture leverages FastAPI for the backend API layer, Firecrawl (self-hosted) for web crawling and content extraction, PostgreSQL for data persistence, Redis for task queue management, and Playwright for dynamic content rendering. All components run in Docker containers orchestrated by Docker Compose.

The system follows an asynchronous job processing pattern where API requests return immediately with a job ID, while the actual crawling and processing happens in the background. This design ensures high throughput and responsiveness under load.

## Architecture

### System Components

```mermaid
graph TB
    Client[Client Application]
    API[FastAPI Backend Service]
    FC[Firecrawl API]
    FCW[Firecrawl Workers]
    PG[(PostgreSQL Database)]
    RD[(Redis)]
    PS[Playwright Service]
    
    Client -->|HTTP + API Key| API
    API -->|Create Job| PG
    API -->|Start Crawl| FC
    FC -->|Queue Tasks| RD
    FCW -->|Consume Tasks| RD
    FCW -->|Store Queue State| PG
    FCW -->|Render JS Pages| PS
    FCW -->|Return Results| API
    API -->|Store Results| PG
    API -->|Query Results| PG
    Client -->|Poll Status| API
```

### Component Responsibilities

**FastAPI Backend Service**
- Exposes REST API endpoints for job submission and result retrieval
- Validates incoming requests and enforces API key authentication
- Creates and manages crawl job records in the database
- Delegates crawling tasks to Firecrawl
- Processes crawled content to filter by keyword
- Stores extracted results in the database
- Handles background task processing or webhook callbacks

**Firecrawl Service**
- Receives crawl requests via HTTP API
- Discovers and crawls all subpages within the target domain
- Converts web page content to Markdown format
- Manages crawl tasks using Redis-backed queue system
- Delegates JavaScript-heavy pages to Playwright Service
- Returns crawled content to the Backend Service

**PostgreSQL Database**
- Stores crawl job metadata (crawl_jobs table)
- Stores extracted results with keyword matches (crawl_results table)
- Stores Firecrawl's internal queue state (nuq schema)
- Provides persistent storage with ACID guarantees

**Redis**
- Manages Firecrawl's task queue using Bull queue
- Provides rate limiting for crawl requests
- Enables concurrent processing of multiple crawl jobs

**Playwright Service**
- Renders JavaScript-heavy web pages using headless browser
- Returns fully rendered HTML to Firecrawl workers
- Handles dynamic content that requires browser execution

### Network Architecture

All services run within a Docker network named `backend`. Services communicate using Docker service names as hostnames:
- FastAPI accessible at `fastapi-app:8000` (exposed to host as `localhost:8000`)
- Firecrawl accessible at `firecrawl-api:3002` (exposed to host as `localhost:3002`)
- PostgreSQL accessible at `nuq-postgres:5432`
- Redis accessible at `redis:6379`
- Playwright accessible at `playwright-service:3000`

## Components and Interfaces

### FastAPI Backend Service

**Technology Stack:**
- Python 3.12+
- FastAPI framework for REST API
- SQLAlchemy with async support for database ORM
- httpx for async HTTP client to call Firecrawl
- Pydantic for request/response validation

**API Endpoints:**

1. **POST /crawl**
   - Request Body: `{ "url": "string", "keyword": "string" }`
   - Request Headers: `X-API-Key: <api_key>`
   - Response: `{ "job_id": "uuid", "status": "started" }`
   - Status Codes: 202 (Accepted), 400 (Bad Request), 401 (Unauthorized), 500 (Server Error)

2. **GET /crawl/{job_id}**
   - Request Headers: `X-API-Key: <api_key>`
   - Response (in progress): `{ "job_id": "uuid", "status": "in_progress" }`
   - Response (completed): 
     ```json
     {
       "job_id": "uuid",
       "url": "string",
       "keyword": "string",
       "status": "completed",
       "results": [
         {
           "page_url": "string",
           "page_title": "string",
           "content_snippet": "string"
         }
       ]
     }
     ```
   - Status Codes: 200 (OK), 401 (Unauthorized), 404 (Not Found)

3. **POST /webhook/crawl-complete** (Internal)
   - Receives callbacks from Firecrawl when crawl jobs complete
   - Processes crawled data and stores results
   - Not exposed to external clients

**Authentication Mechanism:**
- API key validation using FastAPI dependency injection
- Reads expected key from `APP_API_KEY` environment variable
- Validates `X-API-Key` header on each request
- Returns 401 if key is missing or incorrect

**Background Processing:**
The system uses FastAPI BackgroundTasks for asynchronous job processing:
1. When a crawl job is submitted, immediately return job ID
2. Add background task to poll Firecrawl for completion
3. Background task polls Firecrawl status endpoint every 5 seconds
4. When completed, retrieve all crawled pages
5. Filter pages by keyword (case-insensitive)
6. Store matching results in database
7. Update job status to "completed"

Alternative: Webhook-based processing where Firecrawl calls back when done (more scalable, requires webhook endpoint setup).

### Firecrawl Integration

**Firecrawl API Calls:**

1. **Start Crawl Job**
   - Endpoint: `POST http://firecrawl-api:3002/v2/crawl`
   - Request Body:
     ```json
     {
       "url": "https://example.com",
       "limit": 10000,
       "scrapeOptions": {
         "formats": ["markdown"]
       }
     }
     ```
   - Response: `{ "success": true, "id": "crawl-job-uuid", "url": "..." }`

2. **Check Crawl Status**
   - Endpoint: `GET http://firecrawl-api:3002/v2/crawl/{crawl_id}`
   - Response:
     ```json
     {
       "status": "completed",
       "data": [
         {
           "markdown": "page content...",
           "metadata": {
             "sourceURL": "https://example.com/page",
             "title": "Page Title"
           }
         }
       ]
     }
     ```

**Firecrawl Configuration:**
- `PORT=3002` - API server port
- `HOST=0.0.0.0` - Listen on all interfaces
- `NUM_WORKERS_PER_QUEUE=8` - Concurrent worker processes
- `REDIS_URL=redis://redis:6379` - Redis connection for queue
- `NUQ_DATABASE_URL=postgres://postgres:postgres@nuq-postgres:5432/postgres` - Database connection
- `USE_DB_AUTHENTICATION=false` - Disable Firecrawl's internal auth
- `PLAYWRIGHT_MICROSERVICE_URL=http://playwright-service:3000/scrape` - Playwright service endpoint

### Database Schema

**Table: crawl_jobs**
```sql
CREATE TABLE crawl_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    input_url TEXT NOT NULL,
    keyword TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'in_progress', 'completed', 'failed')),
    firecrawl_job_id TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP,
    error TEXT
);

CREATE INDEX idx_crawl_jobs_status ON crawl_jobs(status);
CREATE INDEX idx_crawl_jobs_created_at ON crawl_jobs(created_at);
```

**Table: crawl_results**
```sql
CREATE TABLE crawl_results (
    id BIGSERIAL PRIMARY KEY,
    job_id UUID NOT NULL REFERENCES crawl_jobs(id) ON DELETE CASCADE,
    page_url TEXT NOT NULL,
    page_title TEXT,
    content_snippet TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_crawl_results_job_id ON crawl_results(job_id);
```

**Database Connection:**
- Both FastAPI and Firecrawl share the same PostgreSQL instance
- Firecrawl uses the `nuq` schema for its internal tables
- Application uses the `public` schema for crawl_jobs and crawl_results
- Connection pooling via SQLAlchemy async engine
- Connection string: `postgresql+asyncpg://postgres:postgres@nuq-postgres:5432/postgres`

## Data Models

### Pydantic Models (FastAPI)

```python
from pydantic import BaseModel, HttpUrl
from typing import List, Optional
from datetime import datetime
from uuid import UUID

class CrawlRequest(BaseModel):
    url: HttpUrl
    keyword: str

class CrawlResponse(BaseModel):
    job_id: UUID
    status: str

class ResultItem(BaseModel):
    page_url: str
    page_title: Optional[str]
    content_snippet: str

class CrawlStatusResponse(BaseModel):
    job_id: UUID
    url: str
    keyword: str
    status: str
    results: Optional[List[ResultItem]] = None
    error: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
```

### SQLAlchemy Models

```python
from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

class CrawlJob(Base):
    __tablename__ = 'crawl_jobs'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    input_url = Column(Text, nullable=False)
    keyword = Column(Text, nullable=False)
    status = Column(String(20), nullable=False)
    firecrawl_job_id = Column(Text)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime)
    error = Column(Text)
    
    results = relationship("CrawlResult", back_populates="job", cascade="all, delete-orphan")

class CrawlResult(Base):
    __tablename__ = 'crawl_results'
    
    id = Column(BigInteger, primary_key=True)
    job_id = Column(UUID(as_uuid=True), ForeignKey('crawl_jobs.id'), nullable=False)
    page_url = Column(Text, nullable=False)
    page_title = Column(Text)
    content_snippet = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    job = relationship("CrawlJob", back_populates="results")
```

## Error Handling

### Error Categories

1. **Client Errors (4xx)**
   - 400 Bad Request: Invalid URL format, missing required fields
   - 401 Unauthorized: Missing or invalid API key
   - 404 Not Found: Job ID does not exist

2. **Server Errors (5xx)**
   - 500 Internal Server Error: Unexpected application errors
   - 503 Service Unavailable: Database or Firecrawl unavailable

### Error Response Format

```json
{
    "error": "error_code",
    "message": "Human-readable error description",
    "details": {}
}
```

### Error Handling Strategy

**Database Connection Failures:**
- Implement connection retry logic with exponential backoff
- Return 503 if database is unavailable after retries
- Log connection errors for monitoring

**Firecrawl Communication Failures:**
- Retry Firecrawl API calls up to 3 times with 2-second delays
- Mark job as "failed" if Firecrawl is unreachable
- Store error message in job record

**Crawl Failures:**
- If Firecrawl returns error status, mark job as "failed"
- Store Firecrawl's error message in job.error field
- Return failed status to user on status query

**Keyword Processing Errors:**
- Wrap keyword search in try-except blocks
- Log errors but continue processing other pages
- If all pages fail, mark job as "failed"

**Timeout Handling:**
- Set 300-second timeout for crawl jobs
- Background task checks elapsed time on each poll
- Mark job as "failed" with timeout error if exceeded

## Testing Strategy

### Unit Tests

**FastAPI Endpoints:**
- Test API key validation (valid, invalid, missing)
- Test request validation (valid URLs, invalid URLs, missing fields)
- Test response serialization
- Mock database and Firecrawl calls

**Keyword Extraction:**
- Test case-insensitive matching
- Test with special characters in keyword
- Test with multi-word keywords
- Test with no matches found

**Database Operations:**
- Test job creation and retrieval
- Test result insertion and querying
- Test cascade deletion of results when job deleted

### Integration Tests

**End-to-End Crawl Flow:**
- Submit crawl job with test URL
- Poll status until completed
- Verify results contain expected pages
- Verify keyword matches are accurate

**Firecrawl Integration:**
- Test communication with Firecrawl API
- Test handling of Firecrawl responses
- Test error handling when Firecrawl fails

**Database Integration:**
- Test with real PostgreSQL instance
- Verify data persistence across restarts
- Test concurrent job processing

### Load Tests

**Concurrency Testing:**
- Submit 100 concurrent crawl jobs
- Verify all jobs complete successfully
- Measure response times and throughput
- Monitor resource usage (CPU, memory, database connections)

**Scalability Testing:**
- Test with large websites (1000+ pages)
- Test with many small jobs vs few large jobs
- Identify bottlenecks and optimization opportunities

### Docker Environment Tests

**Container Startup:**
- Verify all containers start without errors
- Test service discovery and networking
- Verify environment variable configuration

**Data Persistence:**
- Stop and restart containers
- Verify database data persists
- Verify jobs can be queried after restart

## Deployment Configuration

### Docker Compose Structure

```yaml
version: '3.8'

services:
  fastapi-app:
    build: ./app
    ports:
      - "8000:8000"
    environment:
      - APP_API_KEY=${APP_API_KEY}
      - DB_URL=postgresql+asyncpg://postgres:postgres@nuq-postgres:5432/postgres
    depends_on:
      - nuq-postgres
      - firecrawl-api
    networks:
      - backend

  firecrawl-api:
    build: ./firecrawl/apps/api
    ports:
      - "3002:3002"
    environment:
      - PORT=3002
      - HOST=0.0.0.0
      - NUM_WORKERS_PER_QUEUE=8
      - REDIS_URL=redis://redis:6379
      - REDIS_RATE_LIMIT_URL=redis://redis:6379
      - NUQ_DATABASE_URL=postgres://postgres:postgres@nuq-postgres:5432/postgres
      - USE_DB_AUTHENTICATION=false
      - PLAYWRIGHT_MICROSERVICE_URL=http://playwright-service:3000/scrape
    depends_on:
      - nuq-postgres
      - redis
      - playwright-service
    networks:
      - backend

  nuq-postgres:
    build: ./firecrawl/apps/nuq-postgres
    ports:
      - "5432:5432"
    environment:
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=postgres
      - POSTGRES_DB=postgres
    volumes:
      - nuq-data:/var/lib/postgresql/data
    networks:
      - backend

  redis:
    image: redis:alpine
    ports:
      - "6379:6379"
    networks:
      - backend

  playwright-service:
    build: ./firecrawl/apps/playwright-service-ts
    environment:
      - PORT=3000
    networks:
      - backend

networks:
  backend:
    driver: bridge

volumes:
  nuq-data:
```

### Environment Variables (.env)

```
# FastAPI Configuration
APP_API_KEY=your-secure-random-api-key-here

# Database Configuration
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=postgres

# Firecrawl Configuration
NUM_WORKERS_PER_QUEUE=8
USE_DB_AUTHENTICATION=false
```

### Dockerfile for FastAPI App

```dockerfile
FROM python:3.13-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Performance Tuning

**Firecrawl Workers:**
- Increase `NUM_WORKERS_PER_QUEUE` to 16 or 32 for higher concurrency
- Monitor CPU usage and adjust accordingly
- Consider running multiple Firecrawl instances behind load balancer

**Database Optimization:**
- Configure PostgreSQL shared_buffers to 25% of available RAM
- Enable connection pooling with max 20 connections per service
- Add indexes on frequently queried columns

**Redis Configuration:**
- Use Redis persistence (AOF) if queue state must survive restarts
- Configure maxmemory-policy to allkeys-lru for cache eviction

**FastAPI Optimization:**
- Use Gunicorn with multiple Uvicorn workers for production
- Configure worker count based on CPU cores (2 * cores + 1)
- Enable response compression for large JSON payloads

## Security Considerations

**API Key Management:**
- Generate strong random API keys (32+ characters)
- Store in environment variables, never in code
- Rotate keys periodically
- Consider implementing key expiration

**Network Security:**
- Do not expose Firecrawl port 3002 to public internet in production
- Use internal Docker network for service communication
- Consider adding reverse proxy (nginx) for SSL termination

**Input Validation:**
- Validate URL format and scheme (http/https only)
- Sanitize keyword input to prevent injection attacks
- Limit URL length and keyword length

**Rate Limiting:**
- Implement per-API-key rate limiting (e.g., 100 requests/hour)
- Use Redis for distributed rate limit tracking
- Return 429 Too Many Requests when limit exceeded

**Database Security:**
- Change default PostgreSQL password in production
- Use separate database users with minimal privileges
- Enable SSL for database connections in production
