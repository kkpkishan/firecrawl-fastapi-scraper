Web Scraping Backend Design (FastAPI + Firecrawl Integration)
Use Case Overview

The goal is to build a backend service that scrapes a given website URL for a specific keyword or string and provides the extracted information via an API. The user will send a request containing a target URL and a search keyword. The backend will crawl the entire website (including subpages) for that URL using Firecrawl – an open-source web crawler – to collect content. It will then search for the provided keyword within the crawled content, store the relevant data in a database, and make it available through a REST API. This allows other applications to query the API with the job ID (or URL+keyword) and retrieve the data in JSON format. The system is intended to handle this process at scale (potentially thousands of URLs and keywords concurrently) with high performance and accuracy.

Requirements and MVP Features

User Input & Job Creation: The user can submit a URL and a keyword/string. This triggers the creation of a crawl job to process that URL.

Website Crawling: The backend uses Firecrawl (self-hosted, no API key needed) to scrape the given URL and all accessible subpages
github.com
. If the keyword appears in deeper pages (sub-links of the base URL), those pages should also be crawled and analyzed.

Data Extraction: From the crawled data, extract the content relevant to the user’s keyword. Ensure that we capture sufficient context (e.g. the paragraph or section containing the keyword) or the whole page content if needed.

Data Storage: Store the extracted information in a PostgreSQL database. This includes storing metadata like the page URL, page title (if available), the content snippet or markdown containing the keyword, and a reference to the crawl job. This persistence allows reuse of data and avoids re-crawling the same content unnecessarily
blog.csdn.net
blog.csdn.net
.

Data Retrieval API: Provide an API endpoint for retrieving the stored results. Other applications can call this API (with proper authentication) using the job ID or other identifier to get the JSON-formatted data.

Concurrency & Performance: The system should be production-ready and tuned for performance. It must handle many crawl jobs in parallel (scaling to thousands of URLs at a time) without significant degradation. Firecrawl’s architecture uses a queue with Redis and worker processes to manage large-scale crawling, enabling high concurrency
github.com
blog.csdn.net
. We will leverage this design for scalability.

Environment & Deployment: Use Docker and Docker Compose to containerize all components (FastAPI app, Firecrawl services, PostgreSQL, Redis, etc.) for easy deployment. A single Compose file will orchestrate all resources. Environment-specific settings (database URLs, API keys, etc.) will be stored in a .env file for easy configuration.

Authentication: Protect the API endpoints with a simple API key mechanism. Clients must include a valid API key (defined in the environment) in their requests to access the data.

Technology Stack

Python 3.12+ (FastAPI Framework): The backend API will be implemented in Python (targeting Python 3.12/3.13 for latest features and performance). We will use FastAPI to create a RESTful API, due to its speed, intuitive syntax, and support for asynchronous operations and background tasks.

Firecrawl (Self-Hosted): Firecrawl is a powerful open-source web crawling and scraping service
github.com
. We will run Firecrawl locally via Docker. Firecrawl can fetch pages (including dynamic, JavaScript-rendered content) and output them in LLM-ready formats like Markdown or JSON
github.com
. It automatically discovers subpages (no sitemap needed) and handles complexities like proxies, JS, and anti-bot measures. Using Firecrawl locally avoids the need for an external API key and gives us full control over the scraping process.

PostgreSQL Database: All scraped results and job metadata will be stored in a PostgreSQL database. We will reuse Firecrawl’s Postgres instance provided in its Docker setup, rather than running a separate DB container (to simplify the architecture and avoid duplication)
blog.csdn.net
. The database will serve two purposes: Firecrawl’s internal queue/tasks storage and our application’s data storage (we can use separate schemas or tables for our data).

Redis: A Redis instance will be used by Firecrawl for caching and managing task queues (using Bull queue under the hood)
blog.csdn.net
blog.csdn.net
. This enables orchestrating multiple crawl jobs in parallel and rate limiting. Our FastAPI app itself might not use Redis directly, but it benefits from Firecrawl’s queue-based architecture for handling many concurrent crawling tasks.

Docker & Docker-Compose: Docker will be used to containerize the FastAPI app and all required services. Docker Compose will define and run the multi-container setup (FastAPI app, Firecrawl API/worker, PostgreSQL, Redis, etc.) as one cohesive application stack. This ensures consistent environments for development, testing, and production, and makes scaling or deploying easier. We’ll also use Docker to run Firecrawl’s auxiliary services like the optional Playwright browser service (for dynamic content) inside the same composition.

Environment Variables (.env): Configuration such as database connection URL, API keys, and service ports will be managed via environment variables (in a .env file). This allows secure and flexible configuration management without hardcoding secrets. For example, Firecrawl’s required env vars (PORT, HOST, REDIS_URL, NUQ_DATABASE_URL, etc.) and our FastAPI app’s settings (like APP_API_KEY) will reside in this file
blog.csdn.net
blog.csdn.net
.

Architecture and Components

The system consists of several connected components, each running in a container. Below is an overview of each component and how they interact:

FastAPI Application (Backend API): This is the core of our service that coordinates the workflow. It exposes endpoints for starting crawl jobs and retrieving results. When a user submits a URL and keyword, the FastAPI app creates a job entry in the database and then delegates the crawling task to Firecrawl. It uses either background tasks or asynchronous callbacks (webhooks) so that the initial API request can return quickly while the heavy scraping work happens in the background
fastapi.tiangolo.com
fastapi.tiangolo.com
. The FastAPI app also post-processes the scraped data (filtering by keyword) and stores the relevant snippets in the database. It enforces security on its endpoints via an API key check.

