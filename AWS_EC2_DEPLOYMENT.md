# AWS EC2 Deployment Guide

## Problem Solved

When deploying to AWS EC2, the firecrawl-api service was failing with:
```
Error: Port 3002 did not become available within 30000ms
    at Timeout.<anonymous> (/app/dist/src/harness.js:173:52)
```

This happened because:
- The `harness.js` process manager has a hardcoded 30-second timeout
- AWS EC2 instances (especially smaller ones) take longer to start services
- OpenTelemetry instrumentation adds startup overhead
- Multiple workers (api, worker, extract-worker, nuq-worker-0 to nuq-worker-4) need time to initialize
- The API server wasn't binding to port 3002 within the timeout

**Root Cause:** The timeout is hardcoded in `apps/api/dist/src/harness.js` at line 173:
```javascript
const timeoutMs = 30000; // 30 seconds - TOO SHORT for AWS EC2
```

## Solution

We've implemented a **runtime patching solution** that automatically fixes the timeout without modifying source code.

### How It Works

1. **Custom Entrypoint Script** (`apps/api/docker-entrypoint-custom.sh`):
   - Runs before the main command
   - Uses `sed` to patch the compiled JavaScript file
   - Changes `timeoutMs = 30000` to `timeoutMs = 90000`
   - Executes the original command

2. **Docker Configuration** (`docker-compose.yaml`):
   - Mounts the custom entrypoint as read-only volume
   - Overrides the default entrypoint
   - Adds healthcheck with 60s start period

### Why This Approach?

✅ **No source code changes** - Works with any Firecrawl version  
✅ **Automatic** - Applied on every container start  
✅ **Portable** - Works on local dev and AWS EC2  
✅ **Safe** - Only patches the timeout value, nothing else  

### Verification

Check if the patch was applied:
```bash
docker logs firecrawl-api 2>&1 | head -5
# Should show:
# Patching harness.js to increase startup timeout...
# Timeout increased to 90 seconds
```

### Services Started by harness.js

The harness.js process manager starts 8 services simultaneously:

1. **api** - Main API server on port 3002
2. **worker** - Queue worker for background jobs
3. **extract-worker** - Content extraction worker
4. **nuq-worker-0** to **nuq-worker-4** - 5 parallel scraping workers

All services must initialize before the timeout expires. With 90 seconds, there's enough time for:
- OpenTelemetry instrumentation
- Redis connections
- Database connections
- Worker initialization

## Deployment Steps

### 1. Build Docker Images

```bash
# Build all images
docker-compose build --no-cache

# Or build specific service
docker-compose build firecrawl-api
```

### 2. Deploy to AWS EC2

```bash
# Copy files to EC2
scp -r . ec2-user@your-ec2-instance:/home/ec2-user/app/

# SSH into EC2
ssh ec2-user@your-ec2-instance

# Navigate to app directory
cd /home/ec2-user/app/

# Start services
docker-compose up -d

# Check logs
docker-compose logs -f firecrawl-api
```

### 3. Verify Deployment

```bash
# Check service status
docker-compose ps

# Test API health
curl http://localhost:10080/health

# Test firecrawl API
curl http://localhost:3002/

# Check logs for "Worker 19 listening on port 3002"
docker-compose logs firecrawl-api | grep "listening"
```

## Configuration

### Port Mappings

- **FastAPI**: `10080` → container `8000`
- **Firecrawl API**: `3002` → container `3002`
- **PostgreSQL**: Internal only (dynamic port)
- **Redis**: Internal only (dynamic port)

### Environment Variables

Key variables in `.env`:
```bash
# AWS Bedrock
AWS_REGION=ap-south-1
BEDROCK_MODEL_ID=anthropic.claude-3-haiku-20240307-v1:0
BEDROCK_MAX_TOKENS=4096
ENABLE_BEDROCK_EXTRACTION=true

# Firecrawl
NUM_WORKERS_PER_QUEUE=8
USE_DB_AUTHENTICATION=false
```

## Troubleshooting

### Issue: Port 3002 timeout error

