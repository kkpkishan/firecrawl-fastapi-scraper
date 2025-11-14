"""
FastAPI Web Scraping Backend - Main Application
"""
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import os

# Initialize FastAPI app
app = FastAPI(
    title="Web Scraping Backend API",
    description="A scalable web scraping service using FastAPI and Firecrawl",
    version="1.0.0"
)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Web Scraping Backend API",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint for Docker healthcheck"""
    return {
        "status": "healthy",
        "service": "fastapi-app"
    }


@app.get("/readiness")
async def readiness_check():
    """Readiness check - verifies all dependencies are available"""
    # TODO: Add database connectivity check
    return {
        "status": "ready",
        "database": "not_implemented",
        "firecrawl": "not_implemented"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
