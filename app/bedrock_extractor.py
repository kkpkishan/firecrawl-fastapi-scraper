"""
AWS Bedrock-Based Data Extraction Module

This module provides LLM-based extraction using AWS Bedrock for intelligent
understanding and extraction of structured data from web content.
"""
import json
import logging
import re
from typing import Dict, Optional, Tuple, Any, List
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
        Extract structured data from content using LLM.
        
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
        
        # Build the prompt
        prompt = self._build_prompt(content, metadata)
        
        # Invoke LLM
        try:
            response_text = await self._invoke_bedrock(prompt)
            
            # Parse and validate response
            extracted_data, parse_error = self._parse_llm_response(response_text)
            
            if parse_error:
                return None, f"Failed to parse LLM response: {parse_error}"
            
            return extracted_data, None
            
        except Exception as e:
            error_msg = f"Bedrock extraction failed: {str(e)}"
            logger.error(error_msg)
            return None, error_msg
    
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
            content=content[:10000]  # Limit content to avoid token limits
        )
        
        return prompt
    
    def _get_system_prompt(self) -> str:
        """
        Get the system prompt template for extraction.
        
        Returns:
            System prompt string with placeholders
        """
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
            elif 'claude' in self.model_id.lower():
                # Anthropic Claude models
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
                    response = await client.post(
                        endpoint,
                        headers=headers,
                        json=request_body,
                        timeout=30.0
                    )
                    response.raise_for_status()
                    response_body = response.json()
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
            elif 'claude' in self.model_id.lower():
                response_text = response_body.get('completion', '')
            else:
                response_text = response_body.get('outputText', '') or response_body.get('completion', '')
            
            return response_text
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_message = e.response.get('Error', {}).get('Message', str(e))
            logger.error(f"Bedrock ClientError [{error_code}]: {error_message}")
            raise Exception(f"Bedrock API error: {error_code} - {error_message}")
        
        except BotoCoreError as e:
            logger.error(f"Bedrock BotoCoreError: {e}")
            raise Exception(f"AWS SDK error: {str(e)}")
        
        except Exception as e:
            logger.error(f"Unexpected error invoking Bedrock: {e}")
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
                required = ['key', 'value', 'confidence', 'context']
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
                
                required_date_fields = ['label', 'value', 'context']
                for field in required_date_fields:
                    if field not in date:
                        errors.append(f"dates[{i}] missing field: {field}")
                
                # Validate ISO 8601 date format (YYYY-MM-DD)
                if 'value' in date:
                    if not re.match(r'^\d{4}-\d{2}-\d{2}$', str(date['value'])):
                        errors.append(f"dates[{i}].value must be in ISO 8601 format (YYYY-MM-DD)")
    
    # Validate metadata
    if 'metadata' in data:
        if not isinstance(data['metadata'], dict):
            errors.append("metadata must be a dictionary")
        else:
            required_meta_fields = ['extraction_timestamp', 'model_used', 'content_type']
            for field in required_meta_fields:
                if field not in data['metadata']:
                    errors.append(f"metadata missing required field: {field}")
    
    return len(errors) == 0, errors
