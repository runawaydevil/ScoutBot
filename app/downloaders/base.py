"""Base downloader class adapted for aiogram"""

import asyncio
import hashlib
import json
import re
import shutil
import tempfile
import uuid
from abc import ABC, abstractmethod
from io import StringIO
from pathlib import Path
from typing import Optional, List, Dict, Any, Literal

from aiogram import Bot
from aiogram.types import Message, FSInputFile
from tqdm import tqdm

from app.config import settings
from app.utils.logger import get_logger
from app.utils.download_cache import download_cache
from app.utils.download_utils import sizeof_fmt
from app.services.user_settings_service import user_settings_service
from app.downloaders.helper import convert_audio_format, get_metadata as helper_get_metadata, get_caption, generate_thumbnail

logger = get_logger(__name__)

# Verify required tools at module level
FFMPEG_AVAILABLE = shutil.which("ffmpeg") is not None
if not FFMPEG_AVAILABLE:
    logger.warning("FFmpeg not found in PATH - file splitting will not work")

# Telegram file size limits
TELEGRAM_VIDEO_MAX_SIZE = 50 * 1024 * 1024  # 50MB for video format
# Documents can be up to 2GB with Local Bot API Server, or 50MB with standard Bot API

# Global debounce state
_edit_text_last_called = {}
_edit_text_lock = asyncio.Lock()


