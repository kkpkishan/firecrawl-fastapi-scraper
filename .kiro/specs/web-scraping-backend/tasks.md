# Implementation Plan

- [x] 1. Set up Firecrawl service configuration
  - Configure Firecrawl environment variables in .env file (PORT, HOST, NUM_WORKERS_PER_QUEUE, REDIS_URL, NUQ_DATABASE_URL, USE_DB_AUTHENTICATION, PLAYWRIGHT_MICROSERVICE_URL)
  - Create Docker Compose service definitions for firecrawl-api, nuq-postgres, redis, and playwright-service
  - Configure service dependencies and networking in Docker Compose
  - _Requirements: 5.2, 5.3, 5.4, 5.5, 6.3, 6.4_

- [x] 2. Create database schema and models
- [x] 2.1 Define SQLAlchemy models for crawl_jobs and crawl_results tables
  - Write CrawlJob model with id, input_url, keyword, status, firecrawl_job_id, created_at, completed_at, error fields
  - Write CrawlResult model with id, job_id, page_url, page_title, content_snippet, created_at fields
  - Configure relationship between CrawlJob and CrawlResult models
  - _Requirements: 9.1, 9.2_

- [x] 2.2 Create database initialization and migration logic
  - Write database connection setup using SQLAlchemy async engine
  - Implement table creation logic on application startup
  - Add database indexes for performance (job_id, status, created_at)
  - _Requirements: 9.1, 9.2, 9.3_

- [x] 3. Implement FastAPI application structure
- [x] 3.1 Create FastAPI app with basic configuration
  - Initialize FastAPI application instance
  - Configure CORS settings if needed
  - Set up application startup and shutdown event handlers
  - Configure database connection on startup
  - _Requirements: 5.1, 6.1, 6.2_

- [x] 3.2 Implement API key authentication dependency
  - Create verify_api_key dependency function that validates X-API-Key header
  - Read APP_API_KEY from environment variables
  - Return 401 Unauthorized for missing or invalid API keys
  - _Requirements: 1.3, 8.1, 8.2, 8.3, 8.4_

- [x] 3.3 Define Pydantic request and response models
  - Create CrawlRequest model with url and keyword fields
  - Create CrawlResponse model with job_id and status fields
  - Create ResultItem model with page_url, page_title, content_snippet fields
  - Create CrawlStatusResponse model with job details and results array
  - _Requirements: 1.1, 4.1, 4.2, 4.3_

- [x] 4. Implement POST /crawl endpoint
- [x] 4.1 Create crawl job submission handler
  - Validate incoming request using CrawlRequest Pydantic model
  - Validate URL format and reject invalid URLs with 400 status
  - Create new crawl_jobs record with status "pending" and generate UUID
  - Return job_id and status "started" with 202 Accepted status
  - _Requirements: 1.1, 1.2, 1.4, 9.3_

- [x] 4.2 Integrate Firecrawl API call to start crawl
  - Use httpx AsyncClient to POST to Firecrawl's /v2/crawl endpoint
  - Send payload with url, limit, and scrapeOptions (formats: ["markdown"])
  - Store returned Firecrawl job ID in crawl_jobs.firecrawl_job_id field
  - Handle Firecrawl connection errors and mark job as failed if unreachable
  - _Requirements: 1.5, 2.1, 10.2_

- [x] 4.3 Implement background task for crawl result processing
  - Add FastAPI BackgroundTask to poll Firecrawl for completion
  - Implement polling loop that checks Firecrawl status endpoint every 5 seconds
  - Retrieve crawled page data when status is "completed"
  - Handle pagination if Firecrawl returns data in chunks with "next" links
  - Update job status to "in_progress" when background processing starts
  - _Requirements: 2.4, 7.1, 7.2_

- [ ] 5. Implement keyword extraction and result storage
- [ ] 5.1 Create keyword search logic
  - Iterate through all crawled pages returned by Firecrawl
  - Perform case-insensitive search for keyword in page markdown content
  - Extract page URL from metadata.sourceURL and page title from metadata.title
  - Extract content snippet containing the keyword (full markdown or context around keyword)
  - _Requirements: 3.1, 3.2_

- [ ] 5.2 Store matching results in database
  - Insert crawl_results record for each page containing the keyword
  - Store job_id, page_url, page_title, and content_snippet
  - Update crawl_jobs status to "completed" and set completed_at timestamp
  - Handle case where no pages contain keyword (mark completed with zero results)
  - _Requirements: 3.3, 3.4, 3.5, 9.4_

