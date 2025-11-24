# Web Scraping Backend API

A scalable, production-ready web scraping service built with FastAPI and Firecrawl. This service enables users to submit URLs and keywords for crawling, then retrieve extracted content via a REST API.

## 🚀 Features

- **AWS Bedrock LLM Extraction**: Intelligent data extraction using Claude 3 Haiku for structured JSON output
- **Dual Extraction Methods**: Automatic fallback between LLM and regex-based extraction
- **PDF Document Processing**: Extract text and structured data from PDF files
- **Asynchronous Job Processing**: Submit crawl jobs and retrieve results later
- **Keyword Extraction**: Case-insensitive keyword search across all crawled pages
- **Firecrawl Integration**: Leverages open-source Firecrawl for robust web crawling
- **Dynamic Regex Patterns**: Fully configurable regex patterns via .env file
- **API Key Authentication**: Secure endpoints with API key validation
- **Comprehensive Error Handling**: Retry logic, timeouts, and graceful degradation
- **Docker Compose Setup**: Easy deployment with all services containerized
- **Health Checks**: Built-in health and readiness endpoints
- **Interactive API Docs**: Swagger UI at `/docs`

## 📋 Prerequisites

- **Docker** (version 20.10 or higher)
- **Docker Compose** (version 2.0 or higher)
- **Git** (for cloning the repository)

## 🛠️ Quick Start

### 1. Clone the Repository

```bash
git clone <repository-url>
cd firecrawl-fastapi-scraper
```

### 2. Configure Environment Variables

Copy the example environment file and update the values:

```bash
cp .env.example .env
```

**Important**: Update the following variables in `.env`:

```bash
# Generate a strong API key (32+ characters recommended)
APP_API_KEY=your-secure-random-api-key-here

# Optional: Change database password for production
POSTGRES_PASSWORD=your-secure-password

# AWS Bedrock Configuration (Optional - for LLM extraction)
ENABLE_BEDROCK_EXTRACTION=true
AWS_REGION=ap-south-1
AWS_ACCESS_KEY_ID=your-aws-access-key
AWS_SECRET_ACCESS_KEY=your-aws-secret-key
BEDROCK_MODEL_ID=anthropic.claude-3-haiku-20240307-v1:0
```

**Note**: AWS Bedrock is optional. If not configured, the system will use regex-based extraction.

### 3. Start the Services

```bash
docker-compose up -d
```

This will start all required services:
- FastAPI Backend (port 8000)
- Firecrawl API (port 3002)
- PostgreSQL Database (port 5432)
- Redis (port 6379)
- Playwright Service (for JavaScript rendering)

### 4. Verify Installation

Check that all services are running:

```bash
docker-compose ps
```

Test the health endpoint:

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "service": "fastapi-app"
}
```

## 📖 API Usage

### Authentication

All API endpoints require an API key in the `X-API-Key` header:

```bash
curl -H "X-API-Key: your-api-key-here" http://localhost:8000/crawl
```

### Submit a Crawl Job

**Endpoint**: `POST /crawl`

```bash
curl -X POST http://localhost:8000/crawl \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key-here" \
  -d '{
    "url": "https://example.com",
    "keyword": "example"
  }'
```

**Response** (202 Accepted):
```json
{
  "job_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "started"
}
```

### Check Job Status

**Endpoint**: `GET /crawl/{job_id}`

```bash
curl -X GET http://localhost:8000/crawl/123e4567-e89b-12d3-a456-426614174000 \
  -H "X-API-Key": your-api-key-here"
