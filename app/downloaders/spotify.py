"""Spotify downloader using spotDL"""

import re
import tempfile
from pathlib import Path
from typing import List, Optional

from aiogram import Bot
from aiogram.types import Message

from app.config import settings
from app.downloaders.base import BaseDownloader
from app.utils.logger import get_logger
from app.utils.download_utils import normalize_spotify_url
from app.utils.spotdl_wrapper import get_spotdl_wrapper, SpotdlWrapper
from app.utils.spotdl.types.song import Song
from app.utils.zip_utils import create_zip_from_files

logger = get_logger(__name__)

# Maximum number of songs to download from playlists/albums/artists
MAX_SONGS_LIMIT = 50


class SpotifyDownload(BaseDownloader):
    """Spotify downloader using spotDL"""

    def __init__(self, bot: Bot, bot_msg: Message, url: str):
        """Initialize Spotify downloader"""
        # Normalize URL to remove localized paths and query parameters
        normalized_url = normalize_spotify_url(url)
        if normalized_url != url:
            logger.debug(f"Normalized Spotify URL: {url} -> {normalized_url}")
        super().__init__(bot, bot_msg, normalized_url)
        self._wrapper: Optional[SpotdlWrapper] = None
        self._force_format = "audio"  # Spotify downloads are always audio
        self._force_quality = "high"  # Always use high quality for music
        self._is_batch = False  # Will be set in _start() based on URL type

    def _setup_formats(self) -> Optional[List[str]]:
        """Setup download formats - Spotify doesn't use format strings like YouTube"""
        # Spotify uses spotDL which handles format selection internally
        return None

    async def _download(self, songs: List[Song], formats: Optional[List[str]] = None) -> List[Path]:
        """Download files - implemented for abstract method compatibility"""
        if not self._wrapper:
            self._wrapper = get_spotdl_wrapper()

        if not songs:
            raise ValueError("No songs found for the provided Spotify URL")

        # Limit number of songs for playlists/albums/artists
        if len(songs) > MAX_SONGS_LIMIT:
            songs = songs[:MAX_SONGS_LIMIT]

        # Download songs with progress updates
        downloaded_files: List[Path] = []
        total = len(songs)

        for idx, song in enumerate(songs, 1):
            try:
                song_name = f"{song.artist} - {song.name}"
                
                # Use English messages for batch downloads
                if self._is_batch:
                    await self.edit_text(
                        f"Downloading {idx}/{total}:\n{song_name}"
                    )
                else:
                    await self.edit_text(
                        f"📥 Downloading {idx}/{total}:\n{song_name}"
                    )

                song_result, file_path = await self._wrapper.download_song(song)

                if file_path and file_path.exists():
                    downloaded_files.append(file_path)
                    logger.info(
                        f"Successfully downloaded: {song_name} -> {file_path}"
                    )
                else:
                    logger.warning(f"Failed to download: {song_name}")
                    if self._is_batch:
                        await self.edit_text(
                            f"Failed to download: {song_name}\nContinuing..."
                        )
                    else:
                        await self.edit_text(
                            f"⚠️ Failed to download: {song_name}\nContinuing..."
                        )

            except Exception as e:
                logger.error(f"Error downloading song {song.name}: {e}", exc_info=True)
                if self._is_batch:
                    await self.edit_text(
                        f"Error downloading: {song.name}\n{str(e)[:100]}\nContinuing..."
                    )
                else:
                    await self.edit_text(
                        f"⚠️ Error downloading: {song.name}\n{str(e)[:100]}\nContinuing..."
                    )
                continue

        if not downloaded_files:
            raise ValueError("No songs were successfully downloaded")

        return downloaded_files

    async def _start(self):
        """Start download and upload"""
        try:
            # Initialize wrapper (reuse global instance to avoid SpotifyClient re-initialization)
            if not self._wrapper:
                self._wrapper = get_spotdl_wrapper()

            # Parse URL to determine type
            url_type = self._parse_spotify_url_type(self._url)
            logger.debug(f"Detected Spotify URL type: {url_type} for {self._url}")

            # Determine if this is a batch download (playlist, album, or artist)
            self._is_batch = url_type in ("playlist", "album", "artist")

            # Search for songs first to show progress
            if self._is_batch:
                await self.edit_text("Searching for songs...")
            else:
                await self.edit_text("🔍 Searching for songs...")
            
            songs = await self._wrapper.search_songs([self._url])

            if not songs:
                raise ValueError("No songs found for the provided Spotify URL")

            # For individual tracks, only download the first result
            if not self._is_batch and url_type == "track":
                if len(songs) > 1:
                    logger.debug(
                        f"Track URL detected: found {len(songs)} results, using only the first one"
                    )
                    songs = [songs[0]]
                await self.edit_text("📥 Found song, downloading...")
            elif len(songs) > MAX_SONGS_LIMIT:
                # Limit number of songs for playlists/albums/artists
                logger.warning(
                    f"Found {len(songs)} songs, limiting to {MAX_SONGS_LIMIT}"
                )
                songs = songs[:MAX_SONGS_LIMIT]
                if self._is_batch:
                    await self.edit_text(
                        f"Found {len(songs)} songs (limited to {MAX_SONGS_LIMIT})..."
                    )
                else:
                    await self.edit_text(
                        f"📥 Found {len(songs)} songs (limited to {MAX_SONGS_LIMIT})..."
                    )
            else:
                if self._is_batch:
                    await self.edit_text(f"Found {len(songs)} song(s)...")
                else:
                    await self.edit_text(f"📥 Found {len(songs)} song(s)...")

            # Download songs using _download method
            downloaded_files = await self._download(songs)

            # Handle upload based on batch or single track
            if self._is_batch and len(downloaded_files) > 1:
                # Batch download: create ZIP and upload single file
                await self.edit_text("Creating ZIP archive...")
                
                # Create ZIP file in temp directory
                temp_dir = Path(tempfile.gettempdir())
                zip_path = temp_dir / "scoutbotspotify.zip"
                
                # Create ZIP from all downloaded files
                if not create_zip_from_files(downloaded_files, zip_path):
                    raise ValueError("Failed to create ZIP archive")
                
                logger.info(f"Created ZIP archive: {zip_path} with {len(downloaded_files)} files")
                
                # Upload ZIP file
                await self.edit_text("Uploading ZIP file...")
                await self._upload(files=[zip_path])
                
            elif len(downloaded_files) == 1:
                # Single file - upload directly (no ZIP for single tracks)
                await self._upload(files=downloaded_files)
            else:
                # Multiple files but not batch (shouldn't happen, but handle gracefully)
                await self.edit_text(f"📤 Uploading {len(downloaded_files)} file(s)...")
                for idx, file_path in enumerate(downloaded_files, 1):
                    try:
                        await self.edit_text(
                            f"📤 Uploading {idx}/{len(downloaded_files)}..."
                        )
                        await self._upload(files=[file_path])
                    except Exception as e:
                        logger.error(f"Error uploading file {file_path}: {e}")
                        await self.edit_text(
                            f"⚠️ Failed to upload file {idx}/{len(downloaded_files)}\nContinuing..."
                        )

        except ValueError as e:
            logger.error(f"Spotify download failed: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in Spotify download: {e}", exc_info=True)
            raise ValueError(f"Spotify download failed: {str(e)}")

    async def _send_files(self, files: List[Path]) -> None:
        """
        Override base class _send_files to skip audio conversion.
        spotDL already downloads in the correct format (MP3), so we don't need
        to convert again. This prevents FFmpeg errors and unnecessary processing.
        """
        # Skip convert_audio_format - spotDL already handled it
        # Just send the files directly
        if self._format == "audio":
            await self._send_audio(files)
        else:
            await self._send_video(files)

    def _parse_spotify_url_type(self, url: str) -> str:
        """Parse Spotify URL to determine type (track, playlist, album, artist)"""
        url_lower = url.lower()

        if "/track/" in url_lower:
            return "track"
        elif "/playlist/" in url_lower:
            return "playlist"
        elif "/album/" in url_lower:
            return "album"
        elif "/artist/" in url_lower:
            return "artist"
        else:
            return "unknown"
