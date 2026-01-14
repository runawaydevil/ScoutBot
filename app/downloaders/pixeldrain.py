"""Pixeldrain downloader"""

import asyncio
import re
from urllib.parse import urlparse

from app.utils.logger import get_logger
from app.downloaders.direct import DirectDownload

logger = get_logger(__name__)


class PixeldrainDownload(DirectDownload):
    """Pixeldrain downloader - uses DirectDownload internally"""

    FILE_URL_FORMAT = "https://pixeldrain.com/api/file/{}?download"
    USER_PAGE_PATTERN = re.compile(r"https://pixeldrain.com/u/(\w+)")

    def __init__(self, bot, bot_msg, url: str):
        # Extract file ID and convert to download URL
        download_url = self._get_download_url(url)
        super().__init__(bot, bot_msg, download_url)

    def _extract_file_id(self, url: str) -> str:
        """Extract file ID from Pixeldrain URL"""
        if match := self.USER_PAGE_PATTERN.match(url):
            return match.group(1)

        parsed = urlparse(url)
        if parsed.path.startswith("/file/"):
            return parsed.path.split("/")[-1]

        raise ValueError("Invalid Pixeldrain URL format")

    def _get_download_url(self, url: str) -> str:
        """Get direct download URL from Pixeldrain URL"""
        file_id = self._extract_file_id(url)
        return self.FILE_URL_FORMAT.format(file_id)


async def pixeldrain_download(bot, bot_msg, url: str):
    """Pixeldrain download entry point"""
    try:
        downloader = PixeldrainDownload(bot, bot_msg, url)
        await downloader.start()
    except ValueError as e:
        await bot_msg.edit_text(f"Download failed!❌\n\n`{e}`")
    except Exception as e:
        await bot_msg.edit_text(
            f"Download failed!❌\nAn error occurred: {str(e)}\n" "Please check your URL and try again."
        )
