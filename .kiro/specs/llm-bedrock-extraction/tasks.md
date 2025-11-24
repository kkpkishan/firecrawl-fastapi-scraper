# Implementation Plan

## Overview

This implementation plan breaks down the LLM-driven Bedrock extraction feature into discrete, actionable tasks. Each task builds incrementally on previous work, ensuring the system remains functional throughout development.

## Task List

- [-] 1. Set up AWS Bedrock configuration and credentials
  - Add AWS Bedrock configuration settings to `app/config.py`
  - Add environment variables: `AWS_REGION`, `BEDROCK_MODEL_ID`, `BEDROCK_TEMPERATURE`, `BEDROCK_MAX_TOKENS`, `ENABLE_BEDROCK_EXTRACTION`
  - Implement credential chain detection (IAM role vs environment variables)
  - Add validation to fail fast if required configuration is missing
  - _Requirements: 2.1, 2.2, 2.5, 15.1, 15.2_

- [x] 1.1 Write unit tests for configuration loading
  - **Property 1: Configuration validation**
  - **Validates: Requirements 2.1, 2.2, 2.5**

- [x] 2. Create bedrock_extractor module with AWS SDK integration
  - Create `app/bedrock_extractor.py` module
  - Implement `BedrockExtractor` class with AWS Bedrock client initialization
  - Implement credential chain handling using boto3
  - Add singleton pattern with `get_extractor()` function
  - Implement basic error handling for AWS SDK initialization
  - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_

- [x] 2.1 Write unit tests for AWS client initialization
  - **Property 2: AWS credential chain usage**
  - **Validates: Requirements 2.3**

- [x] 3. Design and implement system prompt template
  - Create comprehensive system prompt with JSON schema definition
  - Include strict output rules (valid JSON only, no comments)
  - Document all database schema fields in the prompt
  - Add placeholders for runtime variables (keyword, url, content_type, parent_url, content)
  - Implement prompt formatting function
  - _Requirements: 3.1, 3.2, 3.3, 3.4_

- [x] 3.1 Write unit tests for prompt template formatting
  - **Property 3: Prompt variable substitution**
  - **Validates: Requirements 3.1, 3.2, 3.3**

- [x] 4. Implement LLM invocation with metadata context
  - Implement `extract_structured_data()` method in `BedrockExtractor`
  - Build metadata dict with url, content_type, parent_url, keyword
  - Construct full prompt with system prompt + metadata + content
  - Invoke AWS Bedrock API with configured model and parameters
  - Pass temperature and max_tokens parameters from configuration
  - Return raw LLM response
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 15.3, 15.4_

- [x] 4.1 Write property test for metadata inclusion
  - **Property 4: LLM receives complete context**
  - **Validates: Requirements 4.1, 4.2, 4.3, 4.4**

- [x] 4.2 Write property test for LLM parameter passing
  - **Property 27: Temperature parameter passing**
  - **Property 28: Max tokens parameter passing**
  - **Validates: Requirements 15.3, 15.4**

- [x] 5. Implement JSON parsing with fallback extraction
  - Implement JSON parsing from LLM response
  - Add fallback logic to extract JSON from text using regex if direct parsing fails
  - Handle cases where LLM returns JSON in markdown code blocks
  - Log parsing errors with sanitized content
  - _Requirements: 5.1, 5.2_

- [x] 5.1 Write property test for JSON parsing
  - **Property 6: JSON parsing for all responses**
  - **Validates: Requirements 5.1, 5.2**

- [x] 6. Implement JSON schema validation
  - Create `validate_extraction_schema()` function
  - Validate required top-level fields (page_info, extracted_fields, dates, metadata)
  - Validate field types and structures
  - Validate date format (ISO 8601)
  - Return validation errors as list of specific error messages
  - _Requirements: 5.3_

- [x] 6.1 Write property test for schema validation
  - **Property 7: Schema validation enforcement**
  - **Validates: Requirements 5.3**

- [x] 7. Implement re-prompting logic for validation failures
  - Implement retry logic with max 2 attempts
  - Construct fix prompt with specific validation errors
  - Re-invoke LLM with fix instructions
  - Track retry count and log retry attempts
  - Mark extraction as failed after exhausting retries
  - _Requirements: 5.4, 5.5_