- [ ] 6. Implement GET /crawl/{job_id} endpoint
- [ ] 6.1 Create job status retrieval handler
  - Query crawl_jobs table by job_id UUID
  - Return 404 Not Found if job_id does not exist
  - Return status "in_progress" if job is not yet completed
  - Query crawl_results table for completed jobs and include results array
  - Return status "failed" with error message if job failed
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 9.5_

- [ ] 7. Implement error handling and timeout logic
- [ ] 7.1 Add database connection error handling
  - Implement connection retry logic with exponential backoff (3 retries)
  - Return 503 Service Unavailable if database is unreachable after retries
  - Log database connection errors for monitoring
  - _Requirements: 10.2_

- [ ] 7.2 Add Firecrawl communication error handling
  - Retry Firecrawl API calls up to 3 times with 2-second delays
  - Mark job as "failed" and store error message if Firecrawl is unreachable
  - Handle Firecrawl error responses and store error details in job record
  - _Requirements: 10.1, 10.5_

- [ ] 7.3 Implement crawl job timeout mechanism
  - Add timeout check in background polling loop (300 seconds)
  - Calculate elapsed time from job created_at on each poll iteration
  - Mark job as "failed" with timeout error message if time exceeded
  - _Requirements: 10.4_

- [ ] 8. Create Docker Compose configuration
- [ ] 8.1 Write docker-compose.yaml with all service definitions
  - Define fastapi-app service with build context and port mapping (8000:8000)
  - Define firecrawl-api service with environment variables and dependencies
  - Define nuq-postgres service with volume for data persistence
  - Define redis service using redis:alpine image
  - Define playwright-service with build context
  - Create backend network for service communication
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

- [ ] 8.2 Create Dockerfile for FastAPI application
  - Use python:3.13-slim base image
  - Copy requirements.txt and install dependencies
  - Copy application code to /app directory
  - Set CMD to run uvicorn with host 0.0.0.0 and port 8000
  - _Requirements: 5.1_

- [ ] 8.3 Create .env.example file with required environment variables
  - Document APP_API_KEY variable for FastAPI authentication
  - Document database connection variables (POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB)
  - Document Firecrawl configuration variables (NUM_WORKERS_PER_QUEUE, USE_DB_AUTHENTICATION)
  - Add comments explaining each variable's purpose
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [ ] 9. Add logging and monitoring
- [ ] 9.1 Implement structured logging
  - Configure Python logging with JSON formatter
  - Log job creation events with job_id and input parameters
  - Log Firecrawl API calls and responses
  - Log keyword extraction results (pages found, matches count)
  - Log errors with full stack traces and context
  - _Requirements: 10.5_

- [ ] 9.2 Add health check endpoints
  - Create GET /health endpoint that returns 200 OK
  - Create GET /readiness endpoint that checks database connectivity
  - Return 503 from readiness endpoint if database is unavailable
  - _Requirements: 10.2_

- [ ] 10. Write integration tests
- [ ] 10.1 Create end-to-end test for successful crawl flow
  - Submit crawl job with test URL and keyword
  - Poll status endpoint until job completes
  - Verify results contain expected pages with keyword matches
  - Verify database records are created correctly
  - _Requirements: 1.1, 1.2, 2.4, 3.3, 4.3_

- [ ] 10.2 Create test for authentication failures
  - Test POST /crawl without API key (expect 401)
  - Test POST /crawl with invalid API key (expect 401)
  - Test GET /crawl/{job_id} without API key (expect 401)
  - _Requirements: 8.1, 8.2_

- [ ] 10.3 Create test for error scenarios
  - Test with invalid URL format (expect 400)
  - Test with non-existent job_id (expect 404)
  - Test job timeout scenario
  - Test Firecrawl unavailable scenario
  - _Requirements: 1.4, 4.5, 10.1, 10.4_

- [ ] 11. Create documentation
- [ ] 11.1 Write README.md with setup instructions
  - Document prerequisites (Docker, Docker Compose)
  - Provide step-by-step setup instructions
  - Document environment variable configuration
  - Include example API requests with curl commands
  - Add troubleshooting section for common issues
  - _Requirements: 5.6, 6.5_

- [ ] 11.2 Create API documentation
  - Document all endpoints with request/response examples
  - Document authentication requirements
  - Document error codes and their meanings
  - Include example workflows for common use cases
  - _Requirements: 1.1, 1.2, 4.1, 4.2, 4.3, 4.4_
