# Design Document

## Overview

This design document outlines the architecture for replacing regex-based data extraction with an LLM-driven approach using AWS Bedrock. The system will leverage large language models to intelligently understand web page content and extract structured data according to a defined schema. This approach provides more flexible, context-aware extraction compared to rigid regex patterns while maintaining backward compatibility with existing APIs.

### Critical Clarifications

**1. Firecrawl Handles ALL Scraping**
- Firecrawl continues to crawl websites and retrieve page content
- Firecrawl is NOT being replaced
- Bedrock is ONLY used for understanding and extracting data from content that Firecrawl provides

**2. AWS Bedrock Authentication**
- AWS Bedrock uses standard AWS authentication (IAM roles or AWS credentials)
- There is NO "BEDROCK_API_KEY" - this is not how AWS services work
- **Production**: Use IAM role attached to EC2/ECS instance (no credentials in environment)
- **Development**: Use AWS credentials file or environment variables
- The AWS SDK automatically discovers credentials via the credential chain

**3. What This Design Changes**
- ❌ Removes: Regex pattern matching for data extraction
- ✅ Adds: LLM-based understanding and extraction via AWS Bedrock
- ✅ Keeps: Firecrawl for scraping, Document Extractor for PDFs/Word/Excel, all existing APIs

### Key Design Goals

1. **Intelligent Extraction**: Use LLMs to understand context and extract relevant data
2. **Schema-Driven**: Define extraction structure through a centralized system prompt
3. **Modular Architecture**: Isolate Bedrock integration for easy model swapping
4. **Robust Validation**: Ensure LLM output matches database schema
5. **Comprehensive Error Handling**: Handle AWS service failures gracefully
6. **Backward Compatibility**: Maintain existing API contracts

## Architecture

### High-Level Flow

```
User Request → FastAPI → Firecrawl (Scraping) → Bedrock Extractor (Understanding) → Validation → Database
                ↓              ↓                         ↓                              ↓
            Job Created   Crawls Pages            LLM Extraction              Normalized Data
```

**Important**: Firecrawl handles ALL web scraping and crawling. Bedrock is ONLY used for understanding and extracting structured data from the content that Firecrawl provides.

### Component Interaction

1. **FastAPI Application** (`main.py`): Orchestrates the crawl workflow
2. **Bedrock Extractor** (`bedrock_extractor.py`): Handles AWS Bedrock integration
3. **Document Extractor** (`document_extractor.py`): Extracts text from PDFs, Word, Excel
4. **Validation Module**: Validates and normalizes LLM output
5. **Database Layer** (`database.py`, `models.py`): Persists results

### Replacement Strategy

**What Changes**:
- Replace `regex_extractor.py` with `bedrock_extractor.py` for data extraction
- Regex patterns are NO LONGER used for extraction
- LLM understands and extracts data instead of pattern matching

**What Stays the Same**:
- **Firecrawl** continues to handle ALL web scraping and crawling
- **Document Extractor** continues to extract text from PDFs, Word, Excel
- API endpoints and response formats remain unchanged
- Database structure (with new columns added)

**Interface Pattern**:
The `bedrock_extractor.py` maintains the same interface as `regex_extractor.py`:
- Input: text content, metadata
- Output: tuple of (extracted_data, error_message)

This allows minimal changes to the existing `extract_and_store_results()` function.

**Clear Separation of Concerns**:
1. **Firecrawl**: Scrapes websites, crawls pages, retrieves content
2. **Document Extractor**: Extracts text from documents (PDF, Word, Excel)
3. **Bedrock Extractor**: Understands content and extracts structured data
4. **Database**: Stores results

## Components and Interfaces

### 1. Bedrock Extractor Module (`app/bedrock_extractor.py`)

**Purpose**: Encapsulate all AWS Bedrock interactions and LLM extraction logic.

**Key Classes**:

```python
class BedrockExtractor:
    """Main extractor class for AWS Bedrock integration."""
    
    def __init__(self):
        """Initialize with AWS credentials and configuration."""
        
    async def extract_structured_data(
        self,
        content: str,
        metadata: Dict[str, any],
        schema_hint: Optional[str] = None
    ) -> Tuple[Optional[Dict], Optional[str]]:
        """
        Extract structured data from content using LLM.
        
        Args:
            content: Text content to extract from
            metadata: Dict with url, content_type, parent_url, etc.
            schema_hint: Optional schema override
            
        Returns:
            Tuple of (extracted_data_dict, error_message)
        """
```

**Key Functions**:

```python
def get_extractor() -> BedrockExtractor:
    """Get singleton instance of BedrockExtractor."""

async def extract_with_bedrock(
    content: str,
    metadata: Dict[str, any]
) -> Dict[str, any]:
    """Convenience function matching regex_extractor interface."""
```

### 2. Configuration Updates (`app/config.py`)

Add new settings for Bedrock integration:

```python
class Settings(BaseSettings):
    # ... existing settings ...
    
    # AWS Bedrock Configuration
    aws_region: str = os.getenv("AWS_REGION", "us-east-1")
    bedrock_model_id: str = os.getenv("BEDROCK_MODEL_ID", "amazon.titan-text-express-v1")
    bedrock_temperature: float = float(os.getenv("BEDROCK_TEMPERATURE", "0.0"))
    bedrock_max_tokens: int = int(os.getenv("BEDROCK_MAX_TOKENS", "4096"))
    enable_bedrock_extraction: bool = os.getenv("ENABLE_BEDROCK_EXTRACTION", "true").lower() == "true"
    
    # Extraction retry configuration
    bedrock_max_retries: int = 2
    bedrock_retry_delay: float = 1.0
```