- [x] 7.1 Write property test for retry behavior
  - **Property 8: Retry on validation failure**
  - **Validates: Requirements 5.4, 5.5**

- [-] 8. Implement data normalization functions
  - Create `normalize_extracted_data()` function
  - Implement whitespace trimming for all string fields (recursive)
  - Implement HTML tag removal using regex
  - Implement date normalization to ISO 8601 format
  - Implement numeric string to number conversion
  - Set default values (null or empty arrays) for missing optional fields
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [ ] 8.1 Write property tests for normalization
  - **Property 9: String normalization**
  - **Property 10: HTML tag removal**
  - **Property 11: Date normalization**
  - **Property 12: Type conversion for numerics**
  - **Property 13: Default values for optional fields**
  - **Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5**

- [x] 9. Update database models for LLM extraction
  - Add `raw_llm_output` column to `CrawlResult` model (Text, nullable)
  - Add `normalized_data` column to `CrawlResult` model (Text, nullable)
  - Add `extraction_method` column to `CrawlResult` model (String(20), default='bedrock')
  - Update `to_dict()` method to include new fields
  - _Requirements: 7.3, 7.4_

- [x] 10. Create database migration script
  - Create `migrations/add_bedrock_fields.sql` with ALTER TABLE statements
  - Add columns: raw_llm_output, normalized_data, extraction_method
  - Add index on extraction_method column
  - Add column comments for documentation
  - Create Python migration runner script `migrate_db.py`
  - Test migration on local database
  - _Requirements: 7.3, 7.4_

- [-] 11. Update database functions to store LLM data
  - Modify `create_result()` function in `database.py`
  - Add parameters: raw_llm_output, normalized_data, extraction_method
  - Store both raw and normalized JSON in database
  - Maintain backward compatibility with existing calls
  - _Requirements: 7.1, 7.2_

- [ ] 11.1 Write property test for dual storage
  - **Property 14: Dual storage of extraction results**
  - **Validates: Requirements 7.1, 7.2**

- [x] 12. Integrate Bedrock extractor into main application
  - Modify `extract_and_store_results()` in `app/main.py`
  - Replace `get_extractor()` (regex) with `get_bedrock_extractor()`
  - Build metadata dict for each page (url, title, content_type, keyword)
  - Call `extractor.extract_structured_data()` instead of regex extraction
  - Handle extraction errors gracefully
  - Continue processing other pages on individual failures
  - _Requirements: 1.1, 1.2, 1.4_

- [ ] 12.1 Write property test for Bedrock usage
  - **Property 1: Bedrock extraction replaces regex for all content**
  - **Validates: Requirements 1.1, 1.2**

- [-] 13. Implement document metadata extraction
  - Modify document processing flow to extract metadata
  - For PDFs: extract page count
  - For Excel: extract sheet names
  - For Word: extract section count
  - Pass document metadata to LLM along with extracted text
  - _Requirements: 4.5_

- [ ] 13.1 Write property test for document metadata
  - **Property 5: Document metadata inclusion**
  - **Validates: Requirements 4.5**

- [x] 14. Integrate document extraction with Bedrock
  - Update document URL handling in `extract_and_store_results()`
  - Call Document Extractor for PDF, Word, Excel URLs
  - Pass extracted text and metadata to Bedrock extractor
  - Set content_type metadata appropriately (pdf, docx, xlsx)
  - Handle document extraction failures gracefully
  - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

- [ ] 14.1 Write property tests for document processing
  - **Property 16: Document extractor invocation**
  - **Property 17: Document text to LLM**
  - **Property 18: Graceful document extraction failure**
  - **Validates: Requirements 8.1, 8.2, 8.3, 8.4, 8.5**

- [-] 15. Implement comprehensive error handling for AWS Bedrock
  - Handle service unavailable errors (503) with logging and job failure
  - Handle permission denied errors (403) with clear error messages
  - Handle throttling errors (429) - will be enhanced in next task
  - Handle timeout errors with logging
  - Ensure no sensitive content is logged in production
  - _Requirements: 9.1, 9.2, 9.4, 9.5_

- [ ] 15.1 Write property tests for error handling
  - **Property 19: Bedrock unavailability handling**
  - **Property 20: Permission error handling**
  - **Property 22: Timeout error handling**
  - **Property 23: Sensitive content protection in logs**
  - **Validates: Requirements 9.1, 9.2, 9.4, 9.5**

