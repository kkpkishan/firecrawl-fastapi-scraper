# Requirements Document

## Introduction

This document specifies the requirements for a web scraping backend service that enables users to submit URLs and keywords for crawling, then retrieve extracted content via a REST API. The system leverages Firecrawl (an open-source web crawler) to scrape websites including subpages, searches for user-specified keywords within the crawled content, stores results in a PostgreSQL database, and exposes the data through authenticated API endpoints. The solution is designed to handle thousands of concurrent crawl jobs with high performance and accuracy.

## Glossary

- **Backend Service**: The FastAPI application that orchestrates crawling jobs and serves results via REST API
- **Firecrawl**: An open-source web crawling and scraping service that fetches web pages and converts them to structured formats (Markdown/JSON)
- **Crawl Job**: A user-initiated task to scrape a specific URL and search for a keyword within the crawled content
- **Job ID**: A unique identifier assigned to each crawl job for tracking and retrieval
- **Keyword**: A search string provided by the user to locate within crawled web content
- **API Key**: A secret token used to authenticate requests to the Backend Service
- **PostgreSQL Database**: The relational database storing crawl job metadata and extracted results
- **Redis**: An in-memory data store used by Firecrawl for task queue management and caching
- **Playwright Service**: A microservice that renders JavaScript-heavy web pages using a headless browser
- **Docker Compose**: A tool for defining and running the multi-container application stack

## Requirements

### Requirement 1

**User Story:** As a user, I want to submit a URL and keyword to initiate a web scraping job, so that I can extract relevant content from that website

#### Acceptance Criteria

1. WHEN a user sends a POST request to the crawl endpoint with a valid URL and keyword, THE Backend Service SHALL create a new crawl job record in the PostgreSQL Database
2. WHEN a user sends a POST request to the crawl endpoint with a valid URL and keyword, THE Backend Service SHALL return a unique Job ID within 2 seconds
3. WHEN a user sends a POST request without a valid API Key, THE Backend Service SHALL reject the request with HTTP status 401
4. WHEN a user sends a POST request with an invalid URL format, THE Backend Service SHALL reject the request with HTTP status 400
5. WHEN the Backend Service creates a crawl job, THE Backend Service SHALL initiate a crawl request to Firecrawl with the provided URL

### Requirement 2

**User Story:** As a user, I want the system to crawl the entire website including subpages, so that I can find my keyword across all accessible pages

#### Acceptance Criteria

1. WHEN Firecrawl receives a crawl request, THE Firecrawl SHALL fetch the main page and discover all linked subpages within the same domain
2. WHEN Firecrawl crawls a website, THE Firecrawl SHALL convert each page content to Markdown format
3. WHERE a page contains JavaScript-rendered content, THE Firecrawl SHALL utilize the Playwright Service to render the page before extraction
4. WHEN Firecrawl completes crawling all discovered pages, THE Firecrawl SHALL provide the extracted content to the Backend Service
5. WHEN Firecrawl encounters an error accessing a URL, THE Firecrawl SHALL log the error and continue processing remaining pages

### Requirement 3

**User Story:** As a user, I want the system to search for my keyword in the crawled content, so that I can identify which pages contain relevant information

#### Acceptance Criteria

1. WHEN the Backend Service receives crawled content from Firecrawl, THE Backend Service SHALL search each page for the user-specified Keyword using case-insensitive matching
2. WHEN a page contains the Keyword, THE Backend Service SHALL extract the page URL, page title, and content containing the Keyword
3. WHEN a page contains the Keyword, THE Backend Service SHALL store the extracted information in the crawl_results table with a reference to the Job ID
4. WHEN no pages contain the Keyword, THE Backend Service SHALL mark the crawl job as completed with zero results
5. WHEN the Backend Service completes processing all crawled pages, THE Backend Service SHALL update the crawl job status to "completed" in the PostgreSQL Database

### Requirement 4

**User Story:** As a user, I want to retrieve the results of my crawl job via an API, so that I can access the extracted data in JSON format

#### Acceptance Criteria

1. WHEN a user sends a GET request to the crawl status endpoint with a valid Job ID and API Key, THE Backend Service SHALL return the current job status
2. WHEN a crawl job is still in progress, THE Backend Service SHALL return a response with status "in_progress"
3. WHEN a crawl job is completed, THE Backend Service SHALL return a JSON response containing the Job ID, URL, Keyword, status "completed", and an array of results
4. WHEN a crawl job has failed, THE Backend Service SHALL return a response with status "failed" and an error message
5. WHEN a user requests a non-existent Job ID, THE Backend Service SHALL return HTTP status 404