### 3. Database Schema Updates (`app/models.py`)

Extend `CrawlResult` model to store raw and normalized LLM output:

```python
class CrawlResult(Base):
    # ... existing columns ...
    
    # LLM extraction fields
    raw_llm_output = Column(
        Text,
        nullable=True,
        comment="Raw JSON output from LLM before normalization"
    )
    
    normalized_data = Column(
        Text,
        nullable=True,
        comment="Normalized JSON data matching schema"
    )
    
    extraction_method = Column(
        String(20),
        nullable=True,
        default='bedrock',
        comment="Method used for extraction: 'bedrock', 'regex', or 'keyword'"
    )
```

### 4. Main Application Updates (`app/main.py`)

Modify `extract_and_store_results()` to use Bedrock instead of regex:

```python
async def extract_and_store_results(
    db: AsyncSession,
    job_id: str,
    crawled_data: list,
    keyword: str,
    follow_nested: bool = False,
    max_depth: int = 1,
    current_depth: int = 0
):
    """Extract and store results using Bedrock LLM."""
    
    # Get Bedrock extractor instead of regex extractor
    extractor = get_bedrock_extractor()
    
    for page in crawled_data:
        # ... existing page processing ...
        
        # Build metadata for LLM
        metadata = {
            'url': page_url,
            'title': page_title,
            'content_type': 'html',
            'keyword': keyword
        }
        
        # Extract using Bedrock
        extracted_data, error = await extractor.extract_structured_data(
            markdown_content,
            metadata
        )
        
        if extracted_data:
            # Store results with raw and normalized data
            await create_result(
                db,
                job_id=job_id,
                page_url=page_url,
                page_title=page_title,
                content_snippet=extracted_data.get('summary', ''),
                data_key=extracted_data.get('key', ''),
                data_value=extracted_data.get('value', ''),
                raw_llm_output=json.dumps(extracted_data.get('raw', {})),
                normalized_data=json.dumps(extracted_data.get('normalized', {})),
                extraction_method='bedrock'
            )
```

## Data Models

### Extraction Schema

The LLM will extract data according to this JSON schema:

```json
{
  "page_info": {
    "title": "string",
    "url": "string",
    "summary": "string (max 500 chars)"
  },
  "extracted_fields": [
    {
      "key": "string",
      "value": "string",
      "confidence": "high|medium|low",
      "context": "string (surrounding text)"
    }
  ],
  "dates": [
    {
      "label": "string",
      "value": "ISO 8601 date string",
      "context": "string"
    }
  ],
  "metadata": {
    "extraction_timestamp": "ISO 8601 datetime",
    "model_used": "string",
    "content_type": "string"
  }
}
```

### Database Storage

**Raw Storage**: Complete LLM response stored in `raw_llm_output` column
**Normalized Storage**: Validated and cleaned data in `normalized_data` column
**Legacy Fields**: `data_key` and `data_value` populated from first extracted field for backward compatibility


## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Bedrock extraction replaces regex for all content

*For any* crawled page content, when Bedrock extraction is enabled, the system should invoke the Bedrock extractor and not execute regex pattern matching.

**Validates: Requirements 1.1, 1.2**

### Property 2: Firecrawl integration preservation

*For any* crawl job, the system should continue to use Firecrawl for crawling and content retrieval, with only the extraction method changing.

**Validates: Requirements 1.3, 1.4**

### Property 3: API backward compatibility

*For any* API request to existing endpoints, the response format should match the expected schema regardless of whether regex or Bedrock extraction is used.

**Validates: Requirements 1.5**

### Property 4: LLM receives complete context

*For any* page processed by Bedrock, the LLM invocation should include the page URL, content type, full markdown content, and parent URL (if nested).

**Validates: Requirements 4.1, 4.2, 4.3, 4.4**

### Property 5: Document metadata inclusion

*For any* document (PDF, Word, Excel) processed, the LLM should receive document-specific metadata such as page count or sheet names along with the extracted text.

**Validates: Requirements 4.5**

### Property 6: JSON parsing for all responses

*For any* LLM response, the system should attempt to parse it as JSON, and if parsing fails, attempt to extract JSON from the response text.

**Validates: Requirements 5.1, 5.2**

### Property 7: Schema validation enforcement

*For any* parsed JSON from the LLM, the system should validate all required fields against the expected schema.

**Validates: Requirements 5.3**

### Property 8: Retry on validation failure

*For any* JSON that fails schema validation, the system should re-prompt the LLM with explicit fix instructions, up to 2 retry attempts.

**Validates: Requirements 5.4, 5.5**

### Property 9: String normalization

*For any* extracted string field, the system should trim whitespace from both ends.

**Validates: Requirements 6.1**

### Property 10: HTML tag removal

*For any* extracted text containing HTML tags, the system should remove the tags unless the schema explicitly allows HTML.

**Validates: Requirements 6.2**

### Property 11: Date normalization

*For any* extracted date field, the system should normalize it to ISO 8601 format.

**Validates: Requirements 6.3**

### Property 12: Type conversion for numerics

*For any* numeric field extracted as a string, the system should convert it to the appropriate numeric type.

