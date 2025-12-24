"""
AWS Bedrock-Based Data Extraction Module

This module provides LLM-based extraction using AWS Bedrock for intelligent
understanding and extraction of structured data from web content.
"""
import json
import logging
import re
from typing import Dict, Optional, Tuple, Any, List, Union
from datetime import datetime
import boto3
from botocore.exceptions import ClientError, BotoCoreError
from config import settings

logger = logging.getLogger(__name__)


class BedrockExtractor:
    """
    LLM-based extractor using AWS Bedrock for intelligent data extraction.
    
    Features:
    - Uses AWS Bedrock foundation models for extraction
    - Automatic AWS credential chain detection
    - Schema-driven extraction with validation
    - Retry logic for transient failures
    """
    
    def __init__(self):
        """Initialize extractor with AWS Bedrock client."""
        self.enabled = settings.enable_bedrock_extraction
        self.model_id = settings.bedrock_model_id
        self.temperature = settings.bedrock_temperature
        self.max_tokens = settings.bedrock_max_tokens
        self.max_retries = settings.bedrock_max_retries
        self.retry_delay = settings.bedrock_retry_delay
        
        # Initialize AWS Bedrock client if enabled
        self.client = None
        if self.enabled:
            try:
                self._initialize_client()
                logger.info(f"BedrockExtractor initialized with model: {self.model_id}")
                logger.info(f"AWS Region: {settings.aws_region}")
                logger.info(f"Temperature: {self.temperature}, Max Tokens: {self.max_tokens}")
            except Exception as e:
                logger.error(f"Failed to initialize Bedrock client: {e}")
                self.enabled = False
                raise
        else:
            logger.info("BedrockExtractor disabled in configuration")
    
    def _initialize_client(self):
        """
        Initialize AWS Bedrock client using credential chain or bearer token.
        
        Authentication priority:
        1. Bearer token (AWS_BEARER_TOKEN_BEDROCK) if provided
        2. IAM role attached to EC2/ECS instance (recommended for production)
        3. Environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
        4. AWS credentials file (~/.aws/credentials)
        5. IAM role from ECS task definition
        
        Raises:
            Exception: If client initialization fails
        """
        try:
            # Check if bearer token is provided
            if settings.aws_bearer_token_bedrock:
                logger.info("Using AWS Bedrock bearer token for authentication")
                # Create client with bearer token
                # Note: boto3 doesn't natively support bearer tokens for Bedrock
                # We'll need to use custom request signing or HTTP client
                # For now, store the token for use in API calls
                self.bearer_token = settings.aws_bearer_token_bedrock
                
                # Create a basic client for the region
                self.client = boto3.client(
                    service_name='bedrock-runtime',
                    region_name=settings.aws_region
                )
                logger.info("Bedrock client initialized with bearer token")
            else:
                # Create Bedrock runtime client using standard credential chain
                # boto3 automatically uses the credential chain
                self.client = boto3.client(
                    service_name='bedrock-runtime',
                    region_name=settings.aws_region
                )
                
                # Log credential source (without exposing sensitive data)
                session = boto3.Session()
                credentials = session.get_credentials()
                if credentials:
                    # Determine credential source
                    if hasattr(credentials, 'method'):
                        logger.info(f"AWS credentials source: {credentials.method}")
                    else:
                        logger.info("AWS credentials loaded successfully")
                else:
                    logger.warning("No AWS credentials found in credential chain")
                
                self.bearer_token = None
                
        except Exception as e:
            logger.error(f"Failed to create Bedrock client: {e}")
            raise
    
    async def extract_structured_data(
        self,
        content: str,
        metadata: Dict[str, Any],
        schema_hint: Optional[str] = None
    ) -> Tuple[Optional[Dict], Optional[str]]:
        """
        Extract structured data from content using LLM with retry logic.
        
        Args:
            content: Text content to extract from (markdown format)
            metadata: Dict with url, content_type, parent_url, keyword, etc.
            schema_hint: Optional schema override (not used currently)
            
        Returns:
            Tuple of (extracted_data_dict, error_message)
            - extracted_data_dict: Parsed JSON data if successful, None if failed
            - error_message: Error description if failed, None if successful
        """
        if not self.enabled:
            return None, "Bedrock extraction is disabled"
        
        if not content or not content.strip():
            return None, "Empty content provided"
        
        if not self.client:
            return None, "Bedrock client not initialized"
        
        # Build the initial prompt
        prompt = self._build_prompt(content, metadata)
        
        # Try extraction with retries and exponential backoff for throttling
        import asyncio
        import random
        
        throttle_retry_count = 0
        max_throttle_retries = 3
        
        for attempt in range(self.max_retries + 1):
            try:
                # Invoke LLM
                response_text = await self._invoke_bedrock(prompt)
                
                # Reset throttle counter on successful invocation
                throttle_retry_count = 0
                
                # Parse response
                extracted_data, parse_error = self._parse_llm_response(response_text)
                
                if parse_error:
                    if attempt < self.max_retries:
                        logger.warning(f"Parse error on attempt {attempt + 1}: {parse_error}")
                        # Construct fix prompt
                        prompt = self._build_fix_prompt(response_text, parse_error, content, metadata)
                        continue
                    else:
                        return None, f"Failed to parse LLM response after {self.max_retries + 1} attempts: {parse_error}"
                
                # Validate schema
                is_valid, validation_errors = validate_extraction_schema(extracted_data)
                
                if not is_valid:
                    if attempt < self.max_retries:
                        logger.warning(f"Validation failed on attempt {attempt + 1}: {validation_errors}")
                        # Construct fix prompt with validation errors
                        prompt = self._build_validation_fix_prompt(extracted_data, validation_errors, content, metadata)
                        continue
                    else:
                        error_msg = f"Schema validation failed after {self.max_retries + 1} attempts: {'; '.join(validation_errors)}"
                        return None, error_msg
                
                # Success!
                if attempt > 0:
                    logger.info(f"Extraction succeeded on attempt {attempt + 1}")
                return extracted_data, None
                
            except Exception as e:
                error_str = str(e)
                
                # Check if this is a throttling error
                is_throttling = 'throttl' in error_str.lower() or 'rate limit' in error_str.lower()
                
                if is_throttling and throttle_retry_count < max_throttle_retries:
                    throttle_retry_count += 1
                    
                    # Exponential backoff: 1s, 2s, 4s
                    base_delay = 2 ** (throttle_retry_count - 1)  # 1, 2, 4
                    
                    # Add jitter (random 0-50% of base delay) to prevent thundering herd
                    jitter = random.uniform(0, base_delay * 0.5)
                    delay = base_delay + jitter
                    
                    logger.warning(f"Throttling detected (attempt {throttle_retry_count}/{max_throttle_retries}). Retrying in {delay:.2f}s with exponential backoff")
                    
                    await asyncio.sleep(delay)
                    
                    # Don't increment the main attempt counter for throttling retries
                    continue
                
                elif is_throttling:
                    # Exhausted throttle retries
                    error_msg = f"Bedrock throttling error: Request throttled after {max_throttle_retries} retry attempts with exponential backoff"
                    logger.error(error_msg)
                    return None, error_msg
                
                # Non-throttling error
                if attempt < self.max_retries:
                    logger.warning(f"Extraction error on attempt {attempt + 1}: {e}")
                    continue
                else:
                    error_msg = f"Bedrock extraction failed after {self.max_retries + 1} attempts: {error_str}"
                    logger.error(error_msg)
                    return None, error_msg
        
        return None, "Extraction failed: max retries exhausted"
    
    def _build_prompt(self, content: str, metadata: Dict[str, Any]) -> str:
        """
        Build the complete prompt for LLM extraction.
        
        Args:
            content: Page content in markdown
            metadata: Metadata dict
            
        Returns:
            Complete prompt string
        """
        # Extract metadata fields
        url = metadata.get('url', 'unknown')
        content_type = metadata.get('content_type', 'html')
        parent_url = metadata.get('parent_url', 'none')
        keyword = metadata.get('keyword', '')
        title = metadata.get('title', '')
        
        # Build system prompt with schema
        system_prompt = self._get_system_prompt()
        
        # Format prompt with metadata
        prompt = system_prompt.format(
            keyword=keyword,
            url=url,
            content_type=content_type,
            parent_url=parent_url,
            model_id=self.model_id,
            content=content[:10000]  # Limit content to avoid token limits
        )
        
        return prompt
    
    def _get_system_prompt(self) -> str:
        """
        Get the system prompt template for extraction.
        
        Returns:
            System prompt string with placeholders
        """
        # Use simplified prompt for Amazon Titan models
        if 'titan' in self.model_id.lower():
            return self._get_titan_prompt()
        
        # Use detailed prompt for Claude models
        return """You are a data extraction assistant for a web scraping system. Your task is to analyze web page content and extract structured information according to a specific schema.

## Task

Extract relevant information from the provided web page content. Focus on finding data that matches the user's search keyword and any related structured information.

## Output Format

You MUST return ONLY valid JSON with no additional text, comments, or explanations. The JSON must follow this exact schema:

{{
  "page_info": {{
    "title": "string - page title",
    "url": "string - page URL",
    "summary": "string - brief summary (max 500 characters)"
  }},
  "extracted_fields": [
    {{
      "key": "string - field name/label",
      "value": "string - extracted value",
      "confidence": "high|medium|low",
      "context": "string - surrounding text for context"
    }}
  ],
  "dates": [
    {{
      "label": "string - what this date represents",
      "value": "string - date in ISO 8601 format (YYYY-MM-DD)",
      "context": "string - surrounding text"
    }}
  ],
  "metadata": {{
    "extraction_timestamp": "string - current timestamp in ISO 8601 format",
    "model_used": "string - model identifier",
    "content_type": "string - html|pdf|docx|xlsx|etc"
  }}
}}

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
- Parent URL: {parent_url}
- Search Keyword: {keyword}

Use this metadata to provide context-aware extraction.

## Content to Analyze

{content}
"""
    
    def _get_titan_prompt(self) -> str:
        """
        Get simplified prompt for Amazon Titan models.
        Titan models need simpler, more direct instructions.
        
        Returns:
            Simplified prompt string with placeholders
        """
        return """Extract exam information from the following document.

Find all exam names, exam dates, and related information.

Return your answer as valid JSON only, with this structure:

{{
  "page_info": {{
    "title": "document title",
    "url": "{url}",
    "summary": "brief summary"
  }},
  "extracted_fields": [
    {{
      "key": "Exam Name",
      "value": "the exam name",
      "confidence": "high",
      "context": "surrounding text"
    }}
  ],
  "dates": [
    {{
      "label": "Exam Date",
      "value": "2026-05-24",
      "context": "surrounding text"
    }}
  ],
  "metadata": {{
    "extraction_timestamp": "2025-12-23T10:00:00Z",
    "model_used": "{model_id}",
    "content_type": "{content_type}"
  }}
}}

Important:
- Return ONLY the JSON, no other text
- Dates must be in YYYY-MM-DD format
- Extract all exam names and dates you find
- Use "high", "medium", or "low" for confidence

Document content:

{content}
"""
    
    async def _invoke_bedrock(self, prompt: str) -> str:
        """
        Invoke AWS Bedrock API with the prompt.
        
        Args:
            prompt: Complete prompt string
            
        Returns:
            LLM response text
            
        Raises:
            Exception: If invocation fails
        """
        try:
            # Prepare request body based on model type
            if 'titan' in self.model_id.lower():
                # Amazon Titan models
                request_body = {
                    "inputText": prompt,
                    "textGenerationConfig": {
                        "temperature": self.temperature,
                        "maxTokenCount": self.max_tokens,
                        "topP": 0.9,
                        "stopSequences": []
                    }
                }
            elif 'claude-3' in self.model_id.lower():
                # Anthropic Claude 3 models (new format)
                request_body = {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": self.max_tokens,
                    "temperature": self.temperature,
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ]
                }
            elif 'claude' in self.model_id.lower():
                # Anthropic Claude 2 models (old format)
                request_body = {
                    "prompt": f"\n\nHuman: {prompt}\n\nAssistant:",
                    "temperature": self.temperature,
                    "max_tokens_to_sample": self.max_tokens,
                    "top_p": 0.9
                }
            else:
                # Generic format
                request_body = {
                    "inputText": prompt,
                    "textGenerationConfig": {
                        "temperature": self.temperature,
                        "maxTokenCount": self.max_tokens
                    }
                }
            
            # Invoke model with bearer token if available
            if hasattr(self, 'bearer_token') and self.bearer_token:
                # Use bearer token authentication
                # Note: This requires custom HTTP headers
                import httpx
                
                # Construct Bedrock API endpoint
                endpoint = f"https://bedrock-runtime.{settings.aws_region}.amazonaws.com/model/{self.model_id}/invoke"
                
                headers = {
                    "Authorization": f"Bearer {self.bearer_token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                }
                
                async with httpx.AsyncClient() as client:
                    try:
                        response = await client.post(
                            endpoint,
                            headers=headers,
                            json=request_body,
                            timeout=60.0
                        )
                        response.raise_for_status()
                        response_body = response.json()
                        
                        # Debug: Log the response structure
                        logger.debug(f"Bedrock response keys: {list(response_body.keys())}")
                        logger.debug(f"Bedrock response body (first 500 chars): {str(response_body)[:500]}")
                        
                    except httpx.TimeoutException:
                        logger.error("Bedrock request timeout via bearer token")
                        raise Exception("Bedrock request timed out. The model may be overloaded.")
                    except httpx.HTTPStatusError as e:
                        status_code = e.response.status_code
                        if status_code == 503:
                            logger.error("Bedrock service unavailable (503)")
                            raise Exception("Bedrock service is currently unavailable. Please try again later.")
                        elif status_code == 403:
                            logger.error("Bedrock permission denied (403)")
                            raise Exception("Access denied to Bedrock. Check bearer token permissions.")
                        elif status_code == 429:
                            logger.warning("Bedrock throttling (429)")
                            raise Exception("Bedrock API rate limit exceeded. Request throttled.")
                        else:
                            logger.error(f"Bedrock HTTP error: {status_code}")
                            raise Exception(f"Bedrock API error: HTTP {status_code}")
            else:
                # Use standard boto3 client with credential chain
                response = self.client.invoke_model(
                    modelId=self.model_id,
                    contentType="application/json",
                    accept="application/json",
                    body=json.dumps(request_body)
                )
                
                # Parse response
                response_body = json.loads(response['body'].read())
            
            # Extract text based on model type
            if 'titan' in self.model_id.lower():
                response_text = response_body.get('results', [{}])[0].get('outputText', '')
            elif 'claude-3' in self.model_id.lower():
                # Claude 3 format: content is in messages array
                content = response_body.get('content', [])
                if content and len(content) > 0:
                    response_text = content[0].get('text', '')
                else:
                    response_text = ''
            elif 'claude' in self.model_id.lower():
                # Claude 2 format
                response_text = response_body.get('completion', '')
            else:
                response_text = response_body.get('outputText', '') or response_body.get('completion', '')
            
            return response_text
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_message = e.response.get('Error', {}).get('Message', str(e))
            
            # Handle specific AWS Bedrock errors
            if error_code == 'ServiceUnavailable' or error_code == '503':
                # Service unavailable (503)
                logger.error(f"Bedrock service unavailable: {error_message}")
                raise Exception(f"Bedrock service is currently unavailable. Please try again later.")
            
            elif error_code == 'AccessDeniedException' or error_code == '403':
                # Permission denied (403)
                logger.error(f"Bedrock permission denied: {error_message}")
                raise Exception(f"Access denied to Bedrock. Check IAM permissions for bedrock:InvokeModel")
            
            elif error_code == 'ThrottlingException' or error_code == '429':
                # Throttling (429) - will be handled by retry logic
                logger.warning(f"Bedrock throttling: {error_message}")
                raise Exception(f"Bedrock API rate limit exceeded. Request throttled.")
            
            elif error_code == 'ValidationException' or error_code == '400':
                # Invalid request (400)
                logger.error(f"Bedrock validation error: {error_message}")
                # Don't log sensitive content in production
                if settings.log_level != 'DEBUG':
                    raise Exception(f"Invalid request to Bedrock API")
                else:
                    raise Exception(f"Bedrock validation error: {error_message}")
            
            elif 'timeout' in error_message.lower() or 'timed out' in error_message.lower():
                # Timeout errors
                logger.error(f"Bedrock request timeout: {error_message}")
                raise Exception(f"Bedrock request timed out. The model may be overloaded.")
            
            else:
                # Generic error
                logger.error(f"Bedrock ClientError [{error_code}]: {error_message}")
                # Don't expose sensitive details in production
                if settings.log_level != 'DEBUG':
                    raise Exception(f"Bedrock API error: {error_code}")
                else:
                    raise Exception(f"Bedrock API error: {error_code} - {error_message}")
        
        except BotoCoreError as e:
            logger.error(f"Bedrock BotoCoreError: {e}")
            raise Exception(f"AWS SDK error: {str(e)}")
        
        except Exception as e:
            # Catch-all for unexpected errors
            error_str = str(e)
            logger.error(f"Unexpected error invoking Bedrock: {error_str}")
            
            # Don't log sensitive content in production
            if settings.log_level != 'DEBUG' and len(error_str) > 100:
                raise Exception(f"Unexpected error during Bedrock invocation")
            else:
                raise
    
    def _parse_llm_response(self, response_text: str) -> Tuple[Optional[Dict], Optional[str]]:
        """
        Parse LLM response and extract JSON.
        
        Args:
            response_text: Raw LLM response
            
        Returns:
            Tuple of (parsed_json, error_message)
        """
        if not response_text or not response_text.strip():
            return None, "Empty response from LLM"
        
        # Try direct JSON parsing first
        try:
            data = json.loads(response_text)
            return data, None
        except json.JSONDecodeError:
            pass
        
        # Try to extract JSON from markdown code blocks
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(1))
                return data, None
            except json.JSONDecodeError:
                pass
        
        # Try to find JSON object in text
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(0))
                return data, None
            except json.JSONDecodeError:
                pass
        
        return None, f"Could not parse JSON from response: {response_text[:200]}"
    
    def _build_fix_prompt(self, previous_response: str, error: str, content: str, metadata: Dict[str, Any]) -> str:
        """
        Build a fix prompt for JSON parsing errors.
        
        Args:
            previous_response: The previous LLM response that failed
            error: The parsing error message
            content: Original content
            metadata: Original metadata
            
        Returns:
            Fix prompt string
        """
        return f"""CRITICAL: Your previous response had a JSON parsing error: {error}

You MUST output ONLY the JSON object itself. Do NOT include:
- Any explanatory text before or after the JSON
- Phrases like "Here is the extracted data"
- Markdown code blocks (no ``` markers)
- Comments or notes

Start your response with {{ and end with }}. Nothing else.

Previous response that failed:
{previous_response[:500]}

Output the corrected JSON now:
"""
    
    def _build_validation_fix_prompt(self, previous_data: Dict, errors: List[str], content: str, metadata: Dict[str, Any]) -> str:
        """
        Build a fix prompt for schema validation errors.
        
        Args:
            previous_data: The previous extracted data that failed validation
            errors: List of validation error messages
            content: Original content
            metadata: Original metadata
            
        Returns:
            Fix prompt string
        """
        errors_text = "\n".join(f"- {error}" for error in errors)
        
        return f"""Your previous response had schema validation errors:

{errors_text}

Please provide the extracted data again, fixing these specific issues:

Previous data that failed validation:
{json.dumps(previous_data, indent=2)[:1000]}

Requirements:
1. Fix all validation errors listed above
2. Ensure all required fields are present
3. Use correct data types (strings, arrays, objects)
4. Dates must be in ISO 8601 format (YYYY-MM-DD)
5. Confidence values must be: high, medium, or low
6. Output ONLY valid JSON

Original content to extract from:
{content[:5000]}
"""


