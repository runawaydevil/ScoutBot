"""Unit tests for Pentaract secure logging"""

import pytest
import os
from unittest.mock import Mock, call
from app.utils.logger import log_pentaract_config


def test_log_pentaract_config_disabled():
    """Test logging when Pentaract is disabled"""
    os.environ["BOT_TOKEN"] = "test_token"
    
    from app.config import Settings
    settings = Settings()
    
    mock_logger = Mock()
    log_pentaract_config(mock_logger, settings)
    
    # Should log that it's disabled
    mock_logger.info.assert_called_once_with("pentaract_config_loaded", enabled=False)


def test_log_pentaract_config_enabled_redacts_password():
    """Test that password is redacted in logs"""
    os.environ["BOT_TOKEN"] = "test_token"
    os.environ["PENTARACT_ENABLED"] = "true"
    os.environ["PENTARACT_API_URL"] = "http://pentaract.example.com/api"
    os.environ["PENTARACT_EMAIL"] = "test@example.com"
    os.environ["PENTARACT_PASSWORD"] = "super_secret_password"
    
    from app.config import Settings
    settings = Settings()
    
    mock_logger = Mock()
    log_pentaract_config(mock_logger, settings)
    
    # Check that info was called
    assert mock_logger.info.called
    
    # Get the call arguments
    call_args = mock_logger.info.call_args
    
    # Verify password is redacted
    assert call_args[1]["password"] == "[REDACTED]"
    
    # Verify email is not redacted
    assert call_args[1]["email"] == "test@example.com"
    
    # Verify other fields are present
    assert call_args[1]["enabled"] is True
    assert call_args[1]["api_url"] == "http://pentaract.example.com/api"
    assert call_args[1]["upload_threshold_mb"] == 50


def test_log_pentaract_config_shows_not_set_for_missing_credentials():
    """Test that missing credentials show [NOT_SET] instead of None"""
    os.environ["BOT_TOKEN"] = "test_token"
    os.environ["PENTARACT_ENABLED"] = "false"
    
    from app.config import Settings
    settings = Settings()
    
    # Manually enable to test logging with missing credentials
    settings.pentaract_enabled = True
    
    mock_logger = Mock()
    
    # This should not raise an error even though credentials are missing
    # (validation only happens during Settings initialization)
    log_pentaract_config(mock_logger, settings)
    
    call_args = mock_logger.info.call_args
    
    # Verify missing fields show [NOT_SET]
    assert call_args[1]["email"] == "[NOT_SET]"
    assert call_args[1]["password"] == "[NOT_SET]"


def test_log_pentaract_config_logs_all_configuration_fields():
    """Test that all configuration fields are logged"""
    os.environ["BOT_TOKEN"] = "test_token"
    os.environ["PENTARACT_ENABLED"] = "true"
    os.environ["PENTARACT_API_URL"] = "http://pentaract.example.com/api"
    os.environ["PENTARACT_EMAIL"] = "test@example.com"
    os.environ["PENTARACT_PASSWORD"] = "test_password"
    os.environ["PENTARACT_UPLOAD_THRESHOLD"] = "100"
    os.environ["PENTARACT_AUTO_CLEANUP"] = "false"
    os.environ["PENTARACT_CLEANUP_INTERVAL"] = "60"
    os.environ["PENTARACT_MAX_CONCURRENT_UPLOADS"] = "5"
    os.environ["PENTARACT_TIMEOUT"] = "45"
    os.environ["PENTARACT_RETRY_ATTEMPTS"] = "5"
    
    from app.config import Settings
    settings = Settings()
    
    mock_logger = Mock()
    log_pentaract_config(mock_logger, settings)
    
    call_args = mock_logger.info.call_args
    
    # Verify all fields are present
    assert call_args[1]["enabled"] is True
    assert call_args[1]["api_url"] == "http://pentaract.example.com/api"
    assert call_args[1]["email"] == "test@example.com"
    assert call_args[1]["password"] == "[REDACTED]"
    assert call_args[1]["upload_threshold_mb"] == 100
    assert call_args[1]["auto_cleanup"] is False
    assert call_args[1]["cleanup_interval_minutes"] == 60
    assert call_args[1]["max_concurrent_uploads"] == 5
    assert call_args[1]["timeout_seconds"] == 45
    assert call_args[1]["retry_attempts"] == 5


def test_log_pentaract_config_never_logs_actual_password():
    """Test that the actual password never appears in logs"""
    os.environ["BOT_TOKEN"] = "test_token"
    os.environ["PENTARACT_ENABLED"] = "true"
    os.environ["PENTARACT_API_URL"] = "http://pentaract.example.com/api"
    os.environ["PENTARACT_EMAIL"] = "test@example.com"
    os.environ["PENTARACT_PASSWORD"] = "my_super_secret_password_12345"
    
    from app.config import Settings
    settings = Settings()
    
    mock_logger = Mock()
    log_pentaract_config(mock_logger, settings)
    
    # Convert all call arguments to string and verify password is not present
    all_calls_str = str(mock_logger.info.call_args_list)
    
    assert "my_super_secret_password_12345" not in all_calls_str
    assert "[REDACTED]" in all_calls_str
