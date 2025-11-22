"""
Application Configuration

Manages environment variables and application settings.
"""
from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    """
    # Application
    app_name: str = "Web Scraping Backend API"
    app_version: str = "1.0.0"
    log_level: str = "INFO"
    
    # API Security
    app_api_key: str = os.getenv("APP_API_KEY", "")
    
    # Database
    db_url: str = os.getenv(
        "DB_URL",
        "postgresql+asyncpg://postgres:postgres@nuq-postgres:5432/postgres"
    )
    
    # Firecrawl
    firecrawl_api_url: str = os.getenv(
        "FIRECRAWL_API_URL",
        "http://firecrawl-api:3002"
    )
    
    # CORS
    cors_origins: list = ["*"]  # In production, specify allowed origins
    cors_allow_credentials: bool = True
    cors_allow_methods: list = ["*"]
    cors_allow_headers: list = ["*"]
    
    # Job Processing
    crawl_timeout_seconds: int = 300  # 5 minutes
    polling_interval_seconds: int = 5
    
    # Regex Extraction Configuration
    enable_regex_extraction: bool = os.getenv("ENABLE_REGEX_EXTRACTION", "true").lower() == "true"
    regex_context_chars: int = int(os.getenv("REGEX_CONTEXT_CHARS", "200"))
    
    # AWS Bedrock Configuration
    aws_region: str = os.getenv("AWS_REGION", "us-east-1")
    bedrock_model_id: str = os.getenv("BEDROCK_MODEL_ID", "amazon.titan-text-express-v1")
    bedrock_temperature: float = float(os.getenv("BEDROCK_TEMPERATURE", "0.0"))
    bedrock_max_tokens: int = int(os.getenv("BEDROCK_MAX_TOKENS", "4096"))
    enable_bedrock_extraction: bool = os.getenv("ENABLE_BEDROCK_EXTRACTION", "false").lower() == "true"
    
    # Bedrock retry configuration
    bedrock_max_retries: int = 2
    bedrock_retry_delay: float = 1.0
    
    def validate_bedrock_config(self) -> tuple[bool, list[str]]:
        """
        Validate AWS Bedrock configuration.
        
        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []
        
        if self.enable_bedrock_extraction:
            if not self.aws_region:
                errors.append("AWS_REGION environment variable is required when Bedrock extraction is enabled")
            
            if not self.bedrock_model_id:
                errors.append("BEDROCK_MODEL_ID environment variable is required when Bedrock extraction is enabled")
            
            if self.bedrock_temperature < 0.0 or self.bedrock_temperature > 1.0:
                errors.append("BEDROCK_TEMPERATURE must be between 0.0 and 1.0")
            
            if self.bedrock_max_tokens < 1 or self.bedrock_max_tokens > 100000:
                errors.append("BEDROCK_MAX_TOKENS must be between 1 and 100000")
        
        return len(errors) == 0, errors
    
    def get_all_regex_patterns(self) -> dict:
        """
        Dynamically get all regex patterns from environment variables.
        
        Automatically detects any environment variable starting with 'REGEX_PATTERN_'
        and loads it as a pattern. This allows developers to add new patterns
        without modifying code - just add to .env and restart!
        
        Pattern naming convention:
        - REGEX_PATTERN_<NAME> in .env becomes pattern name '<name>' (lowercase)
        - Example: REGEX_PATTERN_SALARY becomes 'salary'
        - Example: REGEX_PATTERN_PHONE_NUMBER becomes 'phone_number'
        
        Returns:
            Dictionary with pattern_name: regex_pattern
        """
        import logging
        logger = logging.getLogger(__name__)
        
        patterns = {}
        
        # Automatically detect all REGEX_PATTERN_* environment variables
        for env_key, env_value in os.environ.items():
            if env_key.startswith("REGEX_PATTERN_") and env_value:
                # Extract pattern name from environment variable
                # REGEX_PATTERN_DATE -> date
                # REGEX_PATTERN_EXAM_CODE -> exam_code
                pattern_name = env_key.replace("REGEX_PATTERN_", "").lower()
                patterns[pattern_name] = env_value
                logger.debug(f"Loaded regex pattern '{pattern_name}' from {env_key}")
        
        logger.info(f"Loaded {len(patterns)} regex patterns from environment")
        
        return patterns
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields from .env


# Create global settings instance
settings = Settings()


def get_settings() -> Settings:
    """
    Get application settings.
    
    Returns:
        Settings instance
    """
    return settings
