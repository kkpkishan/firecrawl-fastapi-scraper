# Requirements Document

## Introduction

This document specifies the requirements for replacing the current regex-based page scraping in the Vibe backend with an LLM-driven extraction flow using AWS Bedrock. The system will leverage large language models to intelligently understand and extract structured data from web pages and documents (PDFs, Word, Excel, etc.) crawled by Firecrawl. The LLM will interpret content based on a defined schema and return clean, validated JSON that matches the database structure. This approach provides more flexible, context-aware extraction compared to rigid regex patterns.

## Glossary

- **Backend Service**: The FastAPI application that orchestrates crawling jobs and serves results via REST API
- **AWS Bedrock**: Amazon's managed service for accessing foundation models from various AI providers
- **LLM**: Large Language Model - an AI model capable of understanding and generating human-like text
- **Bedrock Model**: The specific foundation model used for extraction (e.g., Amazon Titan, Claude, etc.)
- **System Prompt**: A predefined instruction set that guides the LLM on how to extract and structure data
- **Extraction Schema**: The JSON structure definition that specifies what data to extract and how to format it
- **IAM Role**: AWS Identity and Access Management role that grants permissions to invoke Bedrock models
- **Credential Chain**: AWS SDK's automatic credential discovery mechanism (IAM roles, environment variables, etc.)
- **JSON Validation**: The process of verifying that LLM output conforms to the expected schema
- **Raw Extraction**: The unprocessed JSON output directly from the LLM
- **Normalized Data**: Cleaned and validated data that matches the database schema exactly
- **Firecrawl**: An open-source web crawling service that fetches web pages and converts them to structured formats
- **Document Extractor**: The existing module that extracts text from PDFs, Word, Excel, and other document formats

## Requirements

### Requirement 1

**User Story:** As a developer, I want to remove regex-based extraction logic, so that the system uses intelligent LLM-based understanding instead of brittle pattern matching

#### Acceptance Criteria

1. WHEN the Backend Service processes crawled content, THE Backend Service SHALL use AWS Bedrock for data extraction instead of regex patterns
2. WHEN regex extraction is disabled, THE Backend Service SHALL not execute any regex pattern matching on page content
3. THE Backend Service SHALL maintain the existing Firecrawl integration for crawling and content retrieval
4. WHEN a crawl job completes, THE Backend Service SHALL pass Firecrawl's markdown content to the LLM extraction module
5. THE Backend Service SHALL preserve backward compatibility with existing API endpoints and response formats

### Requirement 2

**User Story:** As a system administrator, I want to configure AWS Bedrock integration via environment variables, so that I can manage credentials and model selection securely

#### Acceptance Criteria

1. THE Backend Service SHALL read AWS region from environment variable AWS_REGION
2. THE Backend Service SHALL read Bedrock model identifier from environment variable BEDROCK_MODEL_ID
3. WHERE AWS credentials are needed, THE Backend Service SHALL use the AWS default credential chain
4. WHEN running on EC2 or ECS with an IAM role, THE Backend Service SHALL automatically use that role for authentication
5. WHEN environment variables AWS_REGION or BEDROCK_MODEL_ID are not set, THE Backend Service SHALL fail to start with a clear error message indicating which variables are missing

### Requirement 3

**User Story:** As a developer, I want a centralized system prompt for LLM extraction, so that I can modify the extraction logic in one place without changing code

#### Acceptance Criteria

1. THE Backend Service SHALL define a single system prompt that describes the extraction task and output schema
2. THE system prompt SHALL specify the exact JSON structure that the LLM must return
3. THE system prompt SHALL include strict rules requiring valid JSON output with no comments or extra text
4. THE system prompt SHALL describe all database schema fields including field names, types, and whether they are required or optional
5. WHEN the database schema changes, THE system prompt SHALL be the only artifact requiring updates for extraction logic

### Requirement 4

**User Story:** As a developer, I want the LLM to receive comprehensive context about each page, so that it can make informed extraction decisions

