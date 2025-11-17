# Nested Scraping & Document Extraction Guide

## Overview

This system provides **automatic nested scraping** and **document content extraction** capabilities. When regex patterns find URLs in scraped content, the system can automatically:

1. **Scrape nested web pages** for deeper data extraction
2. **Extract content from documents** (.pdf, .xlsx, .docx, .doc, .odt, .rtf)
3. **Apply regex patterns** to extracted content
4. **Store structured data** in the database

## Features

### 🔗 Nested URL Scraping
- Automatically extracts URLs from regex pattern matches
- Follows URLs to scrape additional pages
- Respects depth limits (1-3 levels)
- Prevents duplicate scraping
- Only follows same-domain URLs

### 📄 Document Extraction
- **PDF** (.pdf) - Extracts text from all pages
- **Excel** (.xlsx, .xls) - Extracts data from all sheets
- **Word** (.docx, .doc) - Extracts text and tables
- **OpenDocument** (.odt) - Extracts formatted text
- **Rich Text** (.rtf) - Extracts plain text

### 🎯 Smart Pattern Matching
- Applies regex patterns to document content
- Extracts structured data automatically
- Stores key-value pairs in database
- Provides context around matches

## How It Works

```
1. Initial Scrape
   ↓
2. Extract Regex Patterns
   ↓
3. Find URLs in Patterns ──→ Web Pages ──→ Scrape (if depth < max)
   ↓                      └→ Documents ──→ Extract Content
4. Apply Regex to Content
   ↓
5. Store Results in Database
```

## Configuration

### Enable Nested Scraping

Add to your API request:

```json
{
  "url": "https://example.com",
  "keyword": "exam",
  "follow_nested_urls": true,
  "max_depth": 2
}
```

**Parameters:**
- `follow_nested_urls` (boolean): Enable/disable nested scraping
- `max_depth` (integer): Maximum depth (1-3 levels)

### Regex Patterns

Configure in `.env` file:

```bash
# Enable regex extraction
ENABLE_REGEX_EXTRACTION=true

# Add patterns that might contain URLs
REGEX_PATTERN_EXAM=\[([^\]]*(?:Examination|Exam)[^\]]*)\]
REGEX_PATTERN_ADVT=(?:Advt\.?|Advertisement)[:\s]+([\d\/\-]+)
```

## API Usage

### Basic Request (No Nested Scraping)

```bash
curl -X POST "http://localhost:8000/crawl" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com",
    "keyword": "exam"
  }'
```

### With Nested Scraping

```bash
curl -X POST "http://localhost:8000/crawl" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com",
    "keyword": "exam",
    "follow_nested_urls": true,
    "max_depth": 2
  }'
```

### Check Job Status

```bash
curl -X GET "http://localhost:8000/crawl/{job_id}" \
  -H "X-API-Key: your-api-key"
```

## Example Workflow

### Scenario: Scraping Exam Notifications

1. **Initial Page**: `https://example.com/notifications`
   - Contains: "Download PDF: https://example.com/advt-123.pdf"
   - Contains: "More details: https://example.com/details/exam-2025"

2. **Nested Scraping** (if enabled):
   - Downloads and extracts `advt-123.pdf`
   - Scrapes `https://example.com/details/exam-2025`
   - Applies regex patterns to all content

3. **Results Stored**:
   - Exam dates from PDF
   - Post details from nested page
   - Advertisement numbers
   - Application deadlines

## Document Extraction Details

### PDF Extraction
```python
# Extracts text from all pages
# Handles multi-page documents
# Preserves page structure
```

### Excel Extraction
```python
# Extracts data from all sheets
# Converts to tab-separated text
# Includes sheet names
```

### Word Extraction
```python
# Extracts paragraphs and tables
# Preserves document structure
# Handles both .docx and .doc
```

## Database Schema

Results are stored with:

```sql
- page_url: URL of source (web page or document)
- page_title: Title or filename
- content_snippet: Extracted content with context
- data_key: Pattern name or field name
- data_value: Extracted value
```

## Testing

### Test Regex and URL Extraction

```bash
python3 test_nested_scraping.py
```

This tests:
- ✓ Regex pattern extraction
- ✓ URL extraction from patterns
- ✓ Document type detection
- ✓ Key-value pair extraction
- ✓ Structured data extraction

### Test with Docker