### Requirement 5

**User Story:** As a system administrator, I want all components to run in Docker containers, so that I can deploy and scale the system consistently

#### Acceptance Criteria

1. THE Backend Service SHALL run as a Docker container built from a Dockerfile using Python 3.12 or higher
2. THE Firecrawl SHALL run as a Docker container with its API server and worker processes
3. THE PostgreSQL Database SHALL run as a Docker container with persistent volume storage for data
4. THE Redis SHALL run as a Docker container for Firecrawl's queue management
5. THE Playwright Service SHALL run as a Docker container for rendering dynamic web content
6. WHEN all containers are started via Docker Compose, THE Backend Service SHALL be accessible on port 8000 and Firecrawl on port 3002

### Requirement 6

**User Story:** As a system administrator, I want to configure the system using environment variables, so that I can manage secrets and settings securely

#### Acceptance Criteria

1. THE Backend Service SHALL read the API Key from an environment variable named APP_API_KEY
2. THE Backend Service SHALL read the database connection URL from an environment variable
3. THE Firecrawl SHALL read Redis connection details from environment variables REDIS_URL and REDIS_RATE_LIMIT_URL
4. THE Firecrawl SHALL read PostgreSQL connection details from environment variable NUQ_DATABASE_URL
5. WHEN environment variables are not set, THE Backend Service SHALL fail to start with a clear error message

### Requirement 7

**User Story:** As a user, I want the system to handle multiple concurrent crawl jobs, so that I can process thousands of URLs efficiently

#### Acceptance Criteria

1. WHEN multiple users submit crawl requests simultaneously, THE Backend Service SHALL accept all requests and return unique Job IDs within 2 seconds each
2. WHEN Firecrawl receives multiple crawl jobs, THE Firecrawl SHALL process them concurrently using its worker queue system
3. THE Firecrawl SHALL support at least 8 concurrent worker processes per queue as configured by NUM_WORKERS_PER_QUEUE
4. WHEN the system is processing 100 concurrent crawl jobs, THE Backend Service SHALL maintain response times under 3 seconds for status queries
5. THE PostgreSQL Database SHALL handle concurrent read and write operations from multiple crawl jobs without data corruption

### Requirement 8

**User Story:** As a user, I want my API requests to be authenticated, so that only authorized clients can access the scraping service

#### Acceptance Criteria

1. WHEN a user sends a request without the X-API-Key header, THE Backend Service SHALL reject the request with HTTP status 401
2. WHEN a user sends a request with an incorrect API Key, THE Backend Service SHALL reject the request with HTTP status 401
3. WHEN a user sends a request with a valid API Key, THE Backend Service SHALL process the request normally
4. THE Backend Service SHALL compare the provided API Key with the configured APP_API_KEY environment variable
5. THE Backend Service SHALL not log or expose the API Key in error messages or responses

### Requirement 9

**User Story:** As a developer, I want the system to persist crawl results in a database, so that I can retrieve historical data without re-crawling

#### Acceptance Criteria

1. THE PostgreSQL Database SHALL contain a table named crawl_jobs with columns for id, input_url, keyword, status, firecrawl_job_id, created_at, completed_at, and error
2. THE PostgreSQL Database SHALL contain a table named crawl_results with columns for id, job_id, page_url, page_title, content_snippet, and created_at
3. WHEN a crawl job is created, THE Backend Service SHALL insert a new row in the crawl_jobs table with status "pending"
4. WHEN keyword matches are found, THE Backend Service SHALL insert one row per matching page in the crawl_results table
5. WHEN a user queries a completed job, THE Backend Service SHALL retrieve results from the crawl_results table using the Job ID

### Requirement 10

**User Story:** As a system administrator, I want the system to handle errors gracefully, so that failures in one job do not affect other jobs

#### Acceptance Criteria

1. WHEN Firecrawl fails to access a URL, THE Backend Service SHALL mark the job as "failed" and store an error message
2. WHEN the PostgreSQL Database is temporarily unavailable, THE Backend Service SHALL return HTTP status 503 for new requests
3. WHEN Redis is unavailable, THE Firecrawl SHALL log an error and fail to accept new crawl jobs
4. WHEN a crawl job exceeds a timeout of 300 seconds, THE Backend Service SHALL mark the job as "failed" with a timeout error
5. WHEN an error occurs during keyword extraction, THE Backend Service SHALL log the error and mark the job as "failed" without affecting other jobs