- [x] 16. Implement exponential backoff for throttling
  - Implement exponential backoff retry logic (1s, 2s, 4s)
  - Add jitter to prevent thundering herd
  - Retry throttled requests up to 3 times
  - Log throttling events for monitoring
  - Mark job as failed with throttling error after exhausting retries
  - _Requirements: 14.1, 14.2, 14.3, 14.4_

- [ ] 16.1 Write property tests for throttling handling
  - **Property 24: Exponential backoff for throttling**
  - **Property 25: Throttling retry exhaustion**
  - **Property 26: Throttling event logging**
  - **Validates: Requirements 14.1, 14.2, 14.3, 14.4**

- [ ] 17. Implement invalid JSON error handling
  - Handle cases where LLM returns invalid JSON after retries
  - Log raw response (sanitized) for debugging
  - Mark extraction as failed with clear error message
  - Store error details in database
  - _Requirements: 9.3_

- [ ] 17.1 Write property test for invalid JSON handling
  - **Property 21: Invalid JSON error handling**
  - **Validates: Requirements 9.3**

- [-] 18. Update API responses to return normalized data
  - Modify `get_crawl_status()` endpoint to include normalized_data
  - Return normalized data by default in API responses
  - Optionally include raw_llm_output if requested
  - Maintain backward compatibility with existing response format
  - _Requirements: 7.5, 1.5_

- [ ] 18.1 Write property test for API responses
  - **Property 15: Normalized data in API responses**
  - **Property 3: API backward compatibility**
  - **Validates: Requirements 7.5, 1.5**

- [x] 19. Update Docker Compose configuration
  - Add AWS environment variables to docker-compose.yaml
  - Add AWS_REGION, BEDROCK_MODEL_ID, BEDROCK_TEMPERATURE, BEDROCK_MAX_TOKENS
  - Add passthrough for AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY (optional)
  - Add volume mount for ~/.aws directory (optional, for local development)
  - Document IAM role usage for EC2/ECS deployment
  - _Requirements: 11.2_

- [x] 20. Add startup logging for Bedrock integration
  - Log whether Bedrock extraction is enabled or disabled
  - Log configured AWS region and model ID
  - Log credential source (IAM role vs environment variables)
  - Add clear error messages for missing configuration
  - _Requirements: 11.5_

- [ ] 21. Create comprehensive documentation
  - Create `docs/bedrock-integration.md` file
  - Document system prompt and its structure
  - Include complete JSON schema with examples
  - Provide example LLM input and expected output
  - Explain how to update schema when database changes
  - Document IAM role setup for EC2/ECS
  - Add troubleshooting guide
  - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5_

- [ ] 22. Update README with Bedrock setup instructions
  - Add section on AWS Bedrock integration
  - Document required environment variables
  - Explain IAM role vs access key authentication
  - Provide setup instructions for local development
  - Provide deployment instructions for EC2/ECS
  - Add link to detailed documentation
  - _Requirements: 11.1, 11.3_

- [ ] 23. Create integration tests for full extraction flow
  - Create `tests/test_bedrock_integration.py`
  - Test full flow: Firecrawl → Bedrock → Database
  - Test with HTML content
  - Test with PDF documents
  - Test with Word documents
  - Test with Excel files
  - Mock AWS Bedrock for testing
  - _Requirements: 13.4, 13.5_

- [ ] 23.1 Write integration tests for content types
  - **Property 2: Firecrawl integration preservation**
  - **Validates: Requirements 1.3, 1.4, 13.4, 13.5**

- [ ] 24. Create property-based tests
  - Create `tests/test_bedrock_properties.py`
  - Implement property tests for extraction behavior
  - Implement property tests for normalization
  - Implement property tests for error handling
  - Use hypothesis or similar library for property generation
  - _Requirements: 13.1, 13.2, 13.3_

- [ ] 25. Test end-to-end flow with docker-compose
  - Start all services with `docker-compose up`
  - Verify Backend Service starts successfully
  - Submit test crawl job via API
  - Verify Firecrawl crawls the URL
  - Verify Bedrock extraction occurs
  - Verify results are stored in database with raw and normalized data
  - Query results via API and verify response format
  - _Requirements: 11.1, 11.4_

- [ ] 26. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.