```bash
# Build containers
docker-compose build

# Start services
docker-compose up -d

# Check logs
docker-compose logs -f fastapi-app

# Test API
curl -X POST "http://localhost:8000/crawl" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com",
    "keyword": "test",
    "follow_nested_urls": true,
    "max_depth": 2
  }'
```

## Performance Considerations

### Limits
- **Max nested pages**: 10 per level (prevents excessive crawling)
- **Max documents**: 20 per job (prevents timeout)
- **Max depth**: 3 levels (prevents infinite loops)
- **Timeout**: 60 seconds per document download

### Optimization Tips
1. Use specific regex patterns to target relevant URLs
2. Set appropriate `max_depth` (usually 1-2 is sufficient)
3. Monitor database size with many nested jobs
4. Use keyword filtering to reduce irrelevant results

## Troubleshooting

### No Nested URLs Found
- Check if regex patterns match content with URLs
- Verify URLs are from same domain
- Check logs: `docker-compose logs fastapi-app`

### Document Extraction Fails
- Ensure document libraries are installed
- Check document URL is accessible
- Verify document format is supported
- Check logs for specific errors

### Too Many Results
- Reduce `max_depth` to 1
- Use more specific regex patterns
- Add stricter keyword filtering

## Dependencies

Required Python packages (already in `requirements.txt`):

```
PyPDF2==3.0.1          # PDF extraction
openpyxl==3.1.2        # Excel extraction
python-docx==1.1.0     # Word extraction
odfpy==1.4.1           # OpenDocument extraction
striprtf==0.0.26       # RTF extraction
```

## Architecture

### Modules

1. **regex_extractor.py**: Dynamic regex pattern extraction
2. **nested_scraper.py**: URL extraction and nested scraping logic
3. **document_extractor.py**: Document content extraction
4. **main.py**: Integration and API endpoints

### Flow

```
API Request
    ↓
process_crawl_job()
    ↓
extract_and_store_results()
    ↓
├─→ extract_with_regex() ──→ Find patterns
├─→ extract_urls_from_regex_matches() ──→ Find URLs
├─→ process_document_url() ──→ Extract documents
└─→ process_nested_web_pages() ──→ Scrape pages
```

## Best Practices

1. **Start with depth=1**: Test with shallow scraping first
2. **Monitor resources**: Nested scraping uses more CPU/memory
3. **Use specific patterns**: Target URLs you actually need
4. **Test patterns first**: Use `test_nested_scraping.py`
5. **Check database**: Verify results are stored correctly
6. **Set timeouts**: Prevent long-running jobs

## Examples

### Example 1: Exam Notifications with PDFs

```json
{
  "url": "https://exams.gov.in/notifications",
  "keyword": "civil services",
  "follow_nested_urls": true,
  "max_depth": 2
}
```

**Result**: Scrapes notification page, downloads PDFs, extracts exam dates and details.

### Example 2: Job Postings with Application Forms

```json
{
  "url": "https://jobs.example.com/vacancies",
  "keyword": "engineer",
  "follow_nested_urls": true,
  "max_depth": 1
}
```

**Result**: Scrapes job listings, downloads Excel/Word application forms, extracts requirements.

### Example 3: Research Papers with Supplementary Data

```json
{
  "url": "https://research.example.com/papers",
  "keyword": "machine learning",
  "follow_nested_urls": true,
  "max_depth": 2
}
```

**Result**: Scrapes paper listings, downloads PDFs and data files, extracts key findings.

## Security Notes

1. **Same-domain only**: Only follows URLs from same domain
2. **Timeout protection**: 60-second timeout per document
3. **Size limits**: Prevents excessive crawling
4. **Error handling**: Graceful failure for inaccessible documents

## Future Enhancements

Potential improvements:
- [ ] Support for more document formats (PPT, CSV, JSON)
- [ ] Parallel document processing
- [ ] Custom URL filtering rules
- [ ] Document caching to avoid re-downloads
- [ ] OCR for scanned PDFs
- [ ] Image extraction from documents

## Support

For issues or questions:
1. Check logs: `docker-compose logs fastapi-app`
2. Run tests: `python3 test_nested_scraping.py`
3. Review this guide
4. Check `.env.example` for configuration examples

---

**Ready to use!** The system is fully functional and production-ready. Just configure your regex patterns and enable nested scraping in your API requests.
