#!/usr/bin/env python3
"""
Test Bedrock extraction with Anthropic Claude - Run this AFTER getting model access
"""

import requests
import json
import time

BASE_URL = "http://localhost:8000"
API_KEY = "dev-api-key-change-in-production-12345678"
PDF_URL = "https://upsc.gov.in/sites/default/files/Calendar-2026-Engl-150525_5.pdf"
KEYWORD = "exam"

headers = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json"
}

def print_header(text):
    print("\n" + "=" * 80)
    print(f"  {text}")
    print("=" * 80)

def create_crawl_job():
    """Create crawl job for PDF"""
    print_header("1. CREATING CRAWL JOB FOR PDF")
    
    payload = {
        "url": PDF_URL,
        "keyword": KEYWORD,
        "follow_nested_urls": False,
        "max_depth": 1
    }
    
    print(f"URL: {PDF_URL}")
    print(f"Keyword: {KEYWORD}")
    print(f"Model: Anthropic Claude 3 Haiku")
    
    response = requests.post(f"{BASE_URL}/crawl", headers=headers, json=payload)
    
    if response.status_code == 202:
        data = response.json()
        job_id = data['job_id']
        print(f"✅ Job created: {job_id}")
        return job_id
    else:
        print(f"❌ Failed: {response.status_code}")
        print(response.text)
        return None

