"""Instagram downloader"""

import re
import time
from pathlib import Path
from typing import List

import aiohttp
import filetype

from app.utils.logger import get_logger
from app.downloaders.base import BaseDownloader

logger = get_logger(__name__)


class InstagramDownload(BaseDownloader):
    """Instagram downloader"""

    def extract_code(self) -> str | None:
        """Extract Instagram post code from URL"""
        patterns = [
            # Instagram stories highlights
            r"/stories/highlights/([a-zA-Z0-9_-]+)/",
            # Posts
            r"/p/([a-zA-Z0-9_-]+)/",
            # Reels
            r"/reel/([a-zA-Z0-9_-]+)/",
            # TV
            r"/tv/([a-zA-Z0-9_-]+)/",
            # Threads post
            r"(?:https?://)?(?:www\.)?(?:threads\.net)(?:/[@\w.]+)?(?:/post)?/([\w-]+)(?:/?\?.*)?$",
        ]

        for pattern in patterns:
            match = re.search(pattern, self._url)
            if match:
                if pattern == patterns[0]:  # Stories highlights
                    return self._url
                else:
                    return match.group(1)

        return None

    def _setup_formats(self) -> None:
        """Instagram doesn't need format setup"""
        pass

    async def _download(self, formats=None) -> List[Path]:
        """Download Instagram media"""
        try:
            # Try to use external Instagram API if available
            # For now, we'll use a simple approach
            # In production, you might want to use an Instagram API service
            async with aiohttp.ClientSession() as session:
                # This is a placeholder - you'll need to implement actual Instagram download logic
                # or use an external service
                async with session.get(f"http://instagram:15000/?url={self._url}") as resp:
                    if resp.status != 200:
                        raise ValueError(f"Instagram API returned {resp.status}")
                    data = await resp.json()
        except Exception as e:
            logger.error(f"Instagram API error: {e}")
            await self.edit_text(f"Download failed!❌\n\n`{e}`")
            return []

        code = self.extract_code()
        if not code:
            raise ValueError("Could not extract Instagram post code")

        counter = 1
        video_paths = []
        found_media_types = set()

        if url_results := data.get("data"):
            async with aiohttp.ClientSession() as session:
                for media in url_results:
                    link = media["link"]
                    media_type = media["type"]

                    if media_type == "image":
                        ext = "jpg"
                        found_media_types.add("photo")
                    elif media_type == "video":
                        ext = "mp4"
                        found_media_types.add("video")
                    else:
                        continue

                    try:
                        filename = f"Instagram_{code}-{counter}"
                        save_path = Path(self._tempdir.name) / filename

                        async with session.get(link) as req:
                            length = int(req.headers.get("content-length", 0) or req.headers.get("x-full-image-content-length", 0))
                            downloaded = 0
                            start_time = time.time()

                            with open(save_path, "wb") as fp:
                                async for chunk in req.content.iter_chunked(8192):
                                    if chunk:
                                        downloaded += len(chunk)
                                        fp.write(chunk)

                                        elapsed_time = time.time() - start_time
                                        if elapsed_time > 0:
                                            speed = downloaded / elapsed_time

                                            if speed >= 1024 * 1024:
                                                speed_str = f"{speed / (1024 * 1024):.2f}MB/s"
                                            elif speed >= 1024:
                                                speed_str = f"{speed / 1024:.2f}KB/s"
                                            else:
                                                speed_str = f"{speed:.2f}B/s"

                                            if length > 0:
                                                eta_seconds = (length - downloaded) / speed
                                                if eta_seconds >= 3600:
                                                    eta_str = f"{eta_seconds / 3600:.1f}h"
                                                elif eta_seconds >= 60:
                                                    eta_str = f"{eta_seconds / 60:.1f}m"
                                                else:
                                                    eta_str = f"{eta_seconds:.0f}s"
                                            else:
                                                eta_str = "N/A"
                                        else:
                                            speed_str = "N/A"
                                            eta_str = "N/A"

                                        d = {
                                            "status": "downloading",
                                            "downloaded_bytes": downloaded,
                                            "total_bytes": length,
                                            "_speed_str": speed_str,
                                            "_eta_str": eta_str,
                                        }

                                        self.download_hook(d)

                        if ext := filetype.guess_extension(save_path):
                            new_path = save_path.with_suffix(f".{ext}")
                            save_path.rename(new_path)
                            save_path = new_path

                        video_paths.append(save_path)
                        counter += 1

                    except Exception as e:
                        logger.error(f"Failed to download Instagram media: {e}")
                        await self.edit_text(f"Download failed!❌\n\n`{e}`")
                        return []

        if "video" in found_media_types:
            self._format = "video"
        elif "photo" in found_media_types:
            self._format = "photo"
        else:
            self._format = "document"

        return video_paths

    async def _start(self):
        """Start download and upload"""
        downloaded_files = await self._download()
        if not downloaded_files:
            raise ValueError("No files downloaded")
        await self._upload(files=downloaded_files)