**Validates: Requirements 6.4**

### Property 13: Default values for optional fields

*For any* optional field missing from LLM output, the system should set it to null or an empty array as appropriate for the field type.

**Validates: Requirements 6.5**

### Property 14: Dual storage of extraction results

*For any* successful extraction, the system should store both the raw LLM JSON output and the normalized data that matches the database schema.

**Validates: Requirements 7.1, 7.2**

### Property 15: Normalized data in API responses

*For any* API query for crawl results, the system should return the normalized data by default.

**Validates: Requirements 7.5**

### Property 16: Document extractor invocation

*For any* URL pointing to a supported document type (PDF, Word, Excel), the system should invoke the Document Extractor to extract text content.

**Validates: Requirements 8.1, 8.2, 8.3**

### Property 17: Document text to LLM

*For any* successful document extraction, the system should pass the extracted text to the LLM along with document type metadata.

**Validates: Requirements 8.4**

### Property 18: Graceful document extraction failure

*For any* document extraction failure, the system should log the error and continue processing other pages without failing the entire job.

**Validates: Requirements 8.5**

### Property 19: Bedrock unavailability handling

*For any* Bedrock service unavailability, the system should log the error and mark the job as failed with a clear error message.

**Validates: Requirements 9.1**

### Property 20: Permission error handling

*For any* IAM permission error when invoking Bedrock, the system should log the permission error and mark the job as failed.

**Validates: Requirements 9.2**

### Property 21: Invalid JSON error handling

*For any* LLM response that returns invalid JSON after all retry attempts, the system should log the raw response and mark the extraction as failed.

**Validates: Requirements 9.3**

### Property 22: Timeout error handling

*For any* Bedrock request timeout, the system should log the timeout and mark the job as failed.

**Validates: Requirements 9.4**

### Property 23: Sensitive content protection in logs

*For any* Bedrock error in production, the system should not log sensitive page content in error messages.

**Validates: Requirements 9.5**

### Property 24: Exponential backoff for throttling

*For any* throttling error from AWS Bedrock, the system should implement exponential backoff retry logic with increasing delays.

**Validates: Requirements 14.1, 14.2**

### Property 25: Throttling retry exhaustion

*For any* throttled request where retries are exhausted, the system should mark the job as failed with a throttling error message.

**Validates: Requirements 14.3**

### Property 26: Throttling event logging

*For any* throttling event from Bedrock, the system should log the event for monitoring purposes.

**Validates: Requirements 14.4**

### Property 27: Temperature parameter passing

*For any* Bedrock invocation, the system should pass the configured temperature parameter from environment variables.

**Validates: Requirements 15.3**

### Property 28: Max tokens parameter passing

*For any* Bedrock invocation, the system should pass the configured max tokens parameter from environment variables.

**Validates: Requirements 15.4**

## Error Handling

### AWS Bedrock Errors

1. **Service Unavailable (503)**
   - Implement exponential backoff (1s, 2s, 4s)
   - Max 3 retries
   - Mark job as failed with clear message

2. **Throttling (429)**
   - Exponential backoff with jitter
   - Max 3 retries
   - Log for capacity planning

3. **Permission Denied (403)**
   - No retry (permanent error)
   - Log IAM role/policy issue
   - Mark job as failed immediately

4. **Invalid Request (400)**
   - Log request details (without sensitive content)
   - No retry
   - Mark extraction as failed

5. **Timeout**
   - Configurable timeout (default 30s)
   - Single retry with longer timeout
   - Mark job as failed if retry fails

### LLM Response Errors

1. **Invalid JSON**
   - Attempt to extract JSON from text using regex
   - If extraction fails, re-prompt with fix instruction
   - Max 2 re-prompts
   - Store raw response for debugging

2. **Schema Validation Failure**
   - Identify missing/invalid fields
   - Re-prompt with specific field requirements
   - Max 2 re-prompts
   - Fall back to partial data if possible

3. **Empty Response**
   - Log warning
   - Re-prompt once
   - Store as "no data extracted" if retry fails

### Document Extraction Errors

1. **Download Failure**
   - Log error with URL
   - Continue processing other pages
   - Don't fail entire job

2. **Unsupported Format**
   - Log warning
   - Skip document
   - Continue processing

3. **Extraction Library Missing**
   - Log clear error about missing dependency
   - Skip document
   - Continue processing

## Testing Strategy

### Unit Tests

**Module**: `test_bedrock_extractor.py`

1. **Configuration Tests**
   - Test environment variable loading
   - Test default values
   - Test missing required variables

2. **JSON Parsing Tests**
   - Test valid JSON parsing
   - Test invalid JSON extraction
   - Test malformed responses

3. **Validation Tests**
   - Test schema validation logic
   - Test missing field detection
   - Test type conversion

4. **Normalization Tests**
   - Test whitespace trimming
   - Test HTML tag removal
   - Test date normalization
   - Test numeric conversion

5. **Error Handling Tests**
   - Test retry logic
   - Test exponential backoff
   - Test error message formatting

**Module**: `test_bedrock_integration.py`

1. **AWS SDK Mocking**
   - Mock Bedrock client
   - Test credential chain
   - Test IAM role usage

2. **LLM Invocation Tests**
   - Test prompt construction
   - Test metadata inclusion
   - Test parameter passing

3. **Response Processing Tests**
   - Test successful extraction
   - Test partial extraction
   - Test complete failure