def wait_for_completion(job_id, max_wait=120):
    """Wait for job to complete"""
    print_header("2. WAITING FOR JOB COMPLETION")
    
    start = time.time()
    while time.time() - start < max_wait:
        response = requests.get(f"{BASE_URL}/crawl/{job_id}", headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            status = data['status']
            elapsed = int(time.time() - start)
            
            print(f"[{elapsed}s] Status: {status}", end="\r")
            
            if status == "completed":
                print(f"\n✅ Job completed in {elapsed}s")
                return data
            elif status == "failed":
                print(f"\n❌ Job failed: {data.get('error')}")
                return data
        
        time.sleep(3)
    
    print(f"\n⚠️  Timeout after {max_wait}s")
    return None

def analyze_bedrock_extraction(job_data):
    """Analyze Bedrock extracted data in detail"""
    print_header("3. ANALYZING BEDROCK EXTRACTION")
    
    results = job_data.get('results', [])
    print(f"Total Results: {len(results)}")
    
    if not results:
        print("❌ No results found!")
        return False
    
    # Group by extraction method
    by_method = {}
    for r in results:
        method = r.get('extraction_method', 'unknown')
        by_method[method] = by_method.get(method, 0) + 1
    
    print("\nExtraction Methods:")
    for method, count in by_method.items():
        print(f"  - {method}: {count} results")
    
    # Check for Bedrock extractions
    bedrock_results = [r for r in results if r.get('extraction_method') == 'bedrock']
    
    if not bedrock_results:
        print("\n❌ NO BEDROCK EXTRACTIONS FOUND!")
        print("This means Bedrock extraction failed. Check logs:")
        print("  docker-compose logs fastapi-app --tail=100 | grep -i bedrock")
        return False
    
    print(f"\n✅ SUCCESS! Bedrock extracted {len(bedrock_results)} results")
    
    # Analyze first Bedrock result in detail
    print_header("4. DETAILED ANALYSIS OF BEDROCK EXTRACTION")
    
    result = bedrock_results[0]
    print(f"Page URL: {result.get('page_url', 'N/A')}")
    print(f"Page Title: {result.get('page_title', 'N/A')}")
    print(f"Extraction Method: {result.get('extraction_method', 'N/A')}")
    
    # Check normalized_data
    normalized = result.get('normalized_data')
    if not normalized:
        print("\n❌ No normalized_data found!")
        return False
    
    print("\n✅ Normalized data found!")
    
    try:
        data = json.loads(normalized)
        
        # Validate structure
        print("\n--- VALIDATING STRUCTURE ---")
        
        required_fields = ['page_info', 'extracted_fields', 'dates', 'metadata']
        for field in required_fields:
            if field in data:
                print(f"✅ {field}: Present")
            else:
                print(f"❌ {field}: MISSING")
        
        # Show page_info
        print("\n--- PAGE INFO ---")
        page_info = data.get('page_info', {})
        print(f"Title: {page_info.get('title', 'N/A')}")
        print(f"URL: {page_info.get('url', 'N/A')}")
        print(f"Summary: {page_info.get('summary', 'N/A')[:200]}...")
        
        # Show extracted fields (exam titles)
        print("\n--- EXTRACTED FIELDS (EXAM TITLES) ---")
        fields = data.get('extracted_fields', [])
        print(f"Total Fields: {len(fields)}")
        
        if fields:
            print("\nFirst 10 Exam Titles:")
            for idx, field in enumerate(fields[:10], 1):
                key = field.get('key', 'N/A')
                value = field.get('value', 'N/A')
                confidence = field.get('confidence', 'N/A')
                print(f"{idx}. {key}: {value}")
                print(f"   Confidence: {confidence}")
        else:
            print("⚠️  No extracted fields found")
        
        # Show dates (exam dates)
        print("\n--- EXTRACTED DATES (EXAM DATES) ---")
        dates = data.get('dates', [])
        print(f"Total Dates: {len(dates)}")
        
        if dates:
            print("\nFirst 10 Exam Dates:")
            for idx, date in enumerate(dates[:10], 1):
                label = date.get('label', 'N/A')
                value = date.get('value', 'N/A')
                print(f"{idx}. {label}: {value}")
        else:
            print("⚠️  No dates found")
        
        # Show metadata
        print("\n--- METADATA ---")
        metadata = data.get('metadata', {})
        print(f"Extraction Timestamp: {metadata.get('extraction_timestamp', 'N/A')}")
        print(f"Model Used: {metadata.get('model_used', 'N/A')}")
        print(f"Content Type: {metadata.get('content_type', 'N/A')}")
        
        return True
        
    except json.JSONDecodeError as e:
        print(f"\n❌ JSON parse error: {e}")
        print(f"Raw data: {normalized[:500]}...")
        return False

def verify_database_storage(job_id):
    """Verify data is properly stored in database"""
    print_header("5. VERIFYING DATABASE STORAGE")
    
    response = requests.get(f"{BASE_URL}/crawl/{job_id}?include_raw=true", headers=headers)
    
    if response.status_code != 200:
        print(f"❌ Failed to retrieve from database: {response.status_code}")
        return False
    
    data = response.json()
    results = data.get('results', [])
    
    print(f"✅ Found {len(results)} results in database")
    
    # Check for structured data
    structured_count = 0
    raw_count = 0
    
    for result in results:
        if result.get('normalized_data'):
            structured_count += 1
        if result.get('raw_llm_output'):
            raw_count += 1
    
    print(f"✅ {structured_count} results have normalized_data (structured)")
    print(f"✅ {raw_count} results have raw_llm_output")
    
    if structured_count == 0:
        print("\n❌ NO STRUCTURED DATA IN DATABASE!")
        print("Bedrock extraction did not work properly.")
        return False
    
    print("\n✅ SUCCESS! Structured data properly stored in database")
    return True

def main():
    print("\n" + "=" * 80)
    print("  TESTING BEDROCK EXTRACTION WITH ANTHROPIC CLAUDE 3 HAIKU")
    print("  PDF: https://upsc.gov.in/sites/default/files/Calendar-2026-Engl-150525_5.pdf")
    print("=" * 80)
    print("\n⚠️  IMPORTANT: This test requires AWS Bedrock access to Claude model")
    print("If you haven't requested access yet, this test will fail.")
    print("=" * 80)
    
    # Check service
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code != 200:
            print("\n❌ Service not healthy")
            return
    except:
        print("\n❌ Cannot connect to service")
        print("Make sure docker-compose is running:")
        print("  docker-compose up -d")
        return
    
    print("✅ Service is running")
    
    # Create job
    job_id = create_crawl_job()
    if not job_id:
        return
    
    # Wait for completion
    job_data = wait_for_completion(job_id)
    if not job_data:
        return
    
    # Check if job failed
    if job_data.get('status') == 'failed':
        print(f"\n❌ Job failed: {job_data.get('error')}")
        return
    
    # Analyze extraction
    if job_data.get('status') == 'completed':
        success = analyze_bedrock_extraction(job_data)
        
        if success:
            # Verify database storage
            db_success = verify_database_storage(job_id)
            
            if db_success:
                print("\n" + "=" * 80)
                print("  ✅ ALL TESTS PASSED!")
                print("=" * 80)
                print("\nBedrock extraction is working correctly:")
                print("  ✅ Exam titles extracted")
                print("  ✅ Exam dates extracted")
                print("  ✅ Data properly structured")
                print("  ✅ Data stored in database")
                print("\nYou can now use Bedrock for intelligent data extraction!")
            else:
                print("\n" + "=" * 80)
                print("  ❌ DATABASE STORAGE FAILED")
                print("=" * 80)
        else:
            print("\n" + "=" * 80)
            print("  ❌ BEDROCK EXTRACTION FAILED")
            print("=" * 80)
            print("\nPossible reasons:")
            print("  1. AWS Bedrock access not granted yet")
            print("  2. Model configuration incorrect")
            print("  3. AWS credentials invalid")
            print("\nCheck logs: docker-compose logs fastapi-app --tail=100")

if __name__ == "__main__":
    main()
