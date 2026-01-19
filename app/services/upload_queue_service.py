"""Upload Queue Service for managing Pentaract uploads"""

import asyncio
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime
from uuid import uuid4
import mimetypes

from app.config import settings
from app.utils.logger import get_logger
from app.services.pentaract_storage_service import pentaract_storage
from app.models.pentaract_upload import PentaractUpload, generate_file_code
from app.database import database
from app.utils.file_security import validate_file_safety, get_file_info

logger = get_logger(__name__)


class UploadQueueService:
    """Service for managing upload queue to Pentaract"""
    
    def __init__(self):
        self._queue: asyncio.Queue = asyncio.Queue()
        self._running = False
        self._worker_task: Optional[asyncio.Task] = None
        self._current_uploads: Dict[str, Dict[str, Any]] = {}
        self._max_concurrent = settings.pentaract_max_concurrent_uploads
    
    async def start(self):
        """Start the upload queue worker"""
        if self._running:
            logger.warning("Upload queue service is already running")
            return
        
        self._running = True
        self._worker_task = asyncio.create_task(self._process_queue())
        logger.info(
            f"Upload queue service started "
            f"(max concurrent: {self._max_concurrent})"
        )
    
    async def stop(self):
        """Stop the upload queue worker"""
        if not self._running:
            return
        
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Upload queue service stopped")
    
    async def add_to_queue(
        self,
        file_path: Path,
        user_id: str,
        folder: str = "storage"
    ) -> tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Add file to upload queue with security validation
        
        Args:
            file_path: Local file path
            user_id: User ID
            folder: Folder in Pentaract storage (default: "storage")
            
        Returns:
            Tuple of (upload_id, file_code, error_message)
            - upload_id: Upload ID if successful, None if failed
            - file_code: Unique file code for download (e.g., ABC123)
            - error_message: Error message if validation failed
        """
        # Validate file safety
        is_safe, reason = validate_file_safety(file_path.name)
        if not is_safe:
            logger.warning(f"File rejected for security reasons: {file_path.name} - {reason}")
            return None, None, reason
        
        # Generate unique file code
        file_code = await self._generate_unique_code()
        
        # Get file extension
        file_ext = file_path.suffix
        
        # Create remote path with folder included
        # This will be used as-is in Pentaract (no folder parameter)
        remote_path = f"{folder}/{file_code}{file_ext}"
        
        # Get file info
        file_info = get_file_info(file_path)
        mime_type = file_info.get('mime_type', 'application/octet-stream')
        
        upload_id = str(uuid4())
        
        # Create database record
        try:
            with database.get_session() as session:
                upload_record = PentaractUpload(
                    id=upload_id,
                    user_id=user_id,
                    file_code=file_code,
                    original_filename=file_path.name,
                    file_path=str(file_path),
                    remote_path=remote_path,
                    file_size=file_path.stat().st_size,
                    mime_type=mime_type,
                    status="pending",
                    upload_started_at=datetime.utcnow()
                )
                session.add(upload_record)
                session.commit()
                logger.debug(f"Created upload record: {upload_id} with code {file_code}")
        except Exception as e:
            logger.error(f"Failed to create upload record: {e}")
            return None, None, f"Database error: {str(e)}"
        
        upload_item = {
            "id": upload_id,
            "file_code": file_code,
            "file_path": file_path,
            "remote_path": remote_path,
            "original_filename": file_path.name,
            "user_id": user_id,
            "folder": folder,
            "status": "pending",
            "added_at": datetime.utcnow(),
            "retry_count": 0,
        }
        
        await self._queue.put(upload_item)
        logger.info(f"Added upload to queue: {upload_id} - {file_path.name} (code: {file_code})")
        
        return upload_id, file_code, None
    
    async def _generate_unique_code(self, max_attempts: int = 10) -> str:
        """
        Generate a unique file code
        
        Args:
            max_attempts: Maximum attempts to generate unique code
            
        Returns:
            Unique file code
        """
        from sqlmodel import select
        
        for attempt in range(max_attempts):
            code = generate_file_code()
            
            # Check if code already exists
            try:
                with database.get_session() as session:
                    statement = select(PentaractUpload).where(
                        PentaractUpload.file_code == code
                    )
                    existing = session.exec(statement).first()
                    
                    if not existing:
                        return code
            except Exception as e:
                logger.warning(f"Error checking code uniqueness: {e}")
                # If database check fails, just return the code
                return code
        
        # If all attempts failed, add timestamp to ensure uniqueness
        import time
        return f"{generate_file_code()}{int(time.time()) % 1000}"
    
    async def _process_queue(self):
        """Process upload queue with sequential uploads"""
        while self._running:
            try:
                # Get next upload from queue (wait up to 1 second)
                try:
                    upload_item = await asyncio.wait_for(
                        self._queue.get(),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue
                
                # Process upload sequentially (one at a time)
                await self._process_upload(upload_item)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error processing upload queue: {e}", exc_info=True)
    
    async def _process_upload(self, upload_item: Dict[str, Any]):
        """
        Process a single upload with resource monitoring
        
        Args:
            upload_item: Upload item dictionary
        """
        upload_id = upload_item["id"]
        file_path = upload_item["file_path"]
        remote_path = upload_item["remote_path"]
        folder = upload_item["folder"]
        user_id = upload_item["user_id"]
        
        # Check resources before upload
        from app.services.resource_monitor_service import resource_monitor
        await resource_monitor.wait_if_throttled("upload queue processing")
        
        # Update status to uploading
        self._current_uploads[upload_id] = {
            **upload_item,
            "status": "uploading",
            "started_at": datetime.utcnow(),
        }
        
        logger.info(f"Processing upload: {upload_id} - {file_path.name}")
        
        try:
            # Check if file exists
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")
            
            # Upload to Pentaract
            # remote_path already includes the folder (e.g., "storage/ABC123.png")
            result = await pentaract_storage.upload_file(
                file_path=file_path,
                remote_path=remote_path,
                folder=""  # Don't add folder prefix, it's already in remote_path
            )
            
            if result.get("success"):
                # Upload successful
                self._current_uploads[upload_id]["status"] = "completed"
                self._current_uploads[upload_id]["completed_at"] = datetime.utcnow()
                
                logger.info(f"Upload completed: {upload_id} - {file_path.name}")
                
                # Update database record if exists
                await self._update_upload_record(
                    upload_id=upload_id,
                    status="completed",
                    error_message=None
                )
                
                # Delete temp file after successful upload
                try:
                    if file_path.exists():
                        file_path.unlink()
                        logger.debug(f"Deleted temp file: {file_path}")
                except Exception as cleanup_error:
                    logger.warning(f"Failed to delete temp file {file_path}: {cleanup_error}")
                
                # Trigger garbage collection after upload if enabled
                if settings.resource_gc_after_upload:
                    import gc
                    logger.debug("Running garbage collection after queued upload")
                    gc.collect()
            else:
                # Upload failed
                error_msg = result.get("error", "Unknown error")
                raise Exception(error_msg)
        
        except Exception as e:
            logger.error(f"Upload failed: {upload_id} - {e}")
            
            # Update status to failed
            self._current_uploads[upload_id]["status"] = "failed"
            self._current_uploads[upload_id]["error"] = str(e)
            self._current_uploads[upload_id]["failed_at"] = datetime.utcnow()
            
            # Check if should retry
            retry_count = upload_item.get("retry_count", 0)
            max_retries = settings.pentaract_retry_attempts
            
            if retry_count < max_retries:
                # Retry upload
                logger.info(
                    f"Retrying upload: {upload_id} "
                    f"(attempt {retry_count + 1}/{max_retries})"
                )
                
                # Add back to queue with incremented retry count
                upload_item["retry_count"] = retry_count + 1
                await self._queue.put(upload_item)
            else:
                # Max retries reached
                logger.error(
                    f"Upload failed after {max_retries} attempts: {upload_id}"
                )
                
                # Update database record
                await self._update_upload_record(
                    upload_id=upload_id,
                    status="failed",
                    error_message=str(e)
                )
                
                # Delete temp file after failed upload (max retries reached)
                try:
                    if file_path.exists():
                        file_path.unlink()
                        logger.debug(f"Deleted temp file after failed upload: {file_path}")
                except Exception as cleanup_error:
                    logger.warning(f"Failed to delete temp file {file_path}: {cleanup_error}")
        
        finally:
            # Remove from current uploads after a delay
            await asyncio.sleep(5)
            if upload_id in self._current_uploads:
                del self._current_uploads[upload_id]
    
    async def _update_upload_record(
        self,
        upload_id: str,
        status: str,
        error_message: Optional[str] = None
    ):
        """
        Update upload record in database
        
        Args:
            upload_id: Upload ID
            status: New status
            error_message: Error message if failed
        """
        try:
            with database.get_session() as session:
                # Try to find existing record
                from sqlmodel import select
                statement = select(PentaractUpload).where(
                    PentaractUpload.id == upload_id
                )
                upload_record = session.exec(statement).first()
                
                if upload_record:
                    upload_record.status = status
                    if error_message:
                        upload_record.error_message = error_message
                    if status == "completed":
                        upload_record.upload_completed_at = datetime.utcnow()
                    
                    session.add(upload_record)
                    session.commit()
        
        except Exception as e:
            logger.warning(f"Failed to update upload record: {e}")
    
    async def get_queue_status(self) -> Dict[str, Any]:
        """
        Get current queue status
        
        Returns:
            Dict with queue statistics
        """
        return {
            "queue_size": self._queue.qsize(),
            "current_uploads": len(self._current_uploads),
            "max_concurrent": self._max_concurrent,
            "running": self._running,
            "uploads": list(self._current_uploads.values()),
        }
    
    async def cancel_upload(self, upload_id: str) -> bool:
        """
        Cancel an upload
        
        Args:
            upload_id: Upload ID to cancel
            
        Returns:
            True if cancelled successfully
        """
        if upload_id in self._current_uploads:
            # Mark as cancelled
            self._current_uploads[upload_id]["status"] = "cancelled"
            logger.info(f"Cancelled upload: {upload_id}")
            
            # Update database record
            await self._update_upload_record(
                upload_id=upload_id,
                status="failed",
                error_message="Cancelled by user"
            )
            
            return True
        
        return False
    
    async def retry_failed_upload(self, upload_id: str) -> bool:
        """
        Retry a failed upload
        
        Args:
            upload_id: Upload ID to retry
            
        Returns:
            True if added to queue successfully
        """
        # Check if upload exists in current uploads
        if upload_id in self._current_uploads:
            upload_item = self._current_uploads[upload_id]
            
            if upload_item["status"] == "failed":
                # Reset retry count and add back to queue
                upload_item["retry_count"] = 0
                upload_item["status"] = "pending"
                await self._queue.put(upload_item)
                
                logger.info(f"Retrying failed upload: {upload_id}")
                return True
        
        return False


# Global upload queue service instance
upload_queue_service = UploadQueueService()