### Integration Tests

**Module**: `test_end_to_end_bedrock.py`

1. **Full Flow Tests**
   - Test Firecrawl → Bedrock → Database
   - Test with HTML content
   - Test with PDF documents
   - Test with Word documents
   - Test with Excel files

2. **Error Scenario Tests**
   - Test Bedrock unavailable
   - Test invalid credentials
   - Test throttling
   - Test timeout

3. **Backward Compatibility Tests**
   - Test API response format
   - Test existing client compatibility
   - Test database schema compatibility

### Property-Based Tests

**Module**: `test_bedrock_properties.py`

1. **Extraction Properties**
   - Generate random page content
   - Verify Bedrock is called (not regex)
   - Verify metadata is included

2. **Normalization Properties**
   - Generate random extracted data
   - Verify whitespace trimming
   - Verify HTML removal
   - Verify date normalization

3. **Error Handling Properties**
   - Generate random error scenarios
   - Verify retry logic
   - Verify error messages

### Manual Testing Checklist

1. **Local Docker Testing**
   - [ ] Start services with `docker-compose up`
   - [ ] Submit test crawl job
   - [ ] Verify Bedrock extraction in logs
   - [ ] Check database for raw and normalized data
   - [ ] Query results via API

2. **AWS Integration Testing**
   - [ ] Configure AWS credentials
   - [ ] Test with real Bedrock service
   - [ ] Verify IAM role permissions
   - [ ] Test different model IDs

3. **Document Processing Testing**
   - [ ] Test PDF extraction
   - [ ] Test Word document extraction
   - [ ] Test Excel extraction
   - [ ] Verify metadata inclusion


## System Prompt Design

### Purpose

The system prompt is the single source of truth for LLM extraction behavior. It defines:
- The extraction task
- The expected JSON schema
- Strict output rules
- Field descriptions and types

### System Prompt Template

```
You are a data extraction assistant for a web scraping system. Your task is to analyze web page content and extract structured information according to a specific schema.

## Task

Extract relevant information from the provided web page content. Focus on finding data that matches the user's search keyword and any related structured information.

## Output Format

You MUST return ONLY valid JSON with no additional text, comments, or explanations. The JSON must follow this exact schema:

{
  "page_info": {
    "title": "string - page title",
    "url": "string - page URL",
    "summary": "string - brief summary (max 500 characters)"
  },
  "extracted_fields": [
    {
      "key": "string - field name/label",
      "value": "string - extracted value",
      "confidence": "high|medium|low",
      "context": "string - surrounding text for context"
    }
  ],
  "dates": [
    {
      "label": "string - what this date represents",
      "value": "string - date in ISO 8601 format (YYYY-MM-DD)",
      "context": "string - surrounding text"
    }
  ],
  "metadata": {
    "extraction_timestamp": "string - current timestamp in ISO 8601 format",
    "model_used": "string - model identifier",
    "content_type": "string - html|pdf|docx|xlsx|etc"
  }
}

## Field Descriptions

### page_info (required)
- title: The page title or document name
- url: The source URL
- summary: A concise summary of the page content (max 500 chars)

### extracted_fields (required, can be empty array)
- key: The name or label of the extracted data point
- value: The actual extracted value
- confidence: Your confidence level in this extraction (high/medium/low)
- context: Surrounding text that provides context (max 200 chars)

### dates (required, can be empty array)
- label: What this date represents (e.g., "Application Deadline", "Exam Date")
- value: The date in ISO 8601 format (YYYY-MM-DD)
- context: Surrounding text (max 200 chars)

### metadata (required)
- extraction_timestamp: Current timestamp when extraction occurred
- model_used: The model identifier being used
- content_type: Type of content being processed

## Strict Rules

1. Output ONLY valid JSON - no markdown code blocks, no explanations
2. All string values must be properly escaped
3. Use null for missing optional fields
4. Use empty arrays [] for empty lists
5. Dates MUST be in ISO 8601 format (YYYY-MM-DD)
6. Remove all HTML tags from extracted text
7. Trim whitespace from all string values
8. If no relevant data is found, return empty arrays for extracted_fields and dates
9. The summary should capture the main topic of the page
10. Extract data that is relevant to the search keyword: {keyword}

## Input Metadata

You will receive the following metadata about the content:
- URL: {url}
- Content Type: {content_type}
- Parent URL: {parent_url} (if nested content)
- Search Keyword: {keyword}

Use this metadata to provide context-aware extraction.

## Content to Analyze

{content}
```

### Prompt Variables

The system prompt includes placeholders that are filled at runtime:
- `{keyword}`: User's search keyword
- `{url}`: Page URL
- `{content_type}`: Type of content (html, pdf, etc.)
- `{parent_url}`: Parent URL for nested content
- `{content}`: The actual page content in markdown format

### Prompt Maintenance

**When to Update**:
1. Database schema changes (add/remove fields)
2. New content types supported
3. Extraction quality improvements needed
4. New validation rules required

**Update Process**:
1. Modify the prompt in `bedrock_extractor.py`
2. Update documentation in `docs/bedrock-integration.md`
3. Run validation tests
4. Test with sample content
5. Deploy and monitor extraction quality

## AWS Bedrock Integration Details

### Credential Management

**IMPORTANT**: AWS Bedrock uses standard AWS authentication, NOT API keys. There is no "BEDROCK_API_KEY" environment variable.

