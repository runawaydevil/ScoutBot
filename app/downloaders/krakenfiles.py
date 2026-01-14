"""KrakenFiles downloader"""

import asyncio
from bs4 import BeautifulSoup

import aiohttp

from app.utils.logger import get_logger
from app.downloaders.direct import DirectDownload

logger = get_logger(__name__)


class KrakenFilesDownload(DirectDownload):
    """KrakenFiles downloader - uses DirectDownload internally"""

    def __init__(self, bot, bot_msg, url: str):
        # Will extract download URL in _start
        self._original_url = url
        super().__init__(bot, bot_msg, url)

    async def _extract_form_data(self, url: str) -> tuple[str, dict]:
        """Extract form data from KrakenFiles page"""
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                resp.raise_for_status()
                content = await resp.text()
                soup = BeautifulSoup(content, "html.parser")

                # Find form action
                form = soup.find("form", {"id": "dl-form"})
                if not form:
                    raise ValueError("ERROR: Unable to find download form.")

                post_url = form.get("action")
                if not post_url:
                    raise ValueError("ERROR: Unable to find post URL.")

                if not post_url.startswith("http"):
                    post_url = f"https://krakenfiles.com{post_url}"

                # Find token
                token_input = soup.find("input", {"id": "dl-token"})
                if not token_input:
                    raise ValueError("ERROR: Unable to find token for download.")

                token = token_input.get("value")
                if not token:
                    raise ValueError("ERROR: Token value is empty.")

                return post_url, {"token": token}

    async def _get_download_url(self, post_url: str, data: dict) -> str:
        """Get download URL from form submission"""
        async with aiohttp.ClientSession() as session:
            async with session.post(post_url, data=data) as response:
                response.raise_for_status()
                json_data = await response.json()

                if "url" in json_data:
                    return json_data["url"]

                raise ValueError("Could not obtain download URL from response")

    async def _start(self):
        """Start download process"""
        try:
            await self.edit_text("Processing krakenfiles download link...")
            post_url, form_data = await self._extract_form_data(self._original_url)
            download_url = await self._get_download_url(post_url, form_data)

            # Update URL and use DirectDownload
            self._url = download_url
            await self.edit_text("Starting download...")
            await super()._start()

        except ValueError as e:
            await self.edit_text(f"Download failed!❌\n{str(e)}")
            raise
        except Exception as e:
            await self.edit_text(
                f"Download failed!❌\nAn error occurred: {str(e)}\n" "Please check your URL and try again."
            )
            raise


async def krakenfiles_download(bot, bot_msg, url: str):
    """KrakenFiles download entry point"""
    downloader = KrakenFilesDownload(bot, bot_msg, url)
    await downloader.start()
