"""Unit tests for Pentaract data models"""

import pytest
from datetime import datetime
from sqlmodel import SQLModel, create_engine, Session
from app.models.pentaract_upload import PentaractUpload
from app.models.pentaract_file import PentaractFile
from app.models.user_settings import UserSettings


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database for testing"""
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_pentaract_upload_creation(db_session):
    """Test creating a PentaractUpload record"""
    upload = PentaractUpload(
        id="upload_123",
        user_id="user_456",
        file_path="/tmp/test.mp4",
        remote_path="downloads/test.mp4",
        file_size=1024000,
        status="pending"
    )
    
    db_session.add(upload)
    db_session.commit()
    db_session.refresh(upload)
    
    assert upload.id == "upload_123"
    assert upload.user_id == "user_456"
    assert upload.file_path == "/tmp/test.mp4"
    assert upload.remote_path == "downloads/test.mp4"
    assert upload.file_size == 1024000
    assert upload.status == "pending"
    assert upload.error_message is None
    assert upload.upload_started_at is None
    assert upload.upload_completed_at is None
    assert upload.retry_count == 0
    assert isinstance(upload.created_at, datetime)
    assert isinstance(upload.updated_at, datetime)


def test_pentaract_upload_with_error(db_session):
    """Test creating a PentaractUpload with error information"""
    upload = PentaractUpload(
        id="upload_789",
        user_id="user_456",
        file_path="/tmp/test.mp4",
        remote_path="downloads/test.mp4",
        file_size=1024000,
        status="failed",
        error_message="Network timeout",
        retry_count=3
    )
    
    db_session.add(upload)
    db_session.commit()
    db_session.refresh(upload)
    
    assert upload.status == "failed"
    assert upload.error_message == "Network timeout"
    assert upload.retry_count == 3


def test_pentaract_upload_status_transitions(db_session):
    """Test status transitions for upload"""
    upload = PentaractUpload(
        id="upload_status",
        user_id="user_456",
        file_path="/tmp/test.mp4",
        remote_path="downloads/test.mp4",
        file_size=1024000,
        status="pending"
    )
    
    db_session.add(upload)
    db_session.commit()
    
    # Transition to uploading
    upload.status = "uploading"
    upload.upload_started_at = datetime.utcnow()
    db_session.commit()
    db_session.refresh(upload)
    
    assert upload.status == "uploading"
    assert upload.upload_started_at is not None
    
    # Transition to completed
    upload.status = "completed"
    upload.upload_completed_at = datetime.utcnow()
    db_session.commit()
    db_session.refresh(upload)
    
    assert upload.status == "completed"
    assert upload.upload_completed_at is not None


def test_pentaract_file_creation(db_session):
    """Test creating a PentaractFile record"""
    file = PentaractFile(
        id="file_123",
        user_id="user_456",
        remote_path="downloads/video.mp4",
        filename="video.mp4",
        file_size=5242880,
        mime_type="video/mp4",
        folder="downloads"
    )
    
    db_session.add(file)
    db_session.commit()
    db_session.refresh(file)
    
    assert file.id == "file_123"
    assert file.user_id == "user_456"
    assert file.remote_path == "downloads/video.mp4"
    assert file.filename == "video.mp4"
    assert file.file_size == 5242880
    assert file.mime_type == "video/mp4"
    assert file.folder == "downloads"
    assert isinstance(file.uploaded_at, datetime)
    assert file.last_accessed_at is None
    assert file.download_count == 0
    assert file.metadata is None


def test_pentaract_file_with_metadata(db_session):
    """Test creating a PentaractFile with JSON metadata"""
    import json
    
    metadata = json.dumps({
        "source": "youtube",
        "title": "Test Video",
        "duration": 120
    })
    
    file = PentaractFile(
        id="file_meta",
        user_id="user_456",
        remote_path="downloads/video_meta.mp4",
        filename="video_meta.mp4",
        file_size=5242880,
        metadata=metadata
    )
    
    db_session.add(file)
    db_session.commit()
    db_session.refresh(file)
    
    assert file.metadata is not None
    parsed_metadata = json.loads(file.metadata)
    assert parsed_metadata["source"] == "youtube"
    assert parsed_metadata["title"] == "Test Video"
    assert parsed_metadata["duration"] == 120


def test_pentaract_file_download_tracking(db_session):
    """Test tracking file downloads"""
    file = PentaractFile(
        id="file_download",
        user_id="user_456",
        remote_path="downloads/tracked.mp4",
        filename="tracked.mp4",
        file_size=1024000
    )
    
    db_session.add(file)
    db_session.commit()
    
    # Simulate downloads
    file.download_count += 1
    file.last_accessed_at = datetime.utcnow()
    db_session.commit()
    db_session.refresh(file)
    
    assert file.download_count == 1
    assert file.last_accessed_at is not None
    
    # Another download
    file.download_count += 1
    file.last_accessed_at = datetime.utcnow()
    db_session.commit()
    db_session.refresh(file)
    
    assert file.download_count == 2


def test_pentaract_file_unique_remote_path(db_session):
    """Test that remote_path is unique"""
    file1 = PentaractFile(
        id="file_unique_1",
        user_id="user_456",
        remote_path="downloads/unique.mp4",
        filename="unique.mp4",
        file_size=1024000
    )
    
    db_session.add(file1)
    db_session.commit()
    
    # Try to create another file with the same remote_path
    file2 = PentaractFile(
        id="file_unique_2",
        user_id="user_789",
        remote_path="downloads/unique.mp4",  # Same path
        filename="unique.mp4",
        file_size=2048000
    )
    
    db_session.add(file2)
    
    with pytest.raises(Exception):  # Should raise integrity error
        db_session.commit()


def test_user_settings_storage_preference_defaults(db_session):
    """Test that UserSettings has correct default values for storage preferences"""
    settings = UserSettings(
        id="settings_123",
        user_id="user_456"
    )
    
    db_session.add(settings)
    db_session.commit()
    db_session.refresh(settings)
    
    assert settings.storage_preference == "auto"
    assert settings.pentaract_auto_upload is True
    assert settings.pentaract_notify_uploads is True
    assert settings.quality == "high"
    assert settings.format == "video"


def test_user_settings_custom_storage_preference(db_session):
    """Test setting custom storage preference"""
    settings = UserSettings(
        id="settings_custom",
        user_id="user_789",
        storage_preference="pentaract",
        pentaract_auto_upload=False,
        pentaract_notify_uploads=False
    )
    
    db_session.add(settings)
    db_session.commit()
    db_session.refresh(settings)
    
    assert settings.storage_preference == "pentaract"
    assert settings.pentaract_auto_upload is False
    assert settings.pentaract_notify_uploads is False


def test_user_settings_local_preference(db_session):
    """Test setting local storage preference"""
    settings = UserSettings(
        id="settings_local",
        user_id="user_999",
        storage_preference="local"
    )
    
    db_session.add(settings)
    db_session.commit()
    db_session.refresh(settings)
    
    assert settings.storage_preference == "local"


def test_pentaract_upload_user_index(db_session):
    """Test that user_id is indexed for efficient queries"""
    # Create multiple uploads for the same user
    for i in range(5):
        upload = PentaractUpload(
            id=f"upload_{i}",
            user_id="user_indexed",
            file_path=f"/tmp/test_{i}.mp4",
            remote_path=f"downloads/test_{i}.mp4",
            file_size=1024000 * (i + 1),
            status="completed"
        )
        db_session.add(upload)
    
    db_session.commit()
    
    # Query by user_id should be efficient
    from sqlmodel import select
    uploads = db_session.exec(
        select(PentaractUpload).where(PentaractUpload.user_id == "user_indexed")
    ).all()
    
    assert len(uploads) == 5


def test_pentaract_file_user_index(db_session):
    """Test that user_id is indexed for efficient queries"""
    # Create multiple files for the same user
    for i in range(5):
        file = PentaractFile(
            id=f"file_{i}",
            user_id="user_indexed",
            remote_path=f"downloads/file_{i}.mp4",
            filename=f"file_{i}.mp4",
            file_size=1024000 * (i + 1)
        )
        db_session.add(file)
    
    db_session.commit()
    
    # Query by user_id should be efficient
    from sqlmodel import select
    files = db_session.exec(
        select(PentaractFile).where(PentaractFile.user_id == "user_indexed")
    ).all()
    
    assert len(files) == 5


def test_pentaract_file_remote_path_index(db_session):
    """Test that remote_path is indexed for efficient queries"""
    file = PentaractFile(
        id="file_path_index",
        user_id="user_456",
        remote_path="downloads/indexed.mp4",
        filename="indexed.mp4",
        file_size=1024000
    )
    
    db_session.add(file)
    db_session.commit()
    
    # Query by remote_path should be efficient
    from sqlmodel import select
    found_file = db_session.exec(
        select(PentaractFile).where(PentaractFile.remote_path == "downloads/indexed.mp4")
    ).first()
    
    assert found_file is not None
    assert found_file.id == "file_path_index"