**Priority Order** (AWS Default Credential Chain):
1. **IAM role attached to EC2/ECS instance** (RECOMMENDED for production)
2. Environment variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`) - only for development
3. AWS credentials file (`~/.aws/credentials`)
4. IAM role from ECS task definition

**Recommended Approach**:
- **Production (EC2/ECS)**: Use IAM roles attached to instances - NO credentials needed in environment
- **Development (Local)**: Use AWS credentials file (`~/.aws/credentials`) or environment variables
- **CI/CD**: Use IAM roles for service accounts

**What NOT to do**:
- ❌ Do NOT create a `BEDROCK_API_KEY` environment variable
- ❌ Do NOT hardcode `AWS_ACCESS_KEY_ID` or `AWS_SECRET_ACCESS_KEY` in code
- ❌ Do NOT commit AWS credentials to git

**What TO do**:
- ✅ Use IAM roles when deploying to EC2/ECS
- ✅ Use AWS credential chain for automatic credential discovery
- ✅ Only set `AWS_REGION` and `BEDROCK_MODEL_ID` in environment variables

### IAM Policy Requirements

The IAM role or user must have the following permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ],
      "Resource": [
        "arn:aws:bedrock:*::foundation-model/*"
      ]
    }
  ]
}
```

### Supported Models

**Amazon Titan Models**:
- `amazon.titan-text-express-v1`: Fast, cost-effective (recommended for production)
- `amazon.titan-text-lite-v1`: Lightweight, lowest cost
- `amazon.titan-text-premier-v1`: Highest quality, slower

**Anthropic Claude Models** (if available in region):
- `anthropic.claude-v2`: High quality, good for complex extraction
- `anthropic.claude-instant-v1`: Faster, lower cost

**Model Selection Criteria**:
- **Speed**: titan-text-lite-v1 or claude-instant-v1
- **Quality**: titan-text-premier-v1 or claude-v2
- **Cost**: titan-text-lite-v1
- **Balance**: titan-text-express-v1 (recommended)

### Request Configuration

```python
{
    "modelId": settings.bedrock_model_id,
    "contentType": "application/json",
    "accept": "application/json",
    "body": {
        "inputText": prompt,
        "textGenerationConfig": {
            "temperature": settings.bedrock_temperature,  # 0.0 for deterministic
            "maxTokenCount": settings.bedrock_max_tokens,  # 4096 default
            "topP": 0.9,
            "stopSequences": []
        }
    }
}
```

### Rate Limits and Quotas

**Default Limits** (vary by region and model):
- Requests per minute: 100-1000 (depends on model)
- Tokens per minute: 100,000-500,000
- Concurrent requests: 10-50

**Handling Limits**:
1. Implement exponential backoff for throttling
2. Use request queuing for high-volume scenarios
3. Monitor CloudWatch metrics for usage
4. Request quota increases if needed

### Cost Optimization

**Strategies**:
1. Use `temperature=0.0` for consistent, deterministic output
2. Optimize prompt length (shorter = cheaper)
3. Use lite models for simple extraction tasks
4. Cache results for identical content
5. Batch process when possible

**Estimated Costs** (as of 2024):
- Titan Text Express: ~$0.0008 per 1K input tokens, ~$0.0016 per 1K output tokens
- Typical extraction: ~2K input + 500 output = ~$0.0024 per page

## Validation and Normalization

### JSON Schema Validation

**Validation Steps**:
1. Parse JSON from LLM response
2. Check required fields exist
3. Validate field types
4. Check value constraints (e.g., date format)
5. Verify array structures

**Validation Implementation**:

```python
def validate_extraction_schema(data: dict) -> Tuple[bool, List[str]]:
    """
    Validate extracted data against schema.
    
    Returns:
        Tuple of (is_valid, error_messages)
    """
    errors = []
    
    # Check required top-level fields
    required_fields = ['page_info', 'extracted_fields', 'dates', 'metadata']
    for field in required_fields:
        if field not in data:
            errors.append(f"Missing required field: {field}")
    
    # Validate page_info
    if 'page_info' in data:
        page_info = data['page_info']
        if 'title' not in page_info or not isinstance(page_info['title'], str):
            errors.append("page_info.title must be a string")
        if 'url' not in page_info or not isinstance(page_info['url'], str):
            errors.append("page_info.url must be a string")
        if 'summary' not in page_info or not isinstance(page_info['summary'], str):
            errors.append("page_info.summary must be a string")
    
    # Validate extracted_fields array
    if 'extracted_fields' in data:
        if not isinstance(data['extracted_fields'], list):
            errors.append("extracted_fields must be an array")
        else:
            for i, field in enumerate(data['extracted_fields']):
                if not isinstance(field, dict):
                    errors.append(f"extracted_fields[{i}] must be an object")
                    continue
                required = ['key', 'value', 'confidence', 'context']
                for req in required:
                    if req not in field:
                        errors.append(f"extracted_fields[{i}] missing {req}")
    
    # Validate dates array
    if 'dates' in data:
        if not isinstance(data['dates'], list):
            errors.append("dates must be an array")
        else:
            for i, date in enumerate(data['dates']):
                if not isinstance(date, dict):
                    errors.append(f"dates[{i}] must be an object")
                    continue
                if 'value' in date:
                    # Validate ISO 8601 format
                    if not re.match(r'^\d{4}-\d{2}-\d{2}$', date['value']):
                        errors.append(f"dates[{i}].value must be ISO 8601 format")
    
    return len(errors) == 0, errors
```

