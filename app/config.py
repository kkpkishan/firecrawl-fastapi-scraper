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
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Create global settings instance
settings = Settings()


def get_settings() -> Settings:
    """
    Get application settings.
    
    Returns:
        Settings instance
    """
    return settings
