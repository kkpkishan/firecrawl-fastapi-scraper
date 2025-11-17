#!/bin/bash

# Test script for real exam URLs
# Tests nested scraping and document extraction

API_KEY="dev-api-key-change-in-production-12345678"
BASE_URL="http://localhost:8000"

echo "=========================================="
echo "Testing Nested Scraping with Real URLs"
echo "=========================================="
echo ""

# Test URL 1: GPSC Gujarat
echo "Test 1: GPSC Gujarat Exam Calendar"
echo "URL: https://gpsc.gujarat.gov.in/ExamCalendarforUPSC"
echo ""

JOB1=$(curl -s -X POST "$BASE_URL/crawl" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://gpsc.gujarat.gov.in/ExamCalendarforUPSC",
    "keyword": "exam",
    "follow_nested_urls": true,
    "max_depth": 2
  }')

JOB1_ID=$(echo $JOB1 | python3 -c "import sys, json; print(json.load(sys.stdin)['job_id'])" 2>/dev/null)

if [ -n "$JOB1_ID" ]; then
    echo "✓ Job created: $JOB1_ID"
    echo ""
else
    echo "✗ Failed to create job"
    echo "$JOB1"
    echo ""
fi

# Test URL 2: UPSC Active Exams
echo "Test 2: UPSC Active Exams"
echo "URL: https://upsc.gov.in/examinations/active-exams"
echo ""

JOB2=$(curl -s -X POST "$BASE_URL/crawl" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://upsc.gov.in/examinations/active-exams",
    "keyword": "examination",
    "follow_nested_urls": true,
    "max_depth": 2
  }')

JOB2_ID=$(echo $JOB2 | python3 -c "import sys, json; print(json.load(sys.stdin)['job_id'])" 2>/dev/null)

if [ -n "$JOB2_ID" ]; then
    echo "✓ Job created: $JOB2_ID"
    echo ""
else
    echo "✗ Failed to create job"
    echo "$JOB2"
    echo ""
fi

# Test URL 3: GSSSB Gujarat
echo "Test 3: GSSSB Gujarat Exam Details"
echo "URL: https://gsssb.gujarat.gov.in/ExamCategoryDetails/..."
echo ""

JOB3=$(curl -s -X POST "$BASE_URL/crawl" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://gsssb.gujarat.gov.in/ExamCategoryDetails/cqAQSGndT4su5PCjskZ32g%E2%99%AC%E2%99%AC",
    "keyword": "exam",
    "follow_nested_urls": true,
    "max_depth": 2
  }')

JOB3_ID=$(echo $JOB3 | python3 -c "import sys, json; print(json.load(sys.stdin)['job_id'])" 2>/dev/null)

if [ -n "$JOB3_ID" ]; then
    echo "✓ Job created: $JOB3_ID"
    echo ""
else
    echo "✗ Failed to create job"
    echo "$JOB3"
    echo ""
fi

echo "=========================================="
echo "Waiting for jobs to complete (60 seconds)..."
echo "=========================================="
echo ""

sleep 60

# Check results
echo "=========================================="
echo "Checking Results"
echo "=========================================="
echo ""

if [ -n "$JOB1_ID" ]; then
    echo "Job 1 Results (GPSC):"
    curl -s -X GET "$BASE_URL/crawl/$JOB1_ID" \
      -H "X-API-Key: $API_KEY" | python3 -m json.tool | head -100
    echo ""
    echo "---"
    echo ""
fi

if [ -n "$JOB2_ID" ]; then
    echo "Job 2 Results (UPSC):"
    curl -s -X GET "$BASE_URL/crawl/$JOB2_ID" \
      -H "X-API-Key: $API_KEY" | python3 -m json.tool | head -100
    echo ""
    echo "---"
    echo ""
fi

if [ -n "$JOB3_ID" ]; then
    echo "Job 3 Results (GSSSB):"
    curl -s -X GET "$BASE_URL/crawl/$JOB3_ID" \
      -H "X-API-Key: $API_KEY" | python3 -m json.tool | head -100
    echo ""
fi

echo "=========================================="
echo "Database Statistics"
echo "=========================================="
echo ""

docker exec nuq-postgres psql -U postgres -d postgres -c "
SELECT 
    status, 
    COUNT(*) as count 
FROM crawl_jobs 
GROUP BY status 
ORDER BY status;
"

echo ""

docker exec nuq-postgres psql -U postgres -d postgres -c "
SELECT 
    COUNT(*) as total_results,
    COUNT(DISTINCT job_id) as unique_jobs
FROM crawl_results;
"

echo ""
echo "=========================================="
echo "Test Complete!"
echo "=========================================="