class BaseDownloader(ABC):
    """Base downloader class for all download types"""

    def __init__(self, bot: Bot, bot_msg: Message, url: str):
        self._bot = bot
        self._url = url
        self._chat_id = bot_msg.chat.id
        self._from_user = bot_msg.from_user.id if bot_msg.from_user else bot_msg.chat.id
        self._bot_msg = bot_msg
        self._tempdir = tempfile.TemporaryDirectory(prefix="scoutbot-")
        self._quality: Literal["high", "medium", "low", "audio", "custom"] = "high"
        self._format: Literal["video", "audio", "document"] = "video"

    def __del__(self):
        """Cleanup temporary directory"""
        try:
            self._tempdir.cleanup()
        except Exception:
            pass

    async def _load_user_settings(self):
        """Load user quality and format settings"""
        user_id = str(self._from_user)
        
        # Check if format/quality are forced (e.g., for MP3 conversion)
        if hasattr(self, '_force_format') and self._force_format:
            self._format = self._force_format
        else:
            self._format = await user_settings_service.get_format(user_id)
        
        if hasattr(self, '_force_quality') and self._force_quality:
            self._quality = self._force_quality
        else:
            self._quality = await user_settings_service.get_quality(user_id)

    @staticmethod
    def _remove_bash_color(text: str) -> str:
        """Remove ANSI color codes from text"""
        return re.sub(r"\u001b|\[0;94m|\u001b\[0m|\[0;32m|\[0m|\[0;33m", "", text)

    @staticmethod
    def _tqdm_progress(desc: str, total: int, finished: int, speed: str = "", eta: str = "") -> str:
        """Generate progress bar text using tqdm"""
        def more(title: str, initial: str) -> str:
            if initial:
                return f"{title} {initial}"
            return ""

        f = StringIO()
        tqdm(
            total=total,
            initial=finished,
            file=f,
            ascii=False,
            unit_scale=True,
            ncols=30,
            bar_format="{l_bar}{bar} |{n_fmt}/{total_fmt} ",
        )
        raw_output = f.getvalue()
        tqdm_output = raw_output.split("|")
        progress = f"`[{tqdm_output[1]}]`" if len(tqdm_output) > 1 else "`[   ]`"
        detail = tqdm_output[2].replace("[A", "") if len(tqdm_output) > 2 else ""
        text = f"""
{desc}

{progress}
{detail}
{more("Speed:", speed)}
{more("ETA:", eta)}
        """
        f.close()
        return text.strip()

    def download_hook(self, d: Dict[str, Any]):
        """Hook for download progress updates (synchronous for yt-dlp compatibility)"""
        # Progress updates disabled - user only needs to know download is in progress
        # Detailed progress (speed, ETA, bar) is not shown to reduce message spam
        if d.get("status") == "downloading":
            # Only log progress for debugging, don't update user message
            downloaded = d.get("downloaded_bytes", 0)
            total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
            if total > 0:
                percent = (downloaded / total) * 100
                logger.debug(f"Download progress: {percent:.1f}% ({downloaded}/{total} bytes)")

    async def upload_hook(self, current: int, total: int):
        """Hook for upload progress updates"""
        # Progress updates disabled - user only needs to know upload is in progress
        # Detailed progress is not shown to reduce message spam
        if total > 0:
            percent = (current / total) * 100
            logger.debug(f"Upload progress: {percent:.1f}% ({current}/{total} bytes)")

    async def edit_text(self, text: str):
        """Edit bot message with debounce"""
        key = (self._chat_id, self._bot_msg.message_id)
        now = asyncio.get_event_loop().time()
        wait_seconds = 5.0

        async with _edit_text_lock:
            if key in _edit_text_last_called:
                if now - _edit_text_last_called[key] < wait_seconds:
                    return  # Skip if called too recently
            _edit_text_last_called[key] = now

        try:
            await self._bot.edit_message_text(
                chat_id=self._chat_id,
                message_id=self._bot_msg.message_id,
                text=text,
                parse_mode="HTML",
            )
        except Exception as e:
            logger.debug(f"Failed to edit message (may be rate limited): {e}")

    @abstractmethod
    def _setup_formats(self) -> Optional[List[str]]:
        """Setup download formats - to be implemented by subclasses"""
        pass

    @abstractmethod
    async def _download(self, formats: Optional[List[str]] = None) -> List[Path]:
        """Download files - to be implemented by subclasses"""
        pass

    def _check_file_size(self, file_path: Path) -> tuple[bool, str]:
        """Check if file size is within Telegram limits"""
        file_size = file_path.stat().st_size
        if self._format == "video" and file_size > TELEGRAM_VIDEO_MAX_SIZE:
            return False, f"File size {sizeof_fmt(file_size)} exceeds Telegram video limit (50MB). Trying as document..."
        return True, ""

    async def get_metadata(self, video_path: Path) -> Dict[str, Any]:
        """Get video metadata"""
        if not video_path.exists():
            raise ValueError(f"Video file does not exist: {video_path}")
        
        if video_path.stat().st_size == 0:
            raise ValueError(f"Video file is empty: {video_path}")
        
        meta = helper_get_metadata(video_path)
        filename = video_path.name
        
        # Only generate thumbnail for video files, not audio
        # Skip thumbnail generation for audio format
        thumb = None
        if settings.enable_ffmpeg and self._format != "audio":
            try:
                # Check if file has video stream before generating thumbnail
                import ffmpeg as ffmpeg_lib
                streams = ffmpeg_lib.probe(str(video_path)).get("streams", [])
                has_video = any(s.get("codec_type") == "video" for s in streams)
                if has_video:
                    thumb = generate_thumbnail(video_path)
            except Exception as e:
                logger.debug(f"Could not check for video stream or generate thumbnail: {e}")

        caption = get_caption(self._url, video_path)

        return {
            "height": meta["height"],
            "width": meta["width"],
            "duration": meta["duration"],
            "thumb": str(thumb) if thumb else None,
            "caption": caption,
        }

    def _filter_downloaded_files(self, files: List[Path]) -> List[Path]:
        """
        Filter out temporary files that should not be uploaded (cookies, metadata, etc.)
        
        Args:
            files: List of file paths to filter
            
        Returns:
            Filtered list containing only actual media files
        """
        # Specific files to exclude (cookies, metadata, thumbnails, etc.)
        exclude_names = [
            "youtube-cookies.txt",
            "cookies.txt",
            ".cookies",
        ]
        
        # Extensions to exclude (metadata, thumbnails, etc.)
        exclude_extensions = [
            ".json",  # Metadata files
            ".jpg", ".jpeg", ".png", ".webp",  # Thumbnails
            ".description",  # Description files
            ".info.json",  # yt-dlp info files
        ]
        
        filtered = []
        for file_path in files:
            # Skip directories
            if not file_path.is_file():
                continue
            
            # Skip very small files (< 1KB) - likely metadata or cookies
            # Exception: allow small audio files that might be valid
            file_size = file_path.stat().st_size
            if file_size < 1024:
                # Check if it's a known cookie/metadata file
                is_cookie_file = any(
                    exclude_name in file_path.name.lower() 
                    for exclude_name in ["cookie", "metadata", "info", "description"]
                )
                if is_cookie_file:
                    continue
            
            # Skip files matching exclude names
            should_exclude = False
            file_name_lower = file_path.name.lower()
            for exclude_name in exclude_names:
                if exclude_name.lower() in file_name_lower:
                    should_exclude = True
                    break
            
            # Skip files matching exclude extensions
            if not should_exclude:
                for ext in exclude_extensions:
                    if file_path.name.endswith(ext) or file_path.name.endswith(ext.upper()):
                        should_exclude = True
                        break
            
            if not should_exclude:
                filtered.append(file_path)
        
        return filtered

    async def _upload(self, files: Optional[List[Path]] = None, meta: Optional[Dict[str, Any]] = None):
        """Upload files to Telegram"""
        if files is None:
            files = list(Path(self._tempdir.name).glob("*"))
            # Filter out temporary files (cookies, metadata, etc.)
            files = self._filter_downloaded_files(files)

        if not files:
            raise ValueError("No files to upload")

        # Get metadata if not provided
        if meta is None:
            video_path = files[0]
            if not video_path.exists():
                raise ValueError(f"Downloaded file does not exist: {video_path}")
            if video_path.stat().st_size == 0:
                raise ValueError(f"Downloaded file is empty: {video_path}")
            meta = await self.get_metadata(video_path)

        # Check file size and adjust format if necessary
        file_path = files[0]
        file_size = file_path.stat().st_size
        
        # If video is too large for video format, force as document
        # But keep the file intact - no splitting
        is_valid, warning = self._check_file_size(files[0])
        if not is_valid:
            logger.warning(warning)
            if self._format == "video":
                self._format = "document"
                await self.edit_text("Preparing your file...")

        # Convert audio format if needed
        if self._format == "audio" and settings.enable_ffmpeg:
            files = convert_audio_format(files, self._bot_msg)

        # Send based on format
        success = None
        try:
            if self._format == "document":
                logger.debug(f"Sending as document for {self._url}")
                # Always use chunked upload for large files (1MB chunks as recommended by Telegram)
                # This allows sending files larger than 50MB if the bot has access to Local Bot API Server
                chunk_size = 1024 * 1024  # 1MB chunks
                file = FSInputFile(files[0], chunk_size=chunk_size)
                logger.debug(f"Using chunked upload with {chunk_size} byte chunks for file size {sizeof_fmt(file_size)}")
                try:
                    success = await self._bot.send_document(
                        chat_id=self._chat_id,
                        document=file,
                        caption=meta.get("caption"),
                        thumbnail=FSInputFile(meta["thumb"]) if meta.get("thumb") and Path(meta["thumb"]).exists() else None,
                    )
                    if not success:
                        raise ValueError("Failed to upload document: send_document returned None")
                except Exception as doc_error:
                    logger.error(f"Error sending document: {doc_error}", exc_info=True)
                    raise
            elif self._format == "audio":
                logger.debug(f"Sending as audio for {self._url}")
                # Always use chunked upload for large files
                chunk_size = 1024 * 1024  # 1MB chunks
                file = FSInputFile(files[0], chunk_size=chunk_size)
                logger.debug(f"Using chunked upload with {chunk_size} byte chunks for file size {sizeof_fmt(file_size)}")
                success = await self._bot.send_audio(
                    chat_id=self._chat_id,
                    audio=file,
                    caption=meta.get("caption"),
                    thumbnail=FSInputFile(meta["thumb"]) if meta.get("thumb") and Path(meta["thumb"]).exists() else None,
                )
                if not success:
                    raise ValueError("Failed to upload audio: send_audio returned None")
            elif self._format == "video":
                logger.debug(f"Sending as video for {self._url}")
                # Try multiple methods
                attempt_methods = ["video", "animation", "document", "audio"]
                # Always use chunked upload for large files
                chunk_size = 1024 * 1024  # 1MB chunks
                file = FSInputFile(files[0], chunk_size=chunk_size)
                logger.debug(f"Using chunked upload with {chunk_size} byte chunks for file size {sizeof_fmt(file_size)}")

                last_error = None
                size_error_detected = False
                for method in attempt_methods:
                    try:
                        if method == "video":
                            success = await self._bot.send_video(
                                chat_id=self._chat_id,
                                video=file,
                                caption=meta.get("caption"),
                                thumbnail=FSInputFile(meta["thumb"]) if meta.get("thumb") and Path(meta["thumb"]).exists() else None,
                                width=meta.get("width"),
                                height=meta.get("height"),
                                duration=meta.get("duration"),
                            )
                        elif method == "animation":
                            success = await self._bot.send_animation(
                                chat_id=self._chat_id,
                                animation=file,
                                caption=meta.get("caption"),
                                thumbnail=FSInputFile(meta["thumb"]) if meta.get("thumb") and Path(meta["thumb"]).exists() else None,
                            )
                        elif method == "document":
                            success = await self._bot.send_document(
                                chat_id=self._chat_id,
                                document=file,
                                caption=meta.get("caption"),
                                thumbnail=FSInputFile(meta["thumb"]) if meta.get("thumb") and Path(meta["thumb"]).exists() else None,
                            )
                        elif method == "audio":
                            success = await self._bot.send_audio(
                                chat_id=self._chat_id,
                                audio=file,
                                caption=meta.get("caption"),
                                thumbnail=FSInputFile(meta["thumb"]) if meta.get("thumb") and Path(meta["thumb"]).exists() else None,
                            )

                        if success:
                            break
                    except Exception as e:
                        error_msg = str(e)
                        last_error = e
                        # Check if it's a size error
                        if "Request Entity Too Large" in error_msg or "too large" in error_msg.lower():
                            size_error_detected = True
                            logger.warning(f"Failed to send as {method} (file too large): {e}")
                            # If we haven't tried document yet, continue to try it
                            if method != "document" and "document" in attempt_methods:
                                continue
                            # If document also failed, break and let outer handler deal with it
                            break
                        logger.warning(f"Failed to send as {method}: {e}")
                        continue

                if not success:
                    # If size error was detected, raise specific error for outer handler
                    if size_error_detected:
                        raise ValueError("ERROR: File too large for video format. Trying as document...")
                    raise ValueError("ERROR: Failed to upload video. Try again with `/download`.")

            # Cache the result
            if success:
                file_id = None
                if hasattr(success, "video") and success.video is not None:
                    file_id = success.video.file_id
                elif hasattr(success, "document") and success.document is not None:
                    file_id = success.document.file_id
                elif hasattr(success, "audio") and success.audio is not None:
                    file_id = success.audio.file_id
                elif hasattr(success, "animation") and success.animation is not None:
                    file_id = success.animation.file_id

                if file_id:
                    # Prepare meta without thumb path (just keep thumb as boolean)
                    cache_meta = {k: v for k, v in meta.items() if k != "thumb"}
                    cache_meta["has_thumb"] = bool(meta.get("thumb"))
                    await download_cache.set_cache(
                        self._url,
                        self._quality,
                        self._format,
                        [file_id],
                        cache_meta,
                    )

                await self.edit_text("✅ Success")
                logger.debug(f"Successfully uploaded {self._url}")
                
                # Record download statistic
                try:
                    from app.services.statistics_service import statistics_service
                    chat_id = str(self._chat_id)
                    downloader_type = self.__class__.__name__.replace("Download", "").lower()
                    await statistics_service.record_download(
                        downloader_type=downloader_type,
                        status="success",
                        chat_id=chat_id,
                        file_size=file_size,
                    )
                except Exception as e:
                    logger.debug(f"Failed to record download statistic: {e}")

        except Exception as e:
            # Record failed download statistic
            try:
                from app.services.statistics_service import statistics_service
                chat_id = str(self._chat_id)
                downloader_type = self.__class__.__name__.replace("Download", "").lower()
                await statistics_service.record_download(
                    downloader_type=downloader_type,
                    status="failed",
                    chat_id=chat_id,
                    error_message=str(e)[:200],  # Truncate long errors
                )
            except Exception:
                pass
            
            error_msg = str(e)
            # Check if error is due to file size
            if "Request Entity Too Large" in error_msg or "too large" in error_msg.lower():
                if self._format != "document":
                    # Try as document
                    logger.debug("File too large, trying as document...")
                    original_format = self._format
                    self._format = "document"
                    await self.edit_text("Preparing your file...")
                    try:
                        return await self._upload(files, meta)
                    except Exception as e2:
                        file_size = file_path.stat().st_size
                        raise ValueError(
                            f"File size {sizeof_fmt(file_size)} is too large for Telegram. "
                            f"Try downloading with lower quality or use /download command."
                        )
                else:
                    # Already tried as document, file is too large
                    # Chunked upload was already attempted, so this is a hard limit
                    file_size = file_path.stat().st_size
                    raise ValueError(
                        f"File size {sizeof_fmt(file_size)} is too large for Telegram Bot API (50MB limit). "
                        f"To send larger files, you need to set up a Local Bot API Server. "
                        f"Try downloading with lower quality or use /download command."
                    )
            
            logger.error(f"Failed to upload {self._url}: {e}")
            await self.edit_text(f"❌ Upload failed: {e}")
            raise

        return success

    async def _get_video_cache(self) -> Optional[Dict[str, Any]]:
        """Get cached video data"""
        return await download_cache.get_cache(self._url, self._quality, self._format)

    async def start(self):
        """Start download process - check bot state first"""
        # Check if bot is stopped
        from app.services.bot_state_service import bot_state_service
        is_stopped = await bot_state_service.is_stopped()
        if is_stopped:
            await self.edit_text("🛑 Bot is stopped. Use /start to resume operations.")
            return
        
        await self._load_user_settings()

        # Check cache first
        cached = await self._get_video_cache()
        if cached:
            logger.debug(f"Cache hit for {self._url}")
            try:
                file_id = json.loads(cached["file_id"])
                meta = json.loads(cached["meta"])
                meta["cache"] = True

                # Send cached file
                if file_id and file_id[0]:
                    # Try to send as video first, fallback to document
                    try:
                        await self._bot.send_video(
                            chat_id=self._chat_id,
                            video=file_id[0],
                            caption=meta.get("caption"),
                        )
                    except Exception:
                        # Fallback to document
                        await self._bot.send_document(
                            chat_id=self._chat_id,
                            document=file_id[0],
                            caption=meta.get("caption"),
                        )
                    await self.edit_text("✅ Success (from cache)")
                    return
            except Exception as e:
                logger.warning(f"Failed to use cache: {e}, downloading fresh")

        # No cache, download fresh
        await self._start()

    @abstractmethod
    async def _start(self):
        """Start download - to be implemented by subclasses"""
        pass
