"""Main entry point for the application"""

import asyncio
import logging
import uvicorn
from app.main import app
from app.config import settings

if __name__ == "__main__":
    # Configure uvicorn access logger based on environment and log level
    log_level_value = getattr(logging, settings.log_level.upper(), logging.INFO)
    
    # In production with INFO or higher, suppress uvicorn access logs
    if settings.environment == "production" and log_level_value >= logging.INFO:
        uvicorn_access_logger = logging.getLogger("uvicorn.access")
        uvicorn_access_logger.setLevel(logging.WARNING)
        uvicorn_access_logger.disabled = True
    
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
        reload=settings.environment == "development",
        access_log=settings.environment != "production" or log_level_value < logging.INFO,
    )