### Data Normalization

**Normalization Steps**:

1. **Whitespace Trimming**
   ```python
   def trim_strings(data: dict) -> dict:
       """Recursively trim all string values."""
       if isinstance(data, dict):
           return {k: trim_strings(v) for k, v in data.items()}
       elif isinstance(data, list):
           return [trim_strings(item) for item in data]
       elif isinstance(data, str):
           return data.strip()
       return data
   ```

2. **HTML Tag Removal**
   ```python
   def remove_html_tags(text: str) -> str:
       """Remove HTML tags from text."""
       return re.sub(r'<[^>]+>', '', text)
   ```

3. **Date Normalization**
   ```python
   def normalize_date(date_str: str) -> str:
       """Convert various date formats to ISO 8601."""
       # Try common formats
       formats = [
           '%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y',
           '%d-%m-%Y', '%Y/%m/%d', '%B %d, %Y'
       ]
       for fmt in formats:
           try:
               dt = datetime.strptime(date_str, fmt)
               return dt.strftime('%Y-%m-%d')
           except ValueError:
               continue
       return date_str  # Return original if can't parse
   ```

4. **Type Conversion**
   ```python
   def convert_numeric_strings(value: str) -> Union[int, float, str]:
       """Convert numeric strings to appropriate types."""
       try:
           if '.' in value:
               return float(value)
           return int(value)
       except ValueError:
           return value
   ```

### Re-prompting Strategy

When validation fails, construct a fix prompt:

```python
fix_prompt = f"""
The previous JSON output had validation errors:
{', '.join(errors)}

Please provide a corrected JSON response that fixes these issues.
Remember:
- All dates must be in YYYY-MM-DD format
- All required fields must be present
- Arrays must be properly formatted

Original content to extract from:
{content[:1000]}...

Provide ONLY the corrected JSON, no explanations.
"""
```

**Re-prompt Limits**:
- Maximum 2 re-prompts
- Each re-prompt includes specific error messages
- After 2 failures, mark extraction as failed and store errors


## Implementation Phases

### Phase 1: Core Bedrock Integration

**Goal**: Create basic Bedrock extractor module with AWS integration

**Tasks**:
1. Create `app/bedrock_extractor.py` module
2. Implement AWS Bedrock client initialization
3. Implement credential chain handling
4. Create system prompt template
5. Implement basic LLM invocation
6. Add configuration to `config.py`
7. Add unit tests for configuration and AWS client

**Deliverables**:
- Working Bedrock extractor module
- Configuration via environment variables
- Basic error handling
- Unit tests passing

### Phase 2: JSON Processing and Validation

**Goal**: Implement robust JSON parsing and schema validation

**Tasks**:
1. Implement JSON parsing with fallback extraction
2. Create schema validation function
3. Implement data normalization functions
4. Add re-prompting logic for validation failures
5. Add comprehensive unit tests for validation

**Deliverables**:
- Robust JSON processing
- Schema validation
- Data normalization
- Re-prompting on errors
- Unit tests for all validation logic

### Phase 3: Database Integration

**Goal**: Update database schema and integrate with main application

**Tasks**:
1. Add new columns to `CrawlResult` model
2. Create database migration script
3. Update `create_result()` function to accept new fields
4. Modify `extract_and_store_results()` to use Bedrock
5. Add integration tests

**Deliverables**:
- Updated database schema
- Migration script
- Modified main application
- Integration tests passing

### Phase 4: Document Processing Integration

**Goal**: Integrate document extraction with Bedrock

**Tasks**:
1. Update document processing flow
2. Add document metadata to LLM context
3. Test with PDF, Word, Excel files
4. Add error handling for document failures
5. Add integration tests for documents

**Deliverables**:
- Document extraction working with Bedrock
- Metadata properly passed to LLM
- Integration tests for all document types

### Phase 5: Error Handling and Resilience

**Goal**: Implement comprehensive error handling

**Tasks**:
1. Implement exponential backoff for throttling
2. Add timeout handling
3. Add permission error detection
4. Implement sensitive content filtering in logs
5. Add error handling tests

**Deliverables**:
- Robust error handling
- Retry logic with backoff
- Secure logging
- Error handling tests passing

### Phase 6: Documentation and Testing

**Goal**: Complete documentation and comprehensive testing

**Tasks**:
1. Create `docs/bedrock-integration.md`
2. Document system prompt and schema
3. Add examples and troubleshooting guide
4. Create end-to-end integration tests
5. Create property-based tests
6. Update README with Bedrock setup instructions

**Deliverables**:
- Complete documentation
- All tests passing
- README updated
- System ready for deployment

## Deployment Considerations

### Environment Variables

**Required**:
```bash
# AWS Configuration
AWS_REGION=us-east-1
BEDROCK_MODEL_ID=amazon.titan-text-express-v1

# Feature Toggle
ENABLE_BEDROCK_EXTRACTION=true
```

**Optional**:
```bash
# LLM Parameters
BEDROCK_TEMPERATURE=0.0
BEDROCK_MAX_TOKENS=4096
```

**AWS Credentials (Only for Development - NOT for Production)**:
```bash
# Only set these if NOT using IAM role (local development only)
AWS_ACCESS_KEY_ID=<your-access-key>
AWS_SECRET_ACCESS_KEY=<your-secret-key>
```