**Symptoms:**
```
Error: Port 3002 did not become available within 30000ms
```

**Solution:**
- Ensure `docker-entrypoint-custom.sh` is mounted correctly
- Check if timeout was patched: `docker exec firecrawl-api grep "timeoutMs = 90000" /app/dist/src/harness.js`
- Increase EC2 instance size if still timing out

### Issue: Services not starting

**Check:**
```bash
# View all logs
docker-compose logs

# Check specific service
docker-compose logs firecrawl-api

# Check if workers are running
docker-compose logs firecrawl-api | grep "Worker"
```

### Issue: Bedrock extraction failing

**Check:**
```bash
# Verify AWS credentials
docker exec fastapi-app env | grep AWS

# Check Bedrock configuration
docker-compose logs fastapi-app | grep "Bedrock"

# Test extraction
curl -X POST http://localhost:10080/crawl \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-api-key-change-in-production-12345678" \
  -d '{"url": "https://example.com", "keyword": "test"}'
```

## Performance Optimization

### For Smaller EC2 Instances (t2.micro, t2.small)

1. **Reduce worker count:**
   ```bash
   NUM_WORKERS_PER_QUEUE=4
   ```

2. **Increase swap space:**
   ```bash
   sudo dd if=/dev/zero of=/swapfile bs=1M count=2048
   sudo chmod 600 /swapfile
   sudo mkswap /swapfile
   sudo swapon /swapfile
   ```

3. **Monitor resources:**
   ```bash
   docker stats
   ```

### For Larger EC2 Instances (t2.large, t2.xlarge)

1. **Increase worker count:**
   ```bash
   NUM_WORKERS_PER_QUEUE=16
   ```

2. **Enable more nuq-workers** (edit harness.js or docker-compose)

## Security Recommendations

1. **Change API Key:**
   ```bash
   APP_API_KEY=your-secure-random-key-here
   ```

2. **Use IAM Roles for AWS Credentials:**
   - Remove `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` from `.env`
   - Attach IAM role to EC2 instance with Bedrock permissions

3. **Enable HTTPS:**
   - Use nginx or AWS ALB for SSL termination
   - Update port mappings accordingly

4. **Restrict Security Groups:**
   - Only allow necessary ports (10080, 3002)
   - Restrict source IPs if possible

## Monitoring

### Health Checks

```bash
# FastAPI health
curl http://localhost:10080/health

# FastAPI readiness
curl http://localhost:10080/readiness

# Check job status
curl -H "X-API-Key: your-key" http://localhost:10080/crawl/jobs?start_date=2025-12-01&end_date=2025-12-31
```

### Logs

```bash
# Follow all logs
docker-compose logs -f

# Follow specific service
docker-compose logs -f fastapi-app

# Search logs
docker-compose logs | grep "error"
```

## Backup and Recovery

### Database Backup

```bash
# Backup PostgreSQL
docker exec nuq-postgres pg_dump -U postgres postgres > backup.sql

# Restore
docker exec -i nuq-postgres psql -U postgres postgres < backup.sql
```

### Configuration Backup

```bash
# Backup .env and docker-compose.yaml
tar -czf config-backup.tar.gz .env docker-compose.yaml
```

## Success Criteria

✅ All services running:
```bash
docker-compose ps
# Should show all services as "Up" or "healthy"
```

✅ API responding:
```bash
curl http://localhost:10080/health
# Should return: {"status":"healthy","service":"fastapi-app"}
```

✅ Firecrawl workers running:
```bash
docker-compose logs firecrawl-api | grep "Worker.*listening"
# Should show: Worker 19 listening on port 3002
```

✅ Bedrock extraction working:
```bash
# Create test job and check extraction method is "bedrock"
```

## Support

For issues or questions:
1. Check logs: `docker-compose logs`
2. Verify configuration: `.env` file
3. Check AWS credentials and permissions
4. Review this deployment guide

---

**Last Updated:** December 24, 2025
**Tested On:** AWS EC2 t2.medium, Ubuntu 22.04
**Docker Version:** 24.0+
**Docker Compose Version:** 2.20+