#### Acceptance Criteria

1. WHEN invoking the LLM, THE Backend Service SHALL provide the page URL as metadata
2. WHEN invoking the LLM, THE Backend Service SHALL provide the content type (HTML, PDF, DOCX, etc.) as metadata
3. WHERE a page is nested content, THE Backend Service SHALL provide the parent URL as metadata
4. WHEN invoking the LLM, THE Backend Service SHALL provide the full page content in markdown format
5. WHEN a document is processed, THE Backend Service SHALL include document-specific metadata such as page count or sheet names

### Requirement 5

**User Story:** As a developer, I want the system to validate LLM output against the expected schema, so that invalid data does not corrupt the database

#### Acceptance Criteria

1. WHEN the LLM returns a response, THE Backend Service SHALL parse the response as JSON
2. WHEN JSON parsing fails, THE Backend Service SHALL log the error and attempt to extract JSON from the response text
3. WHEN parsed JSON does not match the expected schema, THE Backend Service SHALL validate each required field
4. WHEN validation fails, THE Backend Service SHALL re-prompt the LLM with an explicit instruction to fix the JSON schema mismatch
5. WHEN re-prompting fails after 2 attempts, THE Backend Service SHALL mark the extraction as failed and store an error message

### Requirement 6

**User Story:** As a developer, I want extracted data to be cleaned and normalized, so that it meets database constraints and formatting requirements

#### Acceptance Criteria

1. WHEN the LLM returns extracted data, THE Backend Service SHALL trim whitespace from all string fields
2. WHEN the LLM returns HTML tags in extracted text, THE Backend Service SHALL remove HTML tags unless the schema explicitly allows them
3. WHERE date fields are present, THE Backend Service SHALL normalize dates to ISO 8601 format
4. WHEN numeric fields are extracted as strings, THE Backend Service SHALL convert them to appropriate numeric types
5. WHEN optional fields are missing from LLM output, THE Backend Service SHALL set them to null or empty arrays as appropriate

### Requirement 7

**User Story:** As a developer, I want to store both raw and normalized extraction results, so that I can debug issues and audit LLM output quality

#### Acceptance Criteria

1. WHEN extraction succeeds, THE Backend Service SHALL store the raw JSON output from the LLM
2. WHEN extraction succeeds, THE Backend Service SHALL store the normalized JSON that matches the database schema
3. THE PostgreSQL Database SHALL contain a column for raw LLM output in the crawl_results table
4. THE PostgreSQL Database SHALL contain columns for normalized structured data in the crawl_results table
5. WHEN querying results via API, THE Backend Service SHALL return the normalized data by default

### Requirement 8

**User Story:** As a developer, I want the system to handle nested documents like PDFs and Word files, so that I can extract data from any content type Firecrawl retrieves

#### Acceptance Criteria

1. WHEN Firecrawl returns a PDF URL, THE Backend Service SHALL use the Document Extractor to extract text content
2. WHEN Firecrawl returns a Word document URL, THE Backend Service SHALL use the Document Extractor to extract text content
3. WHEN Firecrawl returns an Excel file URL, THE Backend Service SHALL use the Document Extractor to extract tabular data
4. WHEN document extraction succeeds, THE Backend Service SHALL pass the extracted text to the LLM with document type metadata
5. WHEN document extraction fails, THE Backend Service SHALL log the error and continue processing other pages

### Requirement 9

**User Story:** As a system administrator, I want comprehensive error handling for Bedrock integration, so that failures are logged and jobs are marked appropriately

#### Acceptance Criteria

1. WHEN AWS Bedrock is unavailable, THE Backend Service SHALL log the error and mark the job as failed with a clear error message
2. WHEN the IAM role lacks bedrock:InvokeModel permission, THE Backend Service SHALL log the permission error and mark the job as failed
3. WHEN the LLM returns invalid JSON after retry attempts, THE Backend Service SHALL log the raw response and mark the extraction as failed
4. WHEN the LLM request times out, THE Backend Service SHALL log the timeout and mark the job as failed
5. WHEN any Bedrock error occurs, THE Backend Service SHALL not log sensitive page content in production logs