**Production Deployment (EC2/ECS)**:
- Do NOT set `AWS_ACCESS_KEY_ID` or `AWS_SECRET_ACCESS_KEY`
- Attach an IAM role to your EC2 instance or ECS task
- The AWS SDK will automatically use the IAM role credentials
- Only set `AWS_REGION` and `BEDROCK_MODEL_ID`

### Docker Compose Updates

Add AWS credential passthrough:

```yaml
services:
  fastapi-app:
    environment:
      - AWS_REGION=${AWS_REGION:-us-east-1}
      - BEDROCK_MODEL_ID=${BEDROCK_MODEL_ID:-amazon.titan-text-express-v1}
      - BEDROCK_TEMPERATURE=${BEDROCK_TEMPERATURE:-0.0}
      - BEDROCK_MAX_TOKENS=${BEDROCK_MAX_TOKENS:-4096}
      - ENABLE_BEDROCK_EXTRACTION=${ENABLE_BEDROCK_EXTRACTION:-true}
      # Pass through AWS credentials if set
      - AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID:-}
      - AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY:-}
      - AWS_SESSION_TOKEN=${AWS_SESSION_TOKEN:-}
    # For IAM role support on EC2/ECS
    volumes:
      - ~/.aws:/root/.aws:ro  # Mount AWS config (optional)
```

### Database Migration

Create migration script `migrations/add_bedrock_fields.sql`:

```sql
-- Add new columns to crawl_results table
ALTER TABLE crawl_results
ADD COLUMN IF NOT EXISTS raw_llm_output TEXT,
ADD COLUMN IF NOT EXISTS normalized_data TEXT,
ADD COLUMN IF NOT EXISTS extraction_method VARCHAR(20) DEFAULT 'bedrock';

-- Add index for extraction method queries
CREATE INDEX IF NOT EXISTS idx_extraction_method 
ON crawl_results(extraction_method);

-- Add comment
COMMENT ON COLUMN crawl_results.raw_llm_output IS 
'Raw JSON output from LLM before normalization';

COMMENT ON COLUMN crawl_results.normalized_data IS 
'Normalized JSON data matching schema';

COMMENT ON COLUMN crawl_results.extraction_method IS 
'Method used for extraction: bedrock, regex, or keyword';
```

Run migration:
```bash
python migrate_db.py
```

### Monitoring and Observability

**Key Metrics to Monitor**:

1. **Extraction Success Rate**
   - Successful extractions / Total attempts
   - Target: > 95%

2. **LLM Response Time**
   - Average time for Bedrock API calls
   - Target: < 5 seconds

3. **Validation Failure Rate**
   - Failed validations / Total extractions
   - Target: < 5%

4. **Re-prompt Rate**
   - Re-prompts / Total extractions
   - Target: < 10%

5. **AWS Bedrock Errors**
   - Throttling errors
   - Permission errors
   - Service unavailable errors

**Logging Strategy**:

```python
# Success logging
logger.info(f"Bedrock extraction successful for {url}", extra={
    'job_id': job_id,
    'extraction_time_ms': elapsed_ms,
    'fields_extracted': len(extracted_fields),
    'model_used': model_id
})

# Error logging (without sensitive content)
logger.error(f"Bedrock extraction failed for {url}", extra={
    'job_id': job_id,
    'error_type': error_type,
    'retry_count': retry_count,
    'model_used': model_id
}, exc_info=True)

# Validation logging
logger.warning(f"Schema validation failed, re-prompting", extra={
    'job_id': job_id,
    'validation_errors': errors,
    'attempt': attempt_number
})
```

### Rollback Strategy

**If Bedrock integration causes issues**:

1. **Immediate Rollback**:
   ```bash
   # Disable Bedrock extraction
   export ENABLE_BEDROCK_EXTRACTION=false
   # Restart service
   docker-compose restart fastapi-app
   ```

2. **Gradual Rollout**:
   - Start with `ENABLE_BEDROCK_EXTRACTION=false`
   - Enable for specific job IDs or URLs
   - Monitor metrics
   - Gradually increase percentage

3. **A/B Testing**:
   - Run both regex and Bedrock in parallel
   - Compare extraction quality
   - Choose best approach per content type

### Performance Optimization

**Caching Strategy**:

```python
# Cache LLM responses for identical content
from functools import lru_cache
import hashlib

def content_hash(content: str) -> str:
    """Generate hash of content for caching."""
    return hashlib.sha256(content.encode()).hexdigest()

# In-memory cache (for single instance)
extraction_cache = {}

async def extract_with_cache(content: str, metadata: dict):
    """Extract with caching."""
    cache_key = content_hash(content)
    
    if cache_key in extraction_cache:
        logger.info(f"Cache hit for content hash {cache_key[:8]}")
        return extraction_cache[cache_key]
    
    result = await extractor.extract_structured_data(content, metadata)
    extraction_cache[cache_key] = result
    
    return result
```

**Batch Processing**:

For high-volume scenarios, consider batching:
- Process multiple pages in parallel
- Use async/await for concurrent Bedrock calls
- Implement request queuing
- Monitor rate limits

**Content Truncation**:

For very large pages:
```python
MAX_CONTENT_LENGTH = 50000  # characters

if len(content) > MAX_CONTENT_LENGTH:
    # Extract relevant section around keyword
    keyword_pos = content.lower().find(keyword.lower())
    if keyword_pos != -1:
        start = max(0, keyword_pos - MAX_CONTENT_LENGTH // 2)
        end = min(len(content), keyword_pos + MAX_CONTENT_LENGTH // 2)
        content = content[start:end]
    else:
        # No keyword found, take first chunk
        content = content[:MAX_CONTENT_LENGTH]
```

## Security Considerations

### Credential Security

1. **Never hardcode credentials** in code or configuration files
2. **Use IAM roles** in production (EC2/ECS)
3. **Rotate credentials** regularly if using access keys
4. **Use AWS Secrets Manager** for sensitive configuration
5. **Limit IAM permissions** to minimum required (principle of least privilege)

### Data Privacy

1. **Don't log sensitive content** in production
2. **Sanitize URLs** in logs (remove query parameters with tokens)
3. **Encrypt data at rest** in database
4. **Use HTTPS** for all API communications
5. **Implement data retention policies** for raw LLM output

### Input Validation

1. **Validate URLs** before processing
2. **Limit content size** to prevent memory issues
3. **Sanitize user input** (keywords, URLs)
4. **Implement rate limiting** on API endpoints
5. **Validate LLM output** before database storage

### AWS Security Best Practices

1. **Enable CloudTrail** for API call auditing
2. **Use VPC endpoints** for Bedrock (if available)
3. **Implement request signing** for API calls
4. **Monitor for unusual activity** in CloudWatch
5. **Set up billing alerts** to prevent unexpected costs

## Troubleshooting Guide

### Common Issues

**Issue**: "Bedrock service unavailable"
- **Cause**: AWS service outage or network issue
- **Solution**: Check AWS status page, verify network connectivity, implement retry logic

**Issue**: "Permission denied when invoking Bedrock"
- **Cause**: IAM role/user lacks required permissions
- **Solution**: Add `bedrock:InvokeModel` permission to IAM policy

**Issue**: "Invalid JSON response from LLM"
- **Cause**: LLM returned text instead of JSON
- **Solution**: Check system prompt, implement JSON extraction fallback, re-prompt

**Issue**: "Extraction timeout"
- **Cause**: Large content or slow model response
- **Solution**: Increase timeout, truncate content, use faster model

**Issue**: "High cost from Bedrock usage"
- **Cause**: Too many API calls or large content
- **Solution**: Implement caching, optimize prompt length, use lite model

### Debug Mode

Enable debug logging:

```bash
export LOG_LEVEL=DEBUG
export ENABLE_BEDROCK_EXTRACTION=true
```

This will log:
- Full system prompts (sanitized)
- LLM response times
- Validation errors
- Retry attempts
- Cache hits/misses

### Testing Bedrock Connection

Create a test script `test_bedrock_connection.py`:

```python
import boto3
import json

def test_bedrock_connection():
    """Test AWS Bedrock connectivity."""
    try:
        client = boto3.client('bedrock-runtime', region_name='us-east-1')
        
        response = client.invoke_model(
            modelId='amazon.titan-text-express-v1',
            contentType='application/json',
            accept='application/json',
            body=json.dumps({
                'inputText': 'Hello, this is a test.',
                'textGenerationConfig': {
                    'maxTokenCount': 100,
                    'temperature': 0.0
                }
            })
        )
        
        print("✓ Bedrock connection successful")
        print(f"Response: {response['ResponseMetadata']['HTTPStatusCode']}")
        return True
        
    except Exception as e:
        print(f"✗ Bedrock connection failed: {e}")
        return False

if __name__ == '__main__':
    test_bedrock_connection()
```

Run test:
```bash
python test_bedrock_connection.py
```

## Future Enhancements

### Potential Improvements

1. **Multi-Model Support**
   - Allow different models for different content types
   - Implement model selection based on content complexity
   - A/B test different models for quality comparison

2. **Streaming Responses**
   - Use Bedrock streaming API for faster perceived performance
   - Process partial responses as they arrive
   - Reduce overall latency

3. **Fine-Tuned Models**
   - Train custom models on domain-specific data
   - Improve extraction accuracy for specific use cases
   - Reduce prompt engineering needs

4. **Confidence Scoring**
   - Implement confidence thresholds
   - Flag low-confidence extractions for review
   - Improve extraction quality over time

5. **Active Learning**
   - Collect user feedback on extraction quality
   - Use feedback to improve prompts
   - Build training data for fine-tuning

6. **Multi-Language Support**
   - Detect content language
   - Use language-specific prompts
   - Support international date formats

7. **Structured Output Parsing**
   - Use Bedrock's structured output features (if available)
   - Reduce validation failures
   - Improve consistency

8. **Cost Optimization**
   - Implement smart caching strategies
   - Use cheaper models for simple extractions
   - Batch similar requests

## Conclusion

This design provides a comprehensive approach to replacing regex-based extraction with AWS Bedrock LLM extraction. The modular architecture allows for easy model swapping, the centralized system prompt simplifies maintenance, and robust error handling ensures reliability. The implementation phases provide a clear path from development to production deployment.

Key benefits of this approach:
- **Flexibility**: LLMs understand context better than regex
- **Maintainability**: Single system prompt to update
- **Scalability**: AWS Bedrock handles infrastructure
- **Quality**: Better extraction accuracy
- **Extensibility**: Easy to add new extraction patterns

The design maintains backward compatibility while providing a foundation for future enhancements and improvements to the extraction system.
