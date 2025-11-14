"""
Authentication and Authorization

Handles API key validation for securing endpoints.
"""
from fastapi import Header, HTTPException, status
from typing import Optional
import logging

from config import settings

logger = logging.getLogger(__name__)


async def verify_api_key(x_api_key: Optional[str] = Header(None, alias="X-API-Key")) -> str:
    """
    Verify API key from request header.
    
    This dependency function validates the X-API-Key header against
    the configured APP_API_KEY environment variable.
    
    Args:
        x_api_key: API key from X-API-Key header
        
    Returns:
        The validated API key
        
    Raises:
        HTTPException: 401 if API key is missing or invalid
        
    Example:
        @app.get("/protected")
        async def protected_route(api_key: str = Depends(verify_api_key)):
            return {"message": "Access granted"}
    """
    # Check if API key is provided
    if not x_api_key:
        logger.warning("API request without API key")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Please provide X-API-Key header.",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    
    # Validate API key
    if x_api_key != settings.app_api_key:
        logger.warning(f"Invalid API key attempt: {x_api_key[:8]}...")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    
    logger.debug("API key validated successfully")
    return x_api_key


def get_api_key_header() -> dict:
    """
    Get API key header for documentation.
    
    Returns:
        Dictionary with API key header configuration for OpenAPI docs
    """
    return {
        "name": "X-API-Key",
        "in": "header",
        "required": True,
        "schema": {
            "type": "string"
        },
        "description": "API key for authentication"
    }
