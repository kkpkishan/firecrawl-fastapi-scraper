#!/usr/bin/env python3
"""
Test Script for Nested Scraping and Document Extraction

Tests the complete nested scraping system including:
1. Regex pattern extraction
2. URL extraction from patterns
3. Document extraction (.pdf, .xlsx, etc.)
4. Nested web page scraping
"""
import asyncio
import sys
import os

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from regex_extractor import get_extractor
from nested_scraper import get_nested_scraper
from document_extractor import get_document_extractor


# Sample content with URLs and patterns
SAMPLE_CONTENT = """
# Exam Notification 2025

**Advertisement No: 123/2025**

## Important Dates

- Last Date: 15/01/2025
- Exam Date: 20 February 2025

## Posts Available

Post: Assistant Engineer
Vacancy: 50 posts

## Documents

Download the detailed notification: https://example.com/notifications/advt-123-2025.pdf
Application form: https://example.com/forms/application-2025.xlsx
Syllabus: https://example.com/syllabus/engineer-2025.docx

## More Information

Visit: https://example.com/exams/civil-services-2025
Details: https://example.com/details/assistant-engineer

Age Limit: 21 to 35 years
Salary: Rs. 50,000 - Rs. 80,000

Email: recruitment@example.com
"""


async def test_regex_extraction():
    """Test regex pattern extraction."""
    print("=" * 80)
    print("TEST 1: Regex Pattern Extraction")
    print("=" * 80)
    
    extractor = get_extractor()
    
    print(f"\nExtractor enabled: {extractor.enabled}")
    print(f"Patterns loaded: {len(extractor.patterns)}")
    print(f"Pattern names: {list(extractor.patterns.keys())}\n")
    
    # Extract patterns
    matches = extractor.extract_patterns(SAMPLE_CONTENT)
    
    print(f"Total matches found: {len(matches)}\n")
    
    for i, match in enumerate(matches, 1):
        print(f"Match {i}:")
        print(f"  Pattern: {match['pattern_name']} ({match['pattern_type']})")
        print(f"  Value: {match['value']}")
        print(f"  Context: {match['context'][:100]}...")
        print()
    
    return matches


async def test_url_extraction(matches):
    """Test URL extraction from regex matches."""
    print("=" * 80)
    print("TEST 2: URL Extraction from Regex Matches")
    print("=" * 80)
    
    nested_scraper = get_nested_scraper()
    
    base_url = "https://example.com/notifications/main"
    
    # Extract URLs
    urls = nested_scraper.extract_urls_from_regex_matches(matches, base_url)
    
    print(f"\nBase URL: {base_url}")
    print(f"\nWeb pages found: {len(urls['web_pages'])}")
    for url in urls['web_pages']:
        print(f"  - {url}")
    
    print(f"\nDocuments found: {len(urls['documents'])}")
    for url in urls['documents']:
        print(f"  - {url}")
    
    return urls


async def test_document_detection():
    """Test document type detection."""
    print("\n" + "=" * 80)
    print("TEST 3: Document Type Detection")
    print("=" * 80)
    
    doc_extractor = get_document_extractor()
    
    test_urls = [
        "https://example.com/file.pdf",
        "https://example.com/data.xlsx",
        "https://example.com/report.docx",
        "https://example.com/page.html",
        "https://example.com/document.odt",
        "https://example.com/text.rtf",
    ]
    
    print("\nTesting document detection:")
    for url in test_urls:
        is_doc = doc_extractor.is_document_url(url)
        doc_type = doc_extractor.get_document_type(url)
        print(f"  {url}")
        print(f"    Is document: {is_doc}")
        print(f"    Type: {doc_type}")
        print()


async def test_key_value_extraction(matches):
    """Test key-value pair extraction."""
    print("=" * 80)
    print("TEST 4: Key-Value Pair Extraction")
    print("=" * 80)
    
    extractor = get_extractor()
    
    key_value_pairs = extractor.extract_key_value_pairs(matches)
    
    print(f"\nTotal key-value pairs: {len(key_value_pairs)}\n")
    
    for i, pair in enumerate(key_value_pairs, 1):
        print(f"Pair {i}:")
        print(f"  Key: {pair['key']}")
        print(f"  Value: {pair['value']}")
        print(f"  Type: {pair['pattern_type']}")
        print()


async def test_structured_extraction():
    """Test structured data extraction."""
    print("=" * 80)
    print("TEST 5: Structured Data Extraction")
    print("=" * 80)
    
    from app.regex_extractor import extract_with_regex
    
    # Test different output formats
    formats = ['raw', 'keyvalue', 'grouped']
    
    for fmt in formats:
        print(f"\n--- Format: {fmt} ---")
        result = extract_with_regex(SAMPLE_CONTENT, output_format=fmt)
        
        print(f"Enabled: {result.get('enabled')}")
        print(f"Total matches: {result.get('total_matches', 0)}")
        
        if fmt == 'keyvalue' and result.get('data'):
            print(f"Key-value pairs: {len(result['data'])}")
            for pair in result['data'][:3]:  # Show first 3
                print(f"  {pair['key']}: {pair['value']}")
        
        elif fmt == 'grouped' and result.get('grouped_data'):
            print(f"Groups: {list(result['grouped_data'].keys())}")
            for group, items in result['grouped_data'].items():
                print(f"  {group}: {len(items)} items")
        
        print()


async def main():
    """Run all tests."""
    print("\n" + "=" * 80)
    print("NESTED SCRAPING & DOCUMENT EXTRACTION TEST SUITE")
    print("=" * 80)
    print()
    
    try:
        # Test 1: Regex extraction
        matches = await test_regex_extraction()
        
        # Test 2: URL extraction
        urls = await test_url_extraction(matches)
        
        # Test 3: Document detection
        await test_document_detection()
        
        # Test 4: Key-value extraction
        await test_key_value_extraction(matches)
        
        # Test 5: Structured extraction
        await test_structured_extraction()
        
        print("\n" + "=" * 80)
        print("✓ ALL TESTS COMPLETED SUCCESSFULLY")
        print("=" * 80)
        print()
        print("Summary:")
        print(f"  - Regex patterns extracted: {len(matches)}")
        print(f"  - Web pages found: {len(urls['web_pages'])}")
        print(f"  - Documents found: {len(urls['documents'])}")
        print()
        print("Next steps:")
        print("  1. Update .env with your regex patterns")
        print("  2. Build Docker containers: docker-compose build")
        print("  3. Start services: docker-compose up -d")
        print("  4. Test API with nested scraping enabled")
        print()
        
        return 0
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
