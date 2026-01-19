"""Unit tests for User Settings Service"""

import pytest
from uuid import uuid4
from unittest.mock import patch, MagicMock
from sqlmodel import SQLModel, create_engine, Session

from app.services.user_settings_service import (
    UserSettingsService,
    VALID_STORAGE_PREFERENCES,
)
from app.models.user_settings import UserSettings


# Create a test database engine
test_engine = create_engine("sqlite:///:memory:")
SQLModel.metadata.create_all(test_engine)


@pytest.fixture(autouse=True)
def mock_database():
    """Mock the database to use in-memory SQLite for all tests"""
    with patch("app.services.user_settings_service.database") as mock_db:
        mock_db.get_session = lambda: Session(test_engine)
        yield mock_db


@pytest.fixture
def user_settings_service():
    """Create a UserSettingsService instance"""
    return UserSettingsService()


@pytest.fixture
def test_user_id():
    """Generate a unique test user ID"""
    return str(uuid4())


class TestStoragePreferences:
    """Test storage preference functionality"""

    @pytest.mark.asyncio
    async def test_get_storage_preference_default(
        self, user_settings_service, test_user_id
    ):
        """Test that new users get 'auto' as default storage preference"""
        # Get settings for new user (will create default)
        preference = await user_settings_service.get_storage_preference(test_user_id)
        
        assert preference == "auto", "Default storage preference should be 'auto'"

    @pytest.mark.asyncio
    async def test_set_storage_preference_auto(
        self, user_settings_service, test_user_id
    ):
        """Test setting storage preference to 'auto'"""
        await user_settings_service.set_storage_preference(test_user_id, "auto")
        
        preference = await user_settings_service.get_storage_preference(test_user_id)
        assert preference == "auto"

    @pytest.mark.asyncio
    async def test_set_storage_preference_pentaract(
        self, user_settings_service, test_user_id
    ):
        """Test setting storage preference to 'pentaract'"""
        await user_settings_service.set_storage_preference(test_user_id, "pentaract")
        
        preference = await user_settings_service.get_storage_preference(test_user_id)
        assert preference == "pentaract"

    @pytest.mark.asyncio
    async def test_set_storage_preference_local(
        self, user_settings_service, test_user_id
    ):
        """Test setting storage preference to 'local'"""
        await user_settings_service.set_storage_preference(test_user_id, "local")
        
        preference = await user_settings_service.get_storage_preference(test_user_id)
        assert preference == "local"

    @pytest.mark.asyncio
    async def test_set_storage_preference_invalid(
        self, user_settings_service, test_user_id
    ):
        """Test that invalid storage preference raises ValueError"""
        with pytest.raises(ValueError) as exc_info:
            await user_settings_service.set_storage_preference(
                test_user_id, "invalid_preference"
            )
        
        assert "Invalid storage preference" in str(exc_info.value)
        assert "invalid_preference" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_storage_preference_persistence(
        self, user_settings_service, test_user_id
    ):
        """Test that storage preference persists across multiple gets"""
        # Set preference
        await user_settings_service.set_storage_preference(test_user_id, "pentaract")
        
        # Get preference multiple times
        pref1 = await user_settings_service.get_storage_preference(test_user_id)
        pref2 = await user_settings_service.get_storage_preference(test_user_id)
        pref3 = await user_settings_service.get_storage_preference(test_user_id)
        
        assert pref1 == pref2 == pref3 == "pentaract"

    @pytest.mark.asyncio
    async def test_storage_preference_update(
        self, user_settings_service, test_user_id
    ):
        """Test updating storage preference from one value to another"""
        # Set initial preference
        await user_settings_service.set_storage_preference(test_user_id, "auto")
        pref1 = await user_settings_service.get_storage_preference(test_user_id)
        assert pref1 == "auto"
        
        # Update to pentaract
        await user_settings_service.set_storage_preference(test_user_id, "pentaract")
        pref2 = await user_settings_service.get_storage_preference(test_user_id)
        assert pref2 == "pentaract"
        
        # Update to local
        await user_settings_service.set_storage_preference(test_user_id, "local")
        pref3 = await user_settings_service.get_storage_preference(test_user_id)
        assert pref3 == "local"

    @pytest.mark.asyncio
    async def test_valid_storage_preferences_constant(self):
        """Test that VALID_STORAGE_PREFERENCES contains expected values"""
        assert "auto" in VALID_STORAGE_PREFERENCES
        assert "pentaract" in VALID_STORAGE_PREFERENCES
        assert "local" in VALID_STORAGE_PREFERENCES
        assert len(VALID_STORAGE_PREFERENCES) == 3

    @pytest.mark.asyncio
    async def test_storage_preference_with_existing_settings(
        self, user_settings_service, test_user_id
    ):
        """Test that storage preference works with users who have existing settings"""
        # Create settings with quality and format
        await user_settings_service.set_quality(test_user_id, "high")
        await user_settings_service.set_format(test_user_id, "video")
        
        # Now set storage preference
        await user_settings_service.set_storage_preference(test_user_id, "pentaract")
        
        # Verify all settings are preserved
        settings = await user_settings_service.get_settings(test_user_id)
        assert settings.quality == "high"
        assert settings.format == "video"
        assert settings.storage_preference == "pentaract"

    @pytest.mark.asyncio
    async def test_multiple_users_different_preferences(
        self, user_settings_service
    ):
        """Test that different users can have different storage preferences"""
        user1_id = str(uuid4())
        user2_id = str(uuid4())
        user3_id = str(uuid4())
        
        # Set different preferences for each user
        await user_settings_service.set_storage_preference(user1_id, "auto")
        await user_settings_service.set_storage_preference(user2_id, "pentaract")
        await user_settings_service.set_storage_preference(user3_id, "local")
        
        # Verify each user has their own preference
        pref1 = await user_settings_service.get_storage_preference(user1_id)
        pref2 = await user_settings_service.get_storage_preference(user2_id)
        pref3 = await user_settings_service.get_storage_preference(user3_id)
        
        assert pref1 == "auto"
        assert pref2 == "pentaract"
        assert pref3 == "local"