### Requirement 10

**User Story:** As a developer, I want the Bedrock integration isolated in a service module, so that I can swap models or adjust prompts without affecting other code

#### Acceptance Criteria

1. THE Backend Service SHALL implement Bedrock integration in a separate module named bedrock_extractor.py
2. THE bedrock_extractor module SHALL expose a single function for extracting structured data from text
3. THE bedrock_extractor module SHALL handle all AWS SDK interactions and credential management
4. WHEN the extraction module is called, THE module SHALL accept text content, metadata, and schema definition as parameters
5. THE bedrock_extractor module SHALL return a tuple of (extracted_data, error_message) similar to existing extractor modules

### Requirement 11

**User Story:** As a developer, I want to test the full extraction flow locally using Docker Compose, so that I can verify functionality before deployment

#### Acceptance Criteria

1. WHEN running docker-compose up, THE Backend Service SHALL start with all dependencies including database
2. THE Docker Compose configuration SHALL support AWS credential passthrough via environment variables
3. WHERE AWS credentials are configured, THE Backend Service SHALL successfully connect to AWS Bedrock
4. WHEN submitting a test crawl job, THE system SHALL complete the full flow from Firecrawl to Bedrock to database storage
5. THE Backend Service SHALL provide clear log messages indicating whether Bedrock integration is enabled or disabled

### Requirement 12

**User Story:** As a developer, I want comprehensive documentation of the Bedrock integration, so that I can understand and maintain the system

#### Acceptance Criteria

1. THE project SHALL contain a documentation file at docs/bedrock-integration.md
2. THE documentation SHALL describe the system prompt and its structure
3. THE documentation SHALL include the complete JSON schema used for extraction
4. THE documentation SHALL provide examples of LLM input and expected output
5. THE documentation SHALL explain how to update the schema when database structure changes

### Requirement 13

**User Story:** As a developer, I want unit and integration tests for Bedrock extraction, so that I can verify correctness and catch regressions

#### Acceptance Criteria

1. THE project SHALL contain unit tests for the bedrock_extractor module
2. THE unit tests SHALL verify JSON parsing and validation logic
3. THE unit tests SHALL verify error handling for invalid LLM responses
4. THE integration tests SHALL verify the full flow from crawled content to database storage
5. THE integration tests SHALL verify handling of different content types (HTML, PDF, Word, Excel)

### Requirement 14

**User Story:** As a system administrator, I want the system to handle rate limits and throttling from AWS Bedrock, so that the service remains stable under load

#### Acceptance Criteria

1. WHEN AWS Bedrock returns a throttling error, THE Backend Service SHALL implement exponential backoff retry logic
2. THE Backend Service SHALL retry throttled requests up to 3 times with increasing delays
3. WHEN retries are exhausted, THE Backend Service SHALL mark the job as failed with a throttling error message
4. THE Backend Service SHALL log throttling events for monitoring and capacity planning
5. WHEN processing multiple concurrent jobs, THE Backend Service SHALL respect Bedrock API rate limits

### Requirement 15

**User Story:** As a developer, I want to configure LLM parameters like temperature and max tokens, so that I can optimize extraction quality and cost

#### Acceptance Criteria

1. THE Backend Service SHALL read LLM temperature from environment variable BEDROCK_TEMPERATURE with default value 0.0
2. THE Backend Service SHALL read max output tokens from environment variable BEDROCK_MAX_TOKENS with default value 4096
3. WHEN invoking Bedrock, THE Backend Service SHALL pass the configured temperature parameter
4. WHEN invoking Bedrock, THE Backend Service SHALL pass the configured max tokens parameter
5. THE system prompt SHALL be optimized to produce concise JSON output within token limits