Firecrawl Service (API & Worker): Firecrawl runs as a service within our stack to handle web crawling and scraping. Under the hood, Firecrawl has an API server (for receiving crawl requests) and worker processes that perform the actual crawling. We will run Firecrawl in self-hosted mode using its Docker setup. The FastAPI app will communicate with Firecrawl’s API (e.g. HTTP calls to Firecrawl’s /v2/crawl endpoint) to submit crawl jobs. Firecrawl will then fetch the URL, follow links up to a certain depth, and extract content in the desired format (we will request Markdown or JSON format for easy processing). Firecrawl leverages Redis for task queue management and uses PostgreSQL to persist queue state and possibly cached results
blog.csdn.net
blog.csdn.net
. Because we run Firecrawl locally with no authentication (its USE_DB_AUTHENTICATION will be false in .env), no API key is needed for our app to call it (Firecrawl will log a warning that auth is bypassed, which is expected in our setup).

PostgreSQL Database: A single Postgres database will be used by both Firecrawl and our application. In Firecrawl’s Docker Compose, the Postgres service (often named nuq-postgres) is set up with default credentials (e.g. user:postgres/password:postgres) and the default database name (postgres)
blog.csdn.net
. Firecrawl uses this DB (with a schema like nuq) to store job queues, crawl metadata, etc. We will also create our own tables in this same database (e.g. in the public schema or a separate schema) to store the extracted data and job info. Using one database container avoids duplication and allows our app to easily join or reference Firecrawl’s data if needed
blog.csdn.net
. The connection string for this DB (e.g. postgres://postgres:postgres@nuq-postgres:5432/postgres) will be provided to Firecrawl via NUQ_DATABASE_URL env variable and similarly used by our FastAPI app to connect
blog.csdn.net
.

Redis: The Redis service will run as an in-memory datastore for Firecrawl, primarily to manage background tasks and caching. Firecrawl’s workers communicate via Redis (using it for the Bull queue and rate limiting)
blog.csdn.net
. We will include a Redis container (using a lightweight redis:alpine image) in our docker-compose. Firecrawl will be configured to use this by setting REDIS_URL=redis://redis:6379 and REDIS_RATE_LIMIT_URL=redis://redis:6379 (pointing to the Redis service on the internal Docker network)
blog.csdn.net
. Our FastAPI app doesn’t directly use Redis, but this is essential for Firecrawl’s scalability (managing thousands of URL crawl jobs concurrently).

Playwright Service (for Dynamic Content): In order to handle JavaScript-rendered content (dynamic websites), Firecrawl can utilize a Playwright microservice. We will enable this in our setup so that if a page requires a headless browser to fully load content, Firecrawl can delegate that rendering to the Playwright service. Firecrawl’s compose file includes a playwright-service container (by default using a Node/Playwright implementation). We may use the TypeScript variant as recommended
docs.firecrawl.dev
docs.firecrawl.dev
. We will set the environment variable PLAYWRIGHT_MICROSERVICE_URL=http://playwright-service:3000/scrape (assuming the service runs on port 3000 in the container) in Firecrawl’s environment. This allows Firecrawl to call the Playwright service internally for pages that need it. Including this component ensures complete dynamic content scraping as required (the system will not be limited to static HTML) – Firecrawl will attempt normal fetch first and fall back to Playwright for heavy JS if needed, so the crawling is comprehensive.

Docker Compose Configuration: All the above services will be defined in a single docker-compose.yaml for a unified deployment. We will have a Docker service for each: fastapi-app, firecrawl-api (and possibly a firecrawl-worker if separate), nuq-postgres, redis, and playwright-service. Each service will join a common Docker network (e.g., backend) to communicate by name. For example, the FastAPI container can reach Firecrawl at http://firecrawl-api:3002 internally, and Firecrawl will reach the database at nuq-postgres:5432 as per its config
blog.csdn.net
. The Compose file will also handle volume mounting: e.g., mounting a volume for Postgres data (nuq-data) so that the database persists data across restarts
blog.csdn.net
, and optionally mounting our code into the FastAPI container for live development (so we can edit code without rebuilding the image each time, speeding up development). We will expose the FastAPI and Firecrawl API ports to the host for testing (e.g., FastAPI on localhost:8000 and Firecrawl on localhost:3002).

Data Flow Summary

To illustrate how everything works together, here’s the step-by-step flow of a typical request through the system:

Job Submission (API Request): A client (user or another app) sends an HTTP request to our FastAPI backend (e.g., POST /crawl) with a JSON payload containing the url to scrape and the keyword to find. This request must include a valid API key (e.g., in headers) for authentication.

Job Initialization: FastAPI receives the request, verifies the API key, and records a new “job” in the database (e.g., in a crawl_jobs table) with status “pending” or “in-progress”. This record stores the input URL, keyword, timestamp, and a generated job ID.

Triggering Firecrawl: The FastAPI app then submits the URL to Firecrawl for crawling. There are two possible approaches here:

Synchronous wait: For simplicity, the app could call Firecrawl’s API and wait for the crawl to finish, then get the data. However, this would make the API call slow and tie up resources.

Asynchronous job (preferred): The app will call Firecrawl’s /v2/crawl endpoint to start the crawl without waiting for completion. Firecrawl will immediately enqueue the crawl job in its system and return a job ID (different from our own job ID)
docs.firecrawl.dev
docs.firecrawl.dev
. We then handle completion asynchronously.

We’ll implement the async pattern using FastAPI BackgroundTasks or Firecrawl’s webhooks. Using FastAPI’s BackgroundTasks, we can return a response to the client immediately and let a background thread handle the crawl result processing once ready
fastapi.tiangolo.com
fastapi.tiangolo.com
. Alternatively, we can leverage Firecrawl’s webhook feature: we provide a callback URL (an endpoint in our FastAPI app like /webhook/crawl-complete) when starting the crawl
docs.firecrawl.dev
. Firecrawl will then POST back to that URL when the crawl is completed (with event type crawl.completed)
firecrawl.dev
firecrawl.dev
. For the MVP, we might start with background polling for simplicity and consider using webhooks as an optimization.

Immediate Response: Having started the crawl job, the FastAPI endpoint immediately responds to the client with a JSON containing our job_id (and maybe a message like "Crawl started"). This allows the client to proceed without waiting. The response could be HTTP 202 Accepted, indicating the process is ongoing.

Crawling in Progress (Firecrawl): Firecrawl’s worker processes fetch the main page and recursively crawl subpages up to a limit. It converts page content to the specified format. We will request at least Markdown output (clean text) and possibly include raw HTML or JSON if needed for parsing. Firecrawl is designed to handle multiple pages concurrently and use caching, etc., so it should efficiently gather the data. For large websites, Firecrawl may pageinate the results (it returns data in chunks if very large, with a next URL to fetch the next chunk)
docs.firecrawl.dev
docs.firecrawl.dev
. We ensure our background task or webhook handler can handle this (by following any next links until all data is retrieved).

Receiving Crawl Results: Once Firecrawl has finished crawling, we obtain the results:

In a polling setup, our background task would periodically check Firecrawl’s status endpoint (e.g., GET /v2/crawl/<firecrawlJobId>) until it reports "status": "completed" and provides the full data (or the final chunk of data)
docs.firecrawl.dev
docs.firecrawl.dev
. We then collect all pages’ data.

In a webhook setup, Firecrawl will send the results to our webhook endpoint. The payload for a crawl.completed event typically includes either the data directly or an ID to fetch the data. According to Firecrawl’s docs, the completed event allows us to know it’s done (and we might call a final GET to retrieve data if not included in the webhook)
firecrawl.dev
docs.firecrawl.dev
. For MVP, assume we can get the data in one of these ways.

Filtering and Storing Data: After obtaining the crawled content (which likely includes an array of pages with their text), our code will filter this data to find the keyword occurrences. Each page’s content can be searched for the keyword (case-insensitive match). For any page that contains the keyword, we create an entry in a results table in the database. For example, a crawl_results table might have columns: id, job_id (linking to the crawl_jobs table), page_url, page_title, and content_snippet. The content_snippet could be the paragraph or line containing the keyword, or possibly the full page content in Markdown/JSON if we want to store it (depending on how much data we want to save). Storing the entire Markdown content for matched pages ensures we have full context for later use, at the cost of more storage. We also update the job record status to "completed" and maybe store a completion timestamp. If no occurrences were found, we might still mark completed but possibly indicate zero results.

Result Retrieval (API): The client (or another system) can query the API to get the results. We will provide an endpoint (e.g., GET /crawl/{job_id}) which returns the status and data. If the job is still in progress, it might return status "pending". If completed, it returns a JSON object with the keyword and an array of results (each containing page URL, title, snippet/content, etc.). For example:

{
  "job_id": "12345",
  "url": "http://example.com",
  "keyword": "sample",
  "status": "completed",
  "results": [
    {
      "page_url": "http://example.com/about",
      "page_title": "About Us - Example",
      "content_snippet": "… sample text around the keyword …"
    },
    {
      "page_url": "http://example.com/contact",
      "page_title": "Contact - Example",
      "content_snippet": "… sample text around the keyword …"
    }
  ]
}


This data is returned in JSON format as required. The API will likely allow filtering by job ID. In future, one might allow retrieving by original URL + keyword, but job ID is simpler and unique.

Subsequent Use: The scraped and stored data can now be used by other applications or services. For instance, an analytics platform could call our API to get all occurrences of a product name across the target site, etc. Because the data is persisted, repeated requests for the same job ID can be served quickly from the database without re-crawling.

Throughout this flow, we must consider error handling: if Firecrawl fails to crawl (e.g., site not reachable or blocked), or if no data is found, the job should be marked as failed or completed with zero results accordingly. The API should convey that status to the user (perhaps through a "status": "failed" field and an error message).

Database Schema Design

We will use PostgreSQL to create the necessary tables for tracking jobs and storing results. Below is a proposed schema (simplified):

Table: crawl_jobs – to track each crawl request.

id (PK, UUID or bigserial): Unique job identifier (we can use a UUID or numeric ID).

input_url (text): The base URL that was crawled.

keyword (text): The search string we looked for.

status (text or enum): Job status (pending, in_progress, completed, failed).

firecrawl_job_id (text): The ID returned by Firecrawl for its internal tracking (in case we need to query status or logs).

created_at (timestamp): Request time.

completed_at (timestamp): Completion time (null if not completed yet).

(Optional) error (text): Error message if the job failed.

Table: crawl_results – to store occurrences of the keyword in crawled pages (multiple rows per job possible).

id (PK, bigserial): Unique ID for each result record.

job_id (FK -> crawl_jobs.id): Reference back to the crawl job.

page_url (text): URL of the page where the keyword was found.

page_title (text): Title of that page (if available from metadata).

content_snippet (text or JSONB): The content containing the keyword. This could be a snippet (e.g. a few sentences around the keyword) or full page content in markdown. We might store it as text (markdown) or as JSON (if we want to keep structured data). Note: JSONB is useful if storing structured data, but since Firecrawl gives markdown by default
github.com
, we may just store markdown text.

created_at (timestamp): Timestamp when this record was inserted.

We will likely create an index on job_id in the results table for quick lookup, and possibly an index on keyword if cross-job searching is needed (though each job is separate, so not strictly necessary).

 

Firecrawl’s own database tables (in schema nuq) are created via nuq.sql when the container starts. These include tables for queue management (e.g., nuq.queue_scrape) and others for user/auth if that were enabled. We do not need to modify those; we just add our tables. It’s important to not conflict with Firecrawl’s tables – using distinct table names (and possibly our own schema or a clear naming convention) will avoid any collision.

 

Because we share the DB container, our application will use the same connection info as Firecrawl (likely postgres://postgres:postgres@nuq-postgres:5432/postgres). We can either connect as the same postgres user or create a separate DB user for our app if desired. For simplicity, the postgres user will suffice in development.

API Design

We will design a clean REST API using FastAPI. Key endpoints include:

POST /crawl – Start a new crawl job.
Request: JSON body with { "url": "<target_url>", "keyword": "<search_string>" }. The client must also provide an API key, for example in a header X-API-Key: <key>.
Behavior: The endpoint validates the input, creates a job entry, and initiates the crawl via Firecrawl. If using background tasks, it adds a background task to handle the crawl result processing. Respond immediately with a JSON containing the job_id and a status message. For example: { "job_id": 42, "status": "started" }. HTTP status could be 202 Accepted. In case of input validation failure or other errors (like Firecrawl not reachable), respond with an appropriate error status (400 or 500).

GET /crawl/{job_id} – Get the status and results of a crawl job.
Request: Path parameter job_id. (Also requires the API key in header to authorize.)
Response: If the job is still in progress, return { "job_id": 42, "status": "in_progress" }. If completed, return the structure described earlier, with the results array. If failed, return status "failed" and maybe an error field. If job_id is not found, return 404.
This endpoint enables polling by the client, but in many cases the client can just wait or be notified out-of-band. It’s still useful to retrieve the data after the fact.

(Optional) GET /crawl/{job_id}/results – In case we want a separate endpoint just for results (e.g., to retrieve results without status metadata). This could simply redirect or be an alias for the above.

Webhook Endpoint (internal) – If we implement Firecrawl webhooks, we will have an endpoint like POST /webhook/crawl-complete (the exact path can be decided). This will not be public for external users, but Firecrawl will call it. We’ll secure it either by a secret token or by making it network-internal only. Firecrawl allows setting a secret or signature header for webhooks
docs.firecrawl.dev
docs.firecrawl.dev
. The webhook handler will parse the incoming data (which could include Firecrawl’s job ID and maybe the crawl data or a link to it). It will then perform the same steps as our background task: retrieve all crawl data (if not already included), filter by keyword, and store results, then mark the job complete. Using webhooks means we don’t need to poll Firecrawl; it pushes the data to us. However, to keep the initial implementation straightforward, we might start with polling. The design supports either approach.

Authentication: The APIs (except maybe the webhook) should be protected by an API key. We’ll define an environment variable, e.g. API_KEY="<some_random_string>" in .env. The FastAPI app will include a dependency that checks for the header X-API-Key (or Authorization header) in incoming requests and compares it with the expected key. If missing or incorrect, the request is rejected with 401 Unauthorized. This is a simple method to restrict access to trusted clients. (In the future, one could integrate OAuth or JWT if needed, but an API key suffices for MVP.)

No front-end is being built in this phase; the focus is on backend and API, so all interactions are via HTTP requests and JSON data.

Implementation Plan

This section outlines the concrete steps to build the system. We will proceed in an incremental fashion, testing each part before moving to the next. Using git, we will commit and push code after each small milestone is achieved and tested (following good CI/CD practices).

1. Setting Up Firecrawl (Local Crawling Service)

Read the Firecrawl Documentation: Before coding, ensure we understand Firecrawl’s self-host setup. The official Firecrawl repository and docs provide guidance
github.com
docs.firecrawl.dev
. We have identified that we need Docker, Docker Compose, and certain environment variables configured.

 

Clone the Firecrawl repository: We will include Firecrawl by cloning its GitHub repo (or adding it as a submodule) in our project, or we can use pre-built Docker images if available. Assuming we clone it, we can leverage its docker-compose.yaml as a reference. The Firecrawl repo’s docker-compose.yaml defines services for nuq-postgres, redis, api, etc., and an .env.example for required variables. We should copy apps/api/.env.example to apps/api/.env (or adapt those settings into our own .env)
docs.firecrawl.dev
docs.firecrawl.dev
.

 

Configure Firecrawl .env: Key settings to review/modify:

PORT=3002 and HOST=0.0.0.0 – Firecrawl API will run on port 3002 inside container.

NUM_WORKERS_PER_QUEUE=8 – number of parallel workers (8 is default; we might increase if needed for more concurrency, or leave as is initially).

REDIS_URL=redis://redis:6379 and REDIS_RATE_LIMIT_URL=redis://redis:6379 – these should point to our Redis container (named "redis"). In the Firecrawl docs example, they use localhost:6379 when running outside Docker
docs.firecrawl.dev
, but in Docker Compose we’ll use the service name.

NUQ_DATABASE_URL=postgres://postgres:postgres@nuq-postgres:5432/postgres – configure Postgres connection for Firecrawl
blog.csdn.net
. Our compose will use a service nuq-postgres for the DB, matching this URL. The credentials and DB name are the defaults as shown.

USE_DB_AUTHENTICATION=false – ensures Firecrawl does not expect auth tokens for API calls (since we are not setting up Supabase authentication for it).

Optional feature flags: For dynamic content, set PLAYWRIGHT_MICROSERVICE_URL=http://playwright-service:3000/scrape as discussed, and ensure the compose includes the Playwright service. Also, if we want PDF parsing or other features, we could configure those (e.g. OPENAI_API_KEY if we wanted to use LLM-based extraction, but for now we likely skip that).

We do not set TEST_API_KEY or any Firecrawl API key because we are bypassing their auth system (so any call to our local Firecrawl will work without a key, with a warning logged
docs.firecrawl.dev
).

Place these configurations either in Firecrawl’s .env file or directly in the docker-compose under the environment section for the Firecrawl service. Since we will manage one unified Compose, we might choose to set them in the Compose file for clarity.

 

Include Firecrawl in Docker Compose: We will add services for Firecrawl:

firecrawl-api: build from the Firecrawl source (apps/api Dockerfile). This will start the API server and workers. Ensure it depends on redis and nuq-postgres so those start first. Map port 3002 to host (if we want to test endpoints directly).

nuq-postgres: use the Dockerfile in apps/nuq-postgres to build the image (as per Firecrawl repo). Or use a standard Postgres image initialized with Firecrawl’s SQL. Firecrawl’s Dockerfile sets up the schema by copying nuq.sql into Docker’s init scripts. We'll stick to their build to get the exact schema. Expose port 5432 (we might map it to host 5433 or something if needed to avoid conflict with any local Postgres).

redis: use redis:alpine image as in the docs
blog.csdn.net
. No persistent volume needed for Redis (cache only). Just ensure network access.

playwright-service: build from apps/playwright-service or apps/playwright-service-ts as needed. Expose port 3000 internally (not necessarily mapped to host). This service might require the Playwright dependencies (so the build could take some time). We will follow Firecrawl’s guidance to use the TS version by changing the build context if needed
docs.firecrawl.dev
docs.firecrawl.dev
.

Test Firecrawl Setup: Before integrating with our FastAPI app, we should test that Firecrawl runs correctly. Using Docker Compose, bring up Redis, Postgres, Firecrawl (and Playwright). Check logs to ensure:

Postgres started and initialized (no errors like the one reported in issue #2264; if we hit that, we might patch the SQL as needed).

Redis is running.

Firecrawl API is listening on port 3002 and workers are ready. We should see something like "Server running at 0.0.0.0:3002" or similar, and possibly a Bull queue UI available at /admin/@/queues as the docs mention
docs.firecrawl.dev
.

We can test a simple request: curl -X GET localhost:3002/test which should return "Hello, world!" (Firecrawl’s test endpoint)
docs.firecrawl.dev
. And a test crawl: curl -X POST localhost:3002/v2/crawl -d '{"url":"https://example.com"}' and see if an ID is returned (since we have no API key and disabled auth, it should return an ID if everything is okay).

If using webhooks approach, we won't test that yet, but we know Firecrawl can send events.

Once Firecrawl is confirmed to work, we proceed to the backend app.

2. Developing the FastAPI Application

Project Structure: Create a new FastAPI app (e.g., in a directory app/). Within, have modules for database (models and connection), routes (for the endpoints), and any utility modules (like one for interacting with Firecrawl). We will use an async PostgreSQL client or ORM. SQLAlchemy (with async support) or Tortoise ORM or even raw asyncpg can be used. For MVP, using SQLAlchemy with async session is fine.

 

Database Connection Setup: In our FastAPI startup, connect to the Postgres database. Use the same connection string as Firecrawl (we can get it from environment, e.g., DB_URL=postgres://postgres:postgres@nuq-postgres:5432/postgres). We may use an ORM to define the two tables (crawl_jobs and crawl_results). Define the models and create the tables on startup (or use Alembic migrations for a more robust approach later). Ensure that our app connects after the DB container is ready – in Docker Compose, adding depends_on: [nuq-postgres] for our app service will help. Also possibly wait-for-db logic or use Postgres healthchecks for robustness.

 

Pydantic Schemas: Define Pydantic models for the request and response payloads. For example, CrawlRequest with url and keyword fields for validation, and CrawlResponse or similar for job status/results.

 

API Key Dependency: Add a dependency in FastAPI that raises 401 if the incoming X-API-Key header doesn’t match our configured key. This can be as simple as:

from fastapi import Header, HTTPException
API_KEY = os.getenv("APP_API_KEY")
def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")


Then include Depends(verify_api_key) in our endpoints.

 

POST /crawl Implementation: This endpoint will:

Parse the JSON input (FastAPI/Pydantic does this).

Validate the URL format (we might simply rely on trying Firecrawl – but better to at least ensure it starts with http:// or https://).

Insert a new row in crawl_jobs with status "pending" (or directly "in_progress"). Get the generated job ID.

Call Firecrawl to start the crawl:

Prepare the payload: at minimum {"url": input_url, "limit": 0, "scrapeOptions": {"formats": ["markdown"]} }. (We might omit limit to let it crawl default max pages, or set a high limit like 10000 to effectively no limit. Also, possibly set crawlEntireDomain: false to limit to the given URL’s domain by default, which is usually Firecrawl’s default behavior.)

Webhooks approach: add "webhook": {"url": "<our_app_url>/webhook/crawl-complete", "events": ["completed"]} to the payload
docs.firecrawl.dev
. However, if our app is running in Docker, Firecrawl can reach it via the internal network. We could use the service name (e.g., fastapi-app:8000/webhook/crawl-complete), but Firecrawl might not resolve that if it’s in a different container. It should, if all in same network. Alternatively, since Firecrawl and FastAPI are on the same network, using http://fastapi-app:8000/... as webhook URL should work. We’ll ensure our compose gives the FastAPI service a name that Firecrawl can resolve. We also might include a metadata field in the webhook (like our job_id) so that when we get the callback we know which job it corresponds to
docs.firecrawl.dev
. Firecrawl allows custom metadata in the webhook payload.

Make the HTTP request to Firecrawl. We can do this with Python requests or httpx. Since our FastAPI is async, using httpx.AsyncClient would be ideal. But if using BackgroundTasks, a normal sync requests in a thread is acceptable too. Firecrawl’s API is on http://firecrawl-api:3002/v2/crawl internally (as per our compose naming). No auth header needed (auth disabled). Post the JSON. Expect a response like {"success": true, "id": "some-uuid", "url": ...}
docs.firecrawl.dev
.

If Firecrawl returns an ID, store that in our job record (firecrawl_job_id field).

If Firecrawl call fails (no response or error), mark job as failed and return an error response.

Schedule background processing:

If using BackgroundTasks: After firing the Firecrawl request, we do not wait for completion. Instead, add a background task (via BackgroundTasks.add_task) that will later fetch the results and process them. For example, background_tasks.add_task(process_crawl_results, job_id, keyword). Immediately return the response with job_id.

In process_crawl_results(job_id, keyword): implement a loop to poll Firecrawl for results. It might do:

while True:
    resp = requests.get(f"http://firecrawl-api:3002/v2/crawl/{firecrawl_job_id}")
    data = resp.json()
    if data.get("status") == "completed":
        # Possibly collect data chunks if 'next' key in response
        break
    time.sleep(5)  # wait before polling again


Once completed, filter data["data"] which will be a list of pages (each containing e.g. markdown and metadata). For each page in data: if keyword.lower() is in page["markdown"].lower(), save a result entry with page URL (from metadata.sourceURL) and perhaps the snippet. Snippet can be the full markdown or we can extract the paragraph containing the keyword. A simple way is to find the index of keyword in the markdown text and then take, say, 100 characters around it as context.
Insert those records into crawl_results. Update the crawl_jobs status to "completed" and set completed_at. (All of this logic is running in the background thread, so it won’t delay the API response.)

If using Webhooks: Alternatively, skip the background polling. The Firecrawl API call we made has a webhook set, so Firecrawl will call our /webhook/crawl-complete when done. In that case, our POST /crawl endpoint’s job is done after starting the crawl (we still return job_id). We then rely on the webhook handler to do the filtering and storing. The webhook handler function (FastAPI POST endpoint) will receive Firecrawl’s payload. We verify the signature if provided (for security)
docs.firecrawl.dev
. Then we parse the data. Firecrawl’s webhook might include some or all of the data; if not all, we might have to call Firecrawl’s API to get the data by the job ID (the webhook payload likely includes the crawl id). Then proceed to filter and store just like above. Mark job complete.

Note: For MVP, the background task approach might be easier to implement and debug, as it doesn't require setting up the webhook listener and signature. However, webhooks are more scalable for many concurrent jobs because it avoids constant polling. We could mention that as a future improvement (or implement if time permits).

Logging: The app should log that a job started, perhaps log how many pages were found to contain the keyword, etc., for debugging and monitoring.

GET /crawl/{job_id} Implementation: This is straightforward:

Fetch the job record from DB by ID.

If not found, 404.

If job status is "pending/in_progress", return that status. Optionally include progress info if available (we might not have detailed progress without querying Firecrawl; if we wanted, we could query Firecrawl’s status on the fly here to augment, but that’s extra overhead. Simpler to just give a boolean status).

If completed, query the results table for that job_id. Construct the response JSON with job info and results.

If failed, return status failed and maybe error message.

This completes the main development of the FastAPI app.

 

Testing the FastAPI App Locally: We will run the FastAPI app within the Docker Compose environment to test it:

Use docker-compose up --build to build the FastAPI image (which will include our code, likely using a Python base image 3.13 and installing FastAPI, etc.).

Once up, use docker-compose exec fastapi-app bash to enter the container, run any DB migrations or manually ensure tables created (if not auto-created on startup).

Test using curl or a REST client:

POST localhost:8000/crawl with a test URL and keyword. For example, URL https://example.com, keyword "Example". Include header X-API-Key with our known key. Expect a job_id in response.

Then maybe poll GET localhost:8000/crawl/<job_id> every few seconds. Initially should show in_progress. After Firecrawl finishes (which for example.com is quick), it should show completed with results (if "Example" was found on some page).

Verify the result data makes sense (for example.com, maybe it finds the word "example" on the home page).

Test edge cases: a URL that doesn’t exist (should Firecrawl mark failed? we may have to detect via Firecrawl status that no pages scraped or some error), multiple simultaneous requests (you can try firing off a few jobs at once and see if they all complete).

Check the database directly (using psql or a DB admin tool) to ensure records are being stored as expected.

During development, to speed up the edit-run cycle, we will mount the code directory into the container. In docker-compose for fastapi-app, include:

volumes:
  - ./:/app  # assuming our code is in the current directory and Dockerfile sets /app as workdir


And run Uvicorn in reload mode (or simply restart the container) to reflect changes. This way, we avoid rebuilding the image on every code change. Once tests are okay, then commit the code.

 

After confirming functionality, commit the code to git (ensuring no sensitive info like real API keys are committed – use .env which is typically gitignored).

3. Docker and Deployment Setup

We have mostly covered Docker in earlier steps, but to summarize final deployment considerations:

Dockerfile for FastAPI: Create a Dockerfile for our app, e.g.:

FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]


This will be built as part of docker-compose up --build. Ensure it copies all necessary code. We might include ENV PYTHONUNBUFFERED=1 and such for good measure. If using volumes in dev, the code override is fine; in production, we just wouldn't mount and the image code is used.

Docker-Compose Configuration: Ensure the compose file defines all services:

fastapi-app: build from our Dockerfile, depends_on firecrawl-api, nuq-postgres, redis (and maybe playwright-service). Ports: "8000:8000".

firecrawl-api: build from Firecrawl repo context, depends_on nuq-postgres, redis, playwright-service (if dynamic content is used from start). Ports: "3002:3002".

nuq-postgres: build from Firecrawl’s apps/nuq-postgres or use image if available (but likely build). Ports: "5432:5432" (the host port can be 5432 or another if conflict; 5432 is fine if no other Postgres).

redis: use image, port maybe not exposed (or "6379:6379" if we want host access for debugging, but not necessary).

playwright-service: build context apps/playwright-service-ts (if chosen), depends_on maybe just firecrawl-api or none (Firecrawl will call it when needed). Might not need to expose port to host.

Use a common backend network (as seen in Firecrawl docs) for all. Also configure volumes:

nuq-postgres uses a named volume for data (nuq-data:/var/lib/postgresql/data as in Firecrawl docs
docs.firecrawl.dev
docs.firecrawl.dev
).

We might also want to persist any results or logs, but the DB covers results, and logs can be viewed via docker-compose logs.

.env and Secrets: We will have a single .env file at the project root (or we can reuse Firecrawl’s .env for its stuff and also put our APP_API_KEY there). Docker Compose by default reads a .env file for variable substitution. For instance, we might define the API key there (APP_API_KEY=...). We can also define environment for our app in compose referencing those (e.g., environment: - APP_API_KEY=${APP_API_KEY} so it comes from the .env). Similarly, if we want to easily change the Postgres password or such, define POSTGRES_PASSWORD=postgres etc. However, since we rely on Firecrawl’s expected defaults, we might leave those as constants in compose.

 

The .env should not be committed to git if it contains sensitive data (like API keys). We will add it to .gitignore and provide a .env.example for others to know what to set.

Running & Testing in Docker: After assembling everything, we run docker-compose up --build. The expectation:

All containers start without errors. Firecrawl might take a bit to build and initialize (especially with Playwright).

Once steady, test the end-to-end functionality again through the public interface (FastAPI).

Try a few different sites and keywords to ensure the pipeline works. For example, test a site with multiple pages (maybe a small documentation site) and a keyword you know exists in a subpage to verify the crawling depth works.

Performance Tuning: For production, consider adjusting:

Concurrency: Firecrawl by default will crawl multiple pages in parallel (it uses a queue and multiple workers). The NUM_WORKERS_PER_QUEUE env (set to 8) can be increased if the machine has more CPU cores
docs.firecrawl.dev
. Also, Firecrawl’s maxConcurrency parameter (in crawl options) can be set if we want to limit or expand how many simultaneous requests it makes to a single site
docs.firecrawl.dev
docs.firecrawl.dev
. Careful tuning might be needed to avoid overloading target sites or hitting rate limits.

Batching: Firecrawl has a batch mode for thousands of URLs, but our use case is one base URL at a time (which internally might be tens or hundreds of pages). The system should handle many jobs concurrently. We can run multiple instances of our FastAPI app behind a load balancer if needed, and since all share the same Redis and Postgres, Firecrawl’s queue can be shared (the Firecrawl docs note you can run multiple instances behind a load balancer sharing Redis/Postgres for scale-out
self-host.app
). This is advanced; at MVP we likely stick to one instance but it’s good to know scaling horizontally is possible.

Memory and Timeouts: Crawling large sites can be memory intensive. Firecrawl likely streams data, but if a site is huge, consider setting a limit on pages or a maxDiscoveryDepth (max link depth) to avoid infinite crawl. We can expose these as config or use defaults. Also ensure Firecrawl’s default timeouts (perhaps 30s or so per page) and our polling timeouts are reasonable.

Post-processing performance: Searching for a keyword in text is fast, but doing it for very large text repeatedly could be heavy. We can optimize by converting both text and keyword to lowercase once and using Python’s in which is efficient in C. For extremely large text, consider more sophisticated search or indexing, but not needed initially.

Git Commits: After verifying everything works end-to-end (locally via Docker), we will commit the changes. The commit history should show incremental additions:

Initial project setup (Dockerfile, compose, basic FastAPI app structure).

Integration of Firecrawl (compose services, env configuration).

Database models and migration.

Implemented endpoints.

Added background task or webhook handling.

Testing fixes and performance tweaks.
Each step presumably tested. We only push to repository once tests pass for that step.

Performance and Scalability Considerations

Designing for large scale (thousands of concurrent crawl jobs) requires careful consideration:

Non-blocking Operations: By using background tasks or webhooks, we ensure that the API server threads are not tied up waiting for crawls to finish. The FastAPI main loop can continue handling new requests while previous jobs run in background. This allows better throughput and responsiveness under load (clients don’t time out waiting for long crawls).

Firecrawl’s Queue System: Firecrawl itself is built for scale – it uses a queue backed by PostgreSQL and multiple worker processes to handle many URLs
blog.csdn.net
. It also can throttle requests to avoid hitting a site too aggressively and handle dynamic content in parallel via the Playwright service. We rely on these capabilities to manage heavy workloads. If thousands of jobs are queued, Firecrawl will manage them, and we can always increase NUM_WORKERS_PER_QUEUE or run additional worker containers if needed to consume the queue faster.

Resource Allocation: We should monitor CPU and memory usage of each component. Crawling (especially with Playwright for JS) can be CPU and memory heavy. We can impose limits in Docker Compose (e.g., limit the memory for the Playwright service or number of simultaneous browser instances). PostgreSQL should be tuned with enough memory for cache if we store large volumes of text. Redis should comfortably handle many queue messages (as they are small references, not the content itself).

Data Volume Management: If users crawl very large sites or do it frequently, the database will accumulate a lot of text data. We should consider retention policies or enabling compression on the content (Postgres can compress large text in columns automatically, especially with TOAST for text columns). Alternatively, storing just relevant snippets keeps data smaller. If an application needs full page content, storing everything could be tens of MBs per job for large sites – perhaps in that case, one might store the entire markdown in an object storage instead and only keep references. For now, we'll assume moderate usage or that storing in Postgres is acceptable.

Testing at Scale: We should plan to simulate multiple concurrent requests (e.g., use a load testing tool or simply script to launch, say, 50 jobs at once) and observe system behavior. Check that jobs complete correctly and the results are accurate. Identify any bottlenecks (for example, if background tasks pile up, maybe switch to an external task queue like Celery + RabbitMQ for the FastAPI side; but this adds complexity and might not be needed if Firecrawl + threads suffice).

Threading vs Async: FastAPI background tasks run in a threadpool (for standard def functions) which is fine for I/O-bound tasks like waiting on HTTP responses. Python’s GIL won’t be a big problem since we mostly wait on network calls. If we see thread exhaustion with too many concurrent tasks, we could consider alternative approaches. One could offload post-processing to a separate worker process as well, but likely not needed initially.

Firecrawl Updates: Keep an eye on Firecrawl updates; since it’s an active open-source project, improvements or changes (like needing no API key for self-hosted usage
github.com
) might come that simplify integration. Also ensure using a stable release or commit of Firecrawl to avoid dev branch issues.

Security and Environment Configuration

Security considerations:

API Key Security: We use a simple API key in header for authentication. It’s important to use a strong random key and keep it secret (.env file). Over HTTPS (when deployed), this prevents eavesdropping. If this service is internal (e.g., only other backend services call it), this might be sufficient. Otherwise, consider more robust auth for external exposure.

Firecrawl Access: Our FastAPI app calls the Firecrawl service over the internal Docker network (unexposed to the public). We should ensure Firecrawl’s port (3002) is not publicly accessible in production if we don’t want others hitting it directly. In Compose we might omit mapping port 3002 to host in production deployment. That way, only our app can talk to Firecrawl internally. This is important because we disabled Firecrawl’s authentication; if left open, anyone could use it. Alternatively, if we do map it (for debugging), we must not leave it open in a live environment.

Database Credentials: We use default credentials for Postgres (as per Firecrawl default). For production, it’s advisable to change POSTGRES_PASSWORD to something secure via .env and correspondingly update NUQ_DATABASE_URL. The .env file centralizes such secrets (DB password, API keys). Limit access to this file.

Input Validation: We should validate that the url provided is a proper URL. Possibly restrict allowed schemes to http/https. Firecrawl will attempt to fetch whatever URL given – to avoid misuse, one might restrict internal network access or black-list certain domains if necessary (so users don’t crawl sensitive internal sites through our service, if it has access). Firecrawl does have options to set allowed domains, etc., but since the user gives the exact domain, it’s fine.

Rate Limiting: At the API level, we might want to rate limit how many jobs a single client can submit, to prevent abuse. This can be handled by simple counters or using something like an API Gateway or proxy. Not core to MVP, but a note for future.

CORS and Networking: If other apps (frontends) will call our API directly from browsers, we may need to enable CORS in FastAPI. If it’s server-to-server, not needed. We assume server-to-server usage.

Supabase/Auth in Firecrawl: We have turned off Firecrawl’s internal auth (which is fine). There will be some warnings in logs about “bypassing authentication”
docs.firecrawl.dev
 – we can ignore them as they said it doesn’t impede scraping.

Firecrawl Webhook Security: If we use webhooks, set a secret token for Firecrawl to sign webhook requests (they allow setting FIRECRAWL_WEBHOOK_SECRET and they will send X-Firecrawl-Signature header
docs.firecrawl.dev
). Our webhook handler would verify this to ensure the request is genuinely from our Firecrawl service. Since in Docker internal, it’s less of a concern, but still a good practice.

Conclusion

We have outlined a comprehensive plan to implement a scalable web scraping backend using FastAPI and Firecrawl. The system meets the requirements by allowing users to submit URLs and keywords and retrieving the relevant website content in JSON format via an API. We leveraged Firecrawl’s powerful crawling capabilities (covering subpages, dynamic content, etc.)
github.com
 and its queue-based architecture to handle high loads
github.com
. By using a shared PostgreSQL database for persistence
blog.csdn.net
 and Docker Compose to containerize the stack, the solution is both modular and easy to deploy.

 

In summary, the development involves configuring Firecrawl in self-hosted mode, building the FastAPI application with endpoints and background processing, integrating everything with Docker, and rigorously testing the flow. Following this "vibecoding" blueprint, we can confidently proceed to implementation, committing small increments to git after each tested feature. The result will be a production-ready service that can scrape and serve data from websites reliably and efficiently.