# Global extractor instance
_extractor_instance = None


def get_extractor() -> BedrockExtractor:
    """
    Get global BedrockExtractor instance (singleton pattern).
    
    Returns:
        BedrockExtractor instance
    """
    global _extractor_instance
    if _extractor_instance is None:
        _extractor_instance = BedrockExtractor()
    return _extractor_instance


def get_bedrock_extractor() -> BedrockExtractor:
    """
    Alias for get_extractor() for clarity.
    
    Returns:
        BedrockExtractor instance
    """
    return get_extractor()


async def extract_with_bedrock(
    content: str,
    metadata: Dict[str, Any]
) -> Tuple[Optional[Dict], Optional[str]]:
    """
    Convenience function to extract data using Bedrock.
    
    Args:
        content: Text content to extract from
        metadata: Metadata dict with url, content_type, etc.
        
    Returns:
        Tuple of (extracted_data, error_message)
    """
    extractor = get_extractor()
    return await extractor.extract_structured_data(content, metadata)



def validate_extraction_schema(data: dict) -> Tuple[bool, List[str]]:
    """
    Validate extracted data against the expected schema.
    
    Args:
        data: Extracted data dictionary from LLM
        
    Returns:
        Tuple of (is_valid, error_messages)
    """
    errors = []
    
    if not isinstance(data, dict):
        errors.append("Data must be a dictionary")
        return False, errors
    
    # Check required top-level fields
    required_fields = ['page_info', 'extracted_fields', 'dates', 'metadata']
    for field in required_fields:
        if field not in data:
            errors.append(f"Missing required field: {field}")
    
    # Validate page_info
    if 'page_info' in data:
        page_info = data['page_info']
        if not isinstance(page_info, dict):
            errors.append("page_info must be a dictionary")
        else:
            required_page_fields = ['title', 'url', 'summary']
            for field in required_page_fields:
                if field not in page_info:
                    errors.append(f"page_info missing required field: {field}")
                elif not isinstance(page_info[field], str):
                    errors.append(f"page_info.{field} must be a string")
    
    # Validate extracted_fields array
    if 'extracted_fields' in data:
        if not isinstance(data['extracted_fields'], list):
            errors.append("extracted_fields must be an array")
        else:
            for i, field in enumerate(data['extracted_fields']):
                if not isinstance(field, dict):
                    errors.append(f"extracted_fields[{i}] must be an object")
                    continue
                # Only key, value, and confidence are required; context is optional
                required = ['key', 'value', 'confidence']
                for req in required:
                    if req not in field:
                        errors.append(f"extracted_fields[{i}] missing field: {req}")
                
                # Validate confidence values
                if 'confidence' in field:
                    valid_confidence = ['high', 'medium', 'low']
                    if field['confidence'] not in valid_confidence:
                        errors.append(f"extracted_fields[{i}].confidence must be one of: {valid_confidence}")
    
    # Validate dates array
    if 'dates' in data:
        if not isinstance(data['dates'], list):
            errors.append("dates must be an array")
        else:
            for i, date in enumerate(data['dates']):
                if not isinstance(date, dict):
                    errors.append(f"dates[{i}] must be an object")
                    continue
                
                # Only 'value' is required, 'label' and 'context' are optional
                if 'value' not in date:
                    errors.append(f"dates[{i}] missing required field: value")
                
                # Validate ISO 8601 date format (YYYY-MM-DD)
                if 'value' in date:
                    if not re.match(r'^\d{4}-\d{2}-\d{2}$', str(date['value'])):
                        errors.append(f"dates[{i}].value must be in ISO 8601 format (YYYY-MM-DD)")
    
    # Validate metadata (all fields optional)
    if 'metadata' in data:
        if not isinstance(data['metadata'], dict):
            errors.append("metadata must be a dictionary")
        # No required fields - all metadata fields are optional
    
    return len(errors) == 0, errors

    
    def _build_fix_prompt(self, previous_response: str, error: str, content: str, metadata: Dict[str, Any]) -> str:
        """
        Build a fix prompt for JSON parsing errors.
        
        Args:
            previous_response: The previous LLM response that failed
            error: The parsing error message
            content: Original content
            metadata: Original metadata
            
        Returns:
            Fix prompt string
        """
        return f"""Your previous response had a JSON parsing error: {error}

Please provide the extracted data again, ensuring it is ONLY valid JSON with no additional text, comments, or markdown formatting.

Previous response that failed:
{previous_response[:500]}

Remember:
1. Output ONLY valid JSON
2. No markdown code blocks
3. No explanations or comments
4. Follow the exact schema provided earlier

Original content to extract from:
{content[:5000]}
"""
    
    def _build_validation_fix_prompt(self, previous_data: Dict, errors: List[str], content: str, metadata: Dict[str, Any]) -> str:
        """
        Build a fix prompt for schema validation errors.
        
        Args:
            previous_data: The previous extracted data that failed validation
            errors: List of validation error messages
            content: Original content
            metadata: Original metadata
            
        Returns:
            Fix prompt string
        """
        errors_text = "\n".join(f"- {error}" for error in errors)
        
        return f"""Your previous response had schema validation errors:

{errors_text}

Please provide the extracted data again, fixing these specific issues:

Previous data that failed validation:
{json.dumps(previous_data, indent=2)[:1000]}

Requirements:
1. Fix all validation errors listed above
2. Ensure all required fields are present
3. Use correct data types (strings, arrays, objects)
4. Dates must be in ISO 8601 format (YYYY-MM-DD)
5. Confidence values must be: high, medium, or low
6. Output ONLY valid JSON

Original content to extract from:
{content[:5000]}
"""


