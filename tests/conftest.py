"""Pytest configuration and shared fixtures"""

import pytest
import os
from typing import Generator


@pytest.fixture(autouse=True)
def reset_env_vars() -> Generator[None, None, None]:
    """Reset environment variables before each test"""
    # Store original env vars
    original_env = os.environ.copy()
    
    # Clear Pentaract-related env vars
    pentaract_vars = [
        "PENTARACT_ENABLED",
        "PENTARACT_API_URL",
        "PENTARACT_EMAIL",
        "PENTARACT_PASSWORD",
        "PENTARACT_UPLOAD_THRESHOLD",
        "PENTARACT_AUTO_CLEANUP",
        "PENTARACT_CLEANUP_INTERVAL",
        "PENTARACT_MAX_CONCURRENT_UPLOADS",
        "PENTARACT_TIMEOUT",
        "PENTARACT_RETRY_ATTEMPTS",
    ]
    
    for var in pentaract_vars:
        os.environ.pop(var, None)
    
    yield
    
    # Restore original env vars
    os.environ.clear()
    os.environ.update(original_env)
