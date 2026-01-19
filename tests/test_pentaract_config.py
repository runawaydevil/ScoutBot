"""Unit tests for Pentaract configuration"""

import pytest
import os
from pydantic import ValidationError


def test_pentaract_disabled_by_default():
    """Test that Pentaract is disabled by default"""
    # Set required bot_token
    os.environ["BOT_TOKEN"] = "test_token"
    
    from app.config import Settings
    settings = Settings()
    
    assert settings.pentaract_enabled is False
    assert settings.pentaract_api_url == "http://localhost:8000/api"
    assert settings.pentaract_email is None
    assert settings.pentaract_password is None
    assert settings.pentaract_upload_threshold == 50
    assert settings.pentaract_auto_cleanup is True
    assert settings.pentaract_cleanup_interval == 30
    assert settings.pentaract_max_concurrent_uploads == 3
    assert settings.pentaract_timeout == 30
    assert settings.pentaract_retry_attempts == 3


def test_pentaract_enabled_with_all_required_fields():
    """Test that Pentaract can be enabled with all required fields"""
    os.environ["BOT_TOKEN"] = "test_token"
    os.environ["PENTARACT_ENABLED"] = "true"
    os.environ["PENTARACT_API_URL"] = "http://pentaract.example.com/api"
    os.environ["PENTARACT_EMAIL"] = "test@example.com"
    os.environ["PENTARACT_PASSWORD"] = "test_password"
    
    from app.config import Settings
    settings = Settings()
    
    assert settings.pentaract_enabled is True
    assert settings.pentaract_api_url == "http://pentaract.example.com/api"
    assert settings.pentaract_email == "test@example.com"
    assert settings.pentaract_password == "test_password"


def test_pentaract_enabled_missing_api_url():
    """Test that validation fails when Pentaract is enabled but API URL is missing"""
    os.environ["BOT_TOKEN"] = "test_token"
    os.environ["PENTARACT_ENABLED"] = "true"
    os.environ["PENTARACT_EMAIL"] = "test@example.com"
    os.environ["PENTARACT_PASSWORD"] = "test_password"
    os.environ["PENTARACT_API_URL"] = ""  # Empty string
    
    from app.config import Settings
    
    with pytest.raises(ValueError) as exc_info:
        Settings()
    
    assert "pentaract_api_url" in str(exc_info.value)


def test_pentaract_enabled_missing_email():
    """Test that validation fails when Pentaract is enabled but email is missing"""
    os.environ["BOT_TOKEN"] = "test_token"
    os.environ["PENTARACT_ENABLED"] = "true"
    os.environ["PENTARACT_API_URL"] = "http://pentaract.example.com/api"
    os.environ["PENTARACT_PASSWORD"] = "test_password"
    
    from app.config import Settings
    
    with pytest.raises(ValueError) as exc_info:
        Settings()
    
    assert "pentaract_email" in str(exc_info.value)


def test_pentaract_enabled_missing_password():
    """Test that validation fails when Pentaract is enabled but password is missing"""
    os.environ["BOT_TOKEN"] = "test_token"
    os.environ["PENTARACT_ENABLED"] = "true"
    os.environ["PENTARACT_API_URL"] = "http://pentaract.example.com/api"
    os.environ["PENTARACT_EMAIL"] = "test@example.com"
    
    from app.config import Settings
    
    with pytest.raises(ValueError) as exc_info:
        Settings()
    
    assert "pentaract_password" in str(exc_info.value)


def test_pentaract_enabled_missing_multiple_fields():
    """Test that validation fails with all missing fields listed"""
    os.environ["BOT_TOKEN"] = "test_token"
    os.environ["PENTARACT_ENABLED"] = "true"
    
    from app.config import Settings
    
    with pytest.raises(ValueError) as exc_info:
        Settings()
    
    error_msg = str(exc_info.value)
    # API URL has a default, so only email and password should be missing
    assert "pentaract_email" in error_msg
    assert "pentaract_password" in error_msg


def test_pentaract_custom_threshold():
    """Test that custom upload threshold is applied"""
    os.environ["BOT_TOKEN"] = "test_token"
    os.environ["PENTARACT_UPLOAD_THRESHOLD"] = "100"
    
    from app.config import Settings
    settings = Settings()
    
    assert settings.pentaract_upload_threshold == 100


def test_pentaract_custom_timeout():
    """Test that custom timeout is applied"""
    os.environ["BOT_TOKEN"] = "test_token"
    os.environ["PENTARACT_TIMEOUT"] = "60"
    
    from app.config import Settings
    settings = Settings()
    
    assert settings.pentaract_timeout == 60


def test_pentaract_custom_retry_attempts():
    """Test that custom retry attempts is applied"""
    os.environ["BOT_TOKEN"] = "test_token"
    os.environ["PENTARACT_RETRY_ATTEMPTS"] = "5"
    
    from app.config import Settings
    settings = Settings()
    
    assert settings.pentaract_retry_attempts == 5


def test_pentaract_custom_max_concurrent_uploads():
    """Test that custom max concurrent uploads is applied"""
    os.environ["BOT_TOKEN"] = "test_token"
    os.environ["PENTARACT_MAX_CONCURRENT_UPLOADS"] = "5"
    
    from app.config import Settings
    settings = Settings()
    
    assert settings.pentaract_max_concurrent_uploads == 5


def test_pentaract_auto_cleanup_disabled():
    """Test that auto cleanup can be disabled"""
    os.environ["BOT_TOKEN"] = "test_token"
    os.environ["PENTARACT_AUTO_CLEANUP"] = "false"
    
    from app.config import Settings
    settings = Settings()
    
    assert settings.pentaract_auto_cleanup is False


def test_pentaract_custom_cleanup_interval():
    """Test that custom cleanup interval is applied"""
    os.environ["BOT_TOKEN"] = "test_token"
    os.environ["PENTARACT_CLEANUP_INTERVAL"] = "60"
    
    from app.config import Settings
    settings = Settings()
    
    assert settings.pentaract_cleanup_interval == 60