```

**Response** (In Progress):
```json
{
  "job_id": "123e4567-e89b-12d3-a456-426614174000",
  "url": "https://example.com",
  "keyword": "example",
  "status": "in_progress",
  "results": null,
  "error": null,
  "created_at": "2025-11-14T12:00:00",
  "completed_at": null
}
```

**Response** (Completed):
```json
{
  "job_id": "123e4567-e89b-12d3-a456-426614174000",
  "url": "https://example.com",
  "keyword": "example",
  "status": "completed",
  "results": [
    {
      "page_url": "https://example.com/page1",
      "page_title": "Page Title",
      "content_snippet": "Content containing the keyword...",
      "extraction_method": "bedrock",
      "normalized_data": "{...}",
      "raw_llm_output": "{...}"
    }
  ],
  "error": null,
  "created_at": "2025-11-14T12:00:00",
  "completed_at": "2025-11-14T12:01:00"
}
```

### Get Results with Raw LLM Output

**Endpoint**: `GET /crawl/{job_id}?include_raw=true`

```bash
curl -X GET "http://localhost:8000/crawl/123e4567-e89b-12d3-a456-426614174000?include_raw=true" \
  -H "X-API-Key: your-api-key-here"
```

This includes the complete LLM JSON output with structured data extraction.

## 🤖 AWS Bedrock LLM Extraction

### Overview

The system supports intelligent data extraction using AWS Bedrock's Claude 3 Haiku model. When enabled, the LLM automatically structures extracted data into JSON format with:

- **Page Information**: Title, URL, summary
- **Extracted Fields**: Key-value pairs with confidence levels
- **Dates**: Automatically formatted to ISO 8601 (YYYY-MM-DD)
- **Metadata**: Extraction timestamp, model used, content type

### Extraction Methods

The system uses a smart fallback approach:

1. **AWS Bedrock LLM** (Primary): For unstructured content and semantic understanding
2. **Regex Patterns** (Fallback): For structured documents and pattern-based extraction
3. **Keyword Context** (Last Resort): When no patterns match

### Example LLM Output

```json
{
  "page_info": {
    "title": "UPSC Exam Calendar 2026",
    "url": "https://upsc.gov.in/calendar",
    "summary": "Schedule of examinations for 2026"
  },
  "extracted_fields": [
    {
      "key": "Examination",
      "value": "Civil Services Examination",
      "confidence": "high",
      "context": "Civil Services (Preliminary) Examination, 2026"
    }
  ],
  "dates": [
    {
      "label": "Exam Date",
      "value": "2026-05-24",
      "context": "Civil Services (Preliminary) Examination, 2026  24.05.2026"
    }
  ],
  "metadata": {
    "extraction_timestamp": "2025-11-24T12:00:00Z",
    "model_used": "anthropic.claude-3-haiku-20240307-v1:0",
    "content_type": "pdf"
  }
}
```

### Supported Document Types

- **HTML Pages**: Web pages with structured or unstructured content
- **PDF Documents**: Automatically extracts text and applies LLM
- **Excel Files**: `.xlsx`, `.xls` (text extraction)
- **Word Documents**: `.docx`, `.doc` (text extraction)
- **Other Formats**: `.odt`, `.rtf`

### Configuration

Enable Bedrock extraction in `.env`:

```bash
ENABLE_BEDROCK_EXTRACTION=true
AWS_REGION=ap-south-1
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
BEDROCK_MODEL_ID=anthropic.claude-3-haiku-20240307-v1:0
```

### Cost Optimization

- **Temperature**: Set to 0.0 for deterministic results (lower cost)
- **Max Tokens**: Limit to 4096 for most use cases
- **Fallback**: Regex extraction is free and used when appropriate

## 📚 API Documentation

### Interactive Documentation

Visit http://localhost:8000/docs for interactive Swagger UI documentation.

### Available Endpoints

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| GET | `/` | API information | No |
| GET | `/health` | Health check | No |
| GET | `/readiness` | Readiness check | No |
| POST | `/crawl` | Submit crawl job | Yes |
| GET | `/crawl/{job_id}` | Get job status | Yes |
| GET | `/docs` | API documentation | No |

### Status Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 202 | Accepted (job created) |
| 400 | Bad Request (invalid input) |
| 401 | Unauthorized (missing/invalid API key) |
| 404 | Not Found (job doesn't exist) |
| 422 | Unprocessable Entity (validation error) |
| 500 | Internal Server Error |
| 503 | Service Unavailable (database/service down) |

## 🔧 Configuration

### Environment Variables

#### Core Configuration

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `APP_API_KEY` | API key for authentication | - | Yes |
| `LOG_LEVEL` | Logging level (DEBUG, INFO, WARNING, ERROR) | INFO | No |
| `POSTGRES_USER` | PostgreSQL username | postgres | No |
| `POSTGRES_PASSWORD` | PostgreSQL password | postgres | No |
| `POSTGRES_DB` | PostgreSQL database name | postgres | No |
| `NUM_WORKERS_PER_QUEUE` | Firecrawl worker processes | 8 | No |
| `USE_DB_AUTHENTICATION` | Firecrawl internal auth | false | No |

#### AWS Bedrock LLM Configuration (Optional)

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `ENABLE_BEDROCK_EXTRACTION` | Enable AWS Bedrock LLM extraction | false | No |
| `AWS_REGION` | AWS region for Bedrock service | us-east-1 | No |
| `AWS_ACCESS_KEY_ID` | AWS access key (dev only) | - | No |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key (dev only) | - | No |
| `BEDROCK_MODEL_ID` | Bedrock model to use | anthropic.claude-3-haiku-20240307-v1:0 | No |
| `BEDROCK_TEMPERATURE` | LLM temperature (0.0-1.0) | 0.0 | No |
| `BEDROCK_MAX_TOKENS` | Maximum tokens for LLM output | 4096 | No |

**Note**: For production, use IAM roles instead of access keys.

#### Regex Extraction Configuration

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `ENABLE_REGEX_EXTRACTION` | Enable regex pattern extraction | true | No |
| `REGEX_CONTEXT_CHARS` | Context characters around matches | 200 | No |
| `REGEX_PATTERN_*` | Dynamic regex patterns | - | No |

Add custom regex patterns by prefixing with `REGEX_PATTERN_`:
```bash
REGEX_PATTERN_DATE=\b(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{4})\b
REGEX_PATTERN_EMAIL=\b([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b
```

### Performance Tuning

**Increase Concurrency**:
```bash
# In .env file
NUM_WORKERS_PER_QUEUE=16
```

**Adjust Timeout**:
```python
# In app/config.py
crawl_timeout_seconds: int = 600  # 10 minutes
```

## 🐛 Troubleshooting

### Services Won't Start

**Problem**: Docker containers fail to start

**Solution**:
```bash
# Check logs
docker-compose logs fastapi-app
docker-compose logs firecrawl-api

# Restart services
docker-compose down
docker-compose up -d
```

### Database Connection Errors

**Problem**: "Database service is temporarily unavailable"

**Solution**:
```bash
# Check PostgreSQL status
docker-compose ps nuq-postgres

# Restart database
docker-compose restart nuq-postgres

# Check logs
docker-compose logs nuq-postgres
```

### Firecrawl Not Responding

**Problem**: Jobs stuck in "in_progress" status

**Solution**:
```bash
# Check Firecrawl logs
docker-compose logs firecrawl-api

# Restart Firecrawl
docker-compose restart firecrawl-api

# Check Redis (required by Firecrawl)
docker-compose logs redis
```

### Jobs Timing Out

**Problem**: Jobs fail with timeout error

**Solution**:
- Increase timeout in `app/config.py`
- Check if website is accessible
- Verify Playwright service is running:
  ```bash
  docker-compose logs playwright-service
  ```

### API Key Issues

**Problem**: "Invalid API key" or "Missing API key"

**Solution**:
- Verify API key in `.env` file
- Ensure `X-API-Key` header is included in requests
- Restart FastAPI service after changing `.env`:
  ```bash
  docker-compose restart fastapi-app
  ```

## 🧪 Testing

### Run Automated Tests

```bash
# Comprehensive test suite
./test_comprehensive.sh

# Real-world website testing
./test_real_world.sh

# Authentication tests
./test_api.sh
```

### Manual Testing

```bash
# Test health endpoint
curl http://localhost:8000/health

# Test with example.com
curl -X POST http://localhost:8000/crawl \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-api-key-change-in-production-12345678" \
  -d '{"url": "https://example.com", "keyword": "Example"}'
```

## 📊 Monitoring

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f fastapi-app

# Last 100 lines
docker-compose logs --tail=100 fastapi-app
```

### Database Queries

```bash
# Connect to database
docker exec -it nuq-postgres psql -U postgres -d postgres

# View recent jobs
SELECT id, input_url, keyword, status, created_at 
FROM crawl_jobs 
ORDER BY created_at DESC 
LIMIT 10;

# View results for a job
SELECT page_url, page_title 
FROM crawl_results 
WHERE job_id = 'your-job-id-here';
```

## 🔒 Security Best Practices

1. **Change Default Credentials**:
   - Generate a strong `APP_API_KEY` (32+ characters)
   - Change `POSTGRES_PASSWORD` in production

2. **Use HTTPS**:
   - Deploy behind a reverse proxy (nginx, Caddy)
   - Enable SSL/TLS certificates

3. **Rate Limiting**:
   - Implement rate limiting per API key
   - Use Redis for distributed rate limiting

4. **Network Security**:
   - Don't expose Firecrawl port (3002) to public internet
   - Use Docker networks for internal communication

5. **Regular Updates**:
   - Keep Docker images updated
   - Monitor security advisories

## 🚀 Production Deployment

### Recommended Setup

1. **Use a Reverse Proxy**:
   ```nginx
   server {
       listen 443 ssl;
       server_name api.yourdomain.com;
       
       location / {
           proxy_pass http://localhost:8000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
       }
   }
   ```

2. **Enable Monitoring**:
   - Set up log aggregation (ELK, Grafana Loki)
   - Configure alerts for errors
   - Monitor resource usage

3. **Database Backups**:
   ```bash
   # Backup database
   docker exec nuq-postgres pg_dump -U postgres postgres > backup.sql
   
   # Restore database
   docker exec -i nuq-postgres psql -U postgres postgres < backup.sql
   ```

4. **Scale Services**:
   ```bash
   # Increase Firecrawl workers
   NUM_WORKERS_PER_QUEUE=32
   
   # Run multiple FastAPI instances behind load balancer
   docker-compose up --scale fastapi-app=3
   ```

## 📝 Development

### Local Development

```bash
# Install dependencies
cd app
pip install -r requirements.txt

# Run locally (without Docker)
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Code Structure

```
.
├── app/
│   ├── main.py          # FastAPI application
│   ├── models.py        # Database models
│   ├── schemas.py       # Pydantic schemas
│   ├── database.py      # Database connection
│   ├── auth.py          # Authentication
│   ├── config.py        # Configuration
│   └── requirements.txt # Python dependencies
├── docker-compose.yaml  # Service orchestration
├── .env                 # Environment variables
└── README.md           # This file
```

## 🤝 Contributing

Contributions are welcome! Please follow these guidelines:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📄 License

[Your License Here]

## 🆘 Support

For issues and questions:
- Open an issue on GitHub
- Check existing documentation
- Review troubleshooting section

## 🎯 Roadmap

- [x] AWS Bedrock LLM integration
- [x] PDF document extraction
- [x] Dynamic regex patterns
- [x] Structured JSON output
- [ ] Add pagination for large result sets
- [ ] Implement job cancellation
- [ ] Add webhook notifications
- [ ] Support for multiple keywords
- [ ] Fuzzy keyword matching
- [ ] Export results to CSV/JSON
- [ ] Admin dashboard
- [ ] Rate limiting per API key
- [ ] Nested URL scraping
- [ ] Batch job processing

---

**Built with ❤️ using FastAPI and Firecrawl**
