# Web Scraping Backend (FastAPI + Firecrawl)

A scalable web scraping backend service that enables users to submit URLs and keywords for crawling, then retrieve extracted content via a REST API.

## Features

- 🚀 **FastAPI Backend** - High-performance async REST API
- 🕷️ **Firecrawl Integration** - Self-hosted web crawler with JavaScript rendering support
- 🔍 **Keyword Search** - Case-insensitive keyword matching across crawled pages
- 💾 **PostgreSQL Storage** - Persistent storage for crawl jobs and results
- 🔐 **API Key Authentication** - Secure access control
- 🐳 **Docker Compose** - Complete containerized deployment
- ⚡ **Concurrent Processing** - Handle thousands of crawl jobs simultaneously

## Architecture

```
Client → FastAPI Backend → Firecrawl API → Playwright Service
                ↓                ↓
         PostgreSQL ← Redis (Queue)
```

## Prerequisites

- Docker (20.10+)
- Docker Compose (2.0+)
- 4GB+ RAM recommended
- 10GB+ disk space

## Quick Start

### 1. Clone and Setup

```bash
# Clone the repository
git clone <repository-url>
cd <repository-name>

# Copy environment file
cp .env.example .env

# Edit .env and set your APP_API_KEY
nano .env  # or use your preferred editor
```

### 2. Generate API Key

Generate a secure API key for production:

```bash
# Using openssl
openssl rand -hex 32

# Or using Python
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Update `APP_API_KEY` in `.env` with the generated key.

### 3. Start Services

```bash
# Build and start all services
docker-compose up --build

# Or run in detached mode
docker-compose up -d --build
```

### 4. Verify Services

Check that all services are running:

```bash
docker-compose ps
```

You should see:
- `fastapi-app` on port 8000
- `firecrawl-api` on port 3002
- `nuq-postgres` on port 5432
- `redis` on port 6379
- `playwright-service` (internal)

### 5. Test the API

```bash
# Health check
curl http://localhost:8000/health

# Submit a crawl job
curl -X POST http://localhost:8000/crawl \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key-here" \
  -d '{
    "url": "https://example.com",
    "keyword": "example"
  }'

# Check job status (replace {job_id} with the returned ID)
curl http://localhost:8000/crawl/{job_id} \
  -H "X-API-Key: your-api-key-here"
```

## API Documentation

### Endpoints

#### POST /crawl
Submit a new crawl job.

**Request:**
```json
{
  "url": "https://example.com",
  "keyword": "search term"
}
```

**Headers:**
- `X-API-Key`: Your API key
- `Content-Type`: application/json

**Response (202 Accepted):**
```json
{
  "job_id": "uuid",
  "status": "started"
}
```

#### GET /crawl/{job_id}
Retrieve crawl job status and results.

**Headers:**
- `X-API-Key`: Your API key

**Response (200 OK):**
```json
{
  "job_id": "uuid",
  "url": "https://example.com",
  "keyword": "search term",
  "status": "completed",
  "results": [
    {
      "page_url": "https://example.com/page",
      "page_title": "Page Title",
      "content_snippet": "Content containing the keyword..."
    }
  ],
  "created_at": "2024-01-01T00:00:00",
  "completed_at": "2024-01-01T00:01:00"
}
```

**Status Values:**
- `pending` - Job created, not yet started
- `in_progress` - Crawling in progress
- `completed` - Crawling finished successfully
- `failed` - Crawling failed (check error field)

## Configuration

### Environment Variables

See `.env.example` for all available configuration options.

**Required:**
- `APP_API_KEY` - API key for authentication
- `POSTGRES_USER` - Database username
- `POSTGRES_PASSWORD` - Database password
- `POSTGRES_DB` - Database name

**Optional:**
- `NUM_WORKERS_PER_QUEUE` - Firecrawl worker count (default: 8)
- `LOG_LEVEL` - Logging level (default: INFO)
- `PROXY_SERVER` - Proxy server URL for Playwright
- `BLOCK_MEDIA` - Block media requests to save bandwidth

### Performance Tuning

**For higher concurrency:**
```env
NUM_WORKERS_PER_QUEUE=16  # Increase based on CPU cores
```

**For production:**
```env
LOG_LEVEL=WARNING
POSTGRES_PASSWORD=strong-password-here
```

## Development

### Project Structure

```
.
├── app/                    # FastAPI application
│   ├── main.py            # Application entry point
│   ├── models.py          # Database models
│   ├── schemas.py         # Pydantic schemas
│   ├── database.py        # Database connection
│   └── Dockerfile         # FastAPI container
├── apps/                   # Firecrawl source code
│   ├── api/               # Firecrawl API
│   ├── nuq-postgres/      # PostgreSQL with Firecrawl schema
│   └── playwright-service-ts/  # Playwright service
├── docker-compose.yaml    # Service orchestration
├── .env                   # Environment variables (not in git)
└── .env.example          # Environment template
```

### Running Locally

For development with hot reload:

```bash
# Start only the dependencies
docker-compose up nuq-postgres redis firecrawl-api playwright-service

# Run FastAPI locally
cd app
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Viewing Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f fastapi-app
docker-compose logs -f firecrawl-api
```

## Troubleshooting

### Services won't start

```bash
# Check service status
docker-compose ps

# View logs
docker-compose logs

# Restart services
docker-compose restart
```

### Database connection errors

```bash
# Check PostgreSQL is running
docker-compose ps nuq-postgres

# Check database logs
docker-compose logs nuq-postgres

# Restart database
docker-compose restart nuq-postgres
```

### Firecrawl not responding

```bash
# Check Firecrawl logs
docker-compose logs firecrawl-api

# Verify Redis is running
docker-compose ps redis

# Restart Firecrawl
docker-compose restart firecrawl-api
```

### Port conflicts

If ports 8000, 3002, 5432, or 6379 are already in use:

```bash
# Edit docker-compose.yaml and change port mappings
# Example: "8001:8000" instead of "8000:8000"
```

## Production Deployment

### Security Checklist

- [ ] Change `APP_API_KEY` to a strong random value
- [ ] Change `POSTGRES_PASSWORD` to a strong password
- [ ] Remove port mappings for internal services (Redis, PostgreSQL)
- [ ] Enable HTTPS with reverse proxy (nginx/Traefik)
- [ ] Set `LOG_LEVEL=WARNING` or `ERROR`
- [ ] Implement rate limiting
- [ ] Set up monitoring and alerting
- [ ] Configure backup for PostgreSQL volume

### Scaling

**Horizontal Scaling:**
```bash
# Run multiple FastAPI instances
docker-compose up --scale fastapi-app=3
```

**Increase Firecrawl Workers:**
```env
NUM_WORKERS_PER_QUEUE=32
```

## License

[Your License Here]

## Support

For issues and questions, please open an issue on GitHub.