def normalize_extracted_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize extracted data by cleaning and standardizing values.
    
    Normalization steps:
    1. Trim whitespace from all string fields (recursive)
    2. Remove HTML tags from text fields
    3. Normalize dates to ISO 8601 format
    4. Convert numeric strings to appropriate numeric types
    5. Set default values for missing optional fields
    
    Args:
        data: Extracted data dictionary from LLM
        
    Returns:
        Normalized data dictionary
    """
    if not isinstance(data, dict):
        return data
    
    # Create a copy to avoid modifying original
    normalized = {}
    
    for key, value in data.items():
        if key == 'page_info':
            normalized[key] = _normalize_page_info(value)
        elif key == 'extracted_fields':
            normalized[key] = _normalize_extracted_fields(value)
        elif key == 'dates':
            normalized[key] = _normalize_dates(value)
        elif key == 'metadata':
            normalized[key] = _normalize_metadata(value)
        else:
            # Recursively normalize other fields
            normalized[key] = _normalize_value(value)
    
    # Set default values for missing optional fields
    if 'extracted_fields' not in normalized:
        normalized['extracted_fields'] = []
    if 'dates' not in normalized:
        normalized['dates'] = []
    
    return normalized


def _normalize_page_info(page_info: Any) -> Dict[str, Any]:
    """Normalize page_info section."""
    if not isinstance(page_info, dict):
        return page_info
    
    normalized = {}
    for key, value in page_info.items():
        if isinstance(value, str):
            # Trim whitespace and remove HTML tags
            value = value.strip()
            value = remove_html_tags(value)
        normalized[key] = value
    
    return normalized


def _normalize_extracted_fields(fields: Any) -> List[Dict[str, Any]]:
    """Normalize extracted_fields array."""
    if not isinstance(fields, list):
        return []
    
    normalized = []
    for field in fields:
        if not isinstance(field, dict):
            continue
        
        normalized_field = {}
        for key, value in field.items():
            if isinstance(value, str):
                # Trim whitespace and remove HTML tags
                value = value.strip()
                if key in ['value', 'context']:
                    value = remove_html_tags(value)
                
                # Try to convert numeric strings in 'value' field
                if key == 'value':
                    converted = convert_numeric_string(value)
                    # Keep as string if it's still a string after conversion
                    if isinstance(converted, str):
                        normalized_field[key] = converted
                    else:
                        # Store numeric value but keep original string representation
                        normalized_field[key] = value
                        normalized_field['numeric_value'] = converted
                else:
                    normalized_field[key] = value
            else:
                normalized_field[key] = value
        
        normalized.append(normalized_field)
    
    return normalized


def _normalize_dates(dates: Any) -> List[Dict[str, Any]]:
    """Normalize dates array."""
    if not isinstance(dates, list):
        return []
    
    normalized = []
    for date_obj in dates:
        if not isinstance(date_obj, dict):
            continue
        
        normalized_date = {}
        for key, value in date_obj.items():
            if isinstance(value, str):
                value = value.strip()
                
                # Normalize date value to ISO 8601
                if key == 'value':
                    value = normalize_date(value)
                elif key in ['label', 'context']:
                    value = remove_html_tags(value)
                
                normalized_date[key] = value
            else:
                normalized_date[key] = value
        
        normalized.append(normalized_date)
    
    return normalized


def _normalize_metadata(metadata: Any) -> Dict[str, Any]:
    """Normalize metadata section."""
    if not isinstance(metadata, dict):
        return metadata
    
    normalized = {}
    for key, value in metadata.items():
        if isinstance(value, str):
            value = value.strip()
        normalized[key] = value
    
    return normalized


def _normalize_value(value: Any) -> Any:
    """
    Recursively normalize any value.
    
    Args:
        value: Value to normalize
        
    Returns:
        Normalized value
    """
    if isinstance(value, str):
        # Trim whitespace
        value = value.strip()
        # Remove HTML tags
        value = remove_html_tags(value)
        return value
    elif isinstance(value, dict):
        return {k: _normalize_value(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [_normalize_value(item) for item in value]
    else:
        return value


def remove_html_tags(text: str) -> str:
    """
    Remove HTML tags from text.
    
    Args:
        text: Text potentially containing HTML tags
        
    Returns:
        Text with HTML tags removed
    """
    if not isinstance(text, str):
        return text
    
    # Remove HTML tags using regex
    clean_text = re.sub(r'<[^>]+>', '', text)
    
    # Remove extra whitespace that may result from tag removal
    clean_text = re.sub(r'\s+', ' ', clean_text).strip()
    
    return clean_text


def normalize_date(date_str: str) -> str:
    """
    Convert various date formats to ISO 8601 format (YYYY-MM-DD).
    
    Args:
        date_str: Date string in various formats
        
    Returns:
        Date string in ISO 8601 format, or original string if parsing fails
    """
    if not isinstance(date_str, str):
        return date_str
    
    date_str = date_str.strip()
    
    # If already in ISO 8601 format, return as-is
    if re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
        return date_str
    
    # Try common date formats
    formats = [
        '%Y-%m-%d',           # 2024-01-15
        '%d/%m/%Y',           # 15/01/2024
        '%m/%d/%Y',           # 01/15/2024
        '%d-%m-%Y',           # 15-01-2024
        '%Y/%m/%d',           # 2024/01/15
        '%B %d, %Y',          # January 15, 2024
        '%b %d, %Y',          # Jan 15, 2024
        '%d %B %Y',           # 15 January 2024
        '%d %b %Y',           # 15 Jan 2024
        '%Y-%m-%dT%H:%M:%S',  # ISO 8601 with time
        '%Y-%m-%dT%H:%M:%SZ', # ISO 8601 with time and Z
    ]
    
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime('%Y-%m-%d')
        except ValueError:
            continue
    
    # If no format matches, return original string
    logger.warning(f"Could not parse date: {date_str}")
    return date_str


def convert_numeric_string(value: str) -> Union[int, float, str]:
    """
    Convert numeric strings to appropriate numeric types.
    
    Args:
        value: String value that might be numeric
        
    Returns:
        int, float, or original string
    """
    if not isinstance(value, str):
        return value
    
    # Remove whitespace and common formatting
    value = value.strip()
    
    # Remove common currency symbols and commas
    cleaned = value.replace(',', '').replace('$', '').replace('€', '').replace('£', '')
    
    # Try to convert to number
    try:
        # Check if it contains a decimal point
        if '.' in cleaned:
            return float(cleaned)
        else:
            return int(cleaned)
    except ValueError:
        # Not a number, return original string
        return value
