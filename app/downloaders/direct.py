"""Direct downloader using aria2 or requests"""

import asyncio
import re
import subprocess
from pathlib import Path
from uuid import uuid4
from typing import List
from urllib.parse import urlparse

import aiohttp
import filetype

from app.config import settings
from app.utils.logger import get_logger
from app.utils.session_manager import session_manager
from app.utils.rate_limiter import rate_limiter
from app.utils.circuit_breaker import circuit_breaker
from app.downloaders.base import BaseDownloader

logger = get_logger(__name__)


class DirectDownload(BaseDownloader):
    """Direct downloader using aria2 or aiohttp"""

    def _setup_formats(self) -> None:
        """Direct download doesn't need to setup formats"""
        pass

    def _parse_size(self, size_str: str) -> int:
        """Parse size string to bytes"""
        units = {
            "B": 1,
            "K": 1024,
            "KB": 1024,
            "KIB": 1024,
            "M": 1024**2,
            "MB": 1024**2,
            "MIB": 1024**2,
            "G": 1024**3,
            "GB": 1024**3,
            "GIB": 1024**3,
            "T": 1024**4,
            "TB": 1024**4,
            "TIB": 1024**4,
        }
        match = re.match(r"([\d.]+)([A-Za-z]*)", size_str.replace("i", "").upper())
        if match:
            number, unit = match.groups()
            unit = unit or "B"
            return int(float(number) * units.get(unit, 1))
        return 0

    def _parse_progress(self, line: str) -> dict | None:
        """Parse aria2 progress line"""
        if "Download complete:" in line or "(OK):download completed" in line:
            return {"status": "complete"}

        progress_match = re.search(
            r'\[#\w+\s+(?P<progress>[\d.]+[KMGTP]?iB)/(?P<total>[\d.]+[KMGTP]?iB)\(.*?\)\s+CN:\d+\s+DL:(?P<speed>[\d.]+[KMGTP]?iB)\s+ETA:(?P<eta>[\dhms]+)',
            line,
        )

        if progress_match:
            return {
                "status": "downloading",
                "downloaded_bytes": self._parse_size(progress_match.group("progress")),
                "total_bytes": self._parse_size(progress_match.group("total")),
                "_speed_str": f"{progress_match.group('speed')}/s",
                "_eta_str": progress_match.group("eta"),
            }

        return None

    async def _aria2_download(self) -> List[Path]:
        """Download using aria2"""
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"
        process = None
        try:
            await self.edit_text("Aria2 download starting...")
            temp_dir = self._tempdir.name
            command = [
                "aria2c",
                "--max-tries=3",
                "--max-concurrent-downloads=8",
                "--max-connection-per-server=16",
                "--split=16",
                "--summary-interval=1",
                "--console-log-level=notice",
                "--show-console-readout=true",
                "--quiet=false",
                "--human-readable=true",
                f"--user-agent={ua}",
                "-d",
                temp_dir,
                self._url,
            ]

            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            while True:
                line = await process.stdout.readline()
                if not line:
                    if process.returncode is not None:
                        break
                    await asyncio.sleep(0.1)
                    continue

                line_str = line.decode("utf-8", errors="ignore")
                progress = self._parse_progress(line_str)
                if progress:
                    self.download_hook(progress)
                elif "Download complete:" in line_str:
                    self.download_hook({"status": "complete"})

            await process.wait()
            if process.returncode != 0:
                stderr = await process.stderr.read()
                raise subprocess.CalledProcessError(
                    process.returncode, command, stderr.decode("utf-8", errors="ignore")
                )

            # Find downloaded file
            files = list(Path(temp_dir).glob("*"))
            files = [f for f in files if f.is_file()]
            if not files:
                raise FileNotFoundError(f"No files found in {temp_dir}")

            logger.info(f"Successfully downloaded file: {files[0]}")
            return files

        except asyncio.TimeoutError:
            error_msg = "Download timed out after 5 minutes."
            logger.error(error_msg)
            await self.edit_text(f"Download failed!❌\n\n{error_msg}")
            return []
        except Exception as e:
            logger.error(f"Aria2 download failed: {e}")
            await self.edit_text(f"Download failed!❌\n\n`{e}`")
            return []
        finally:
            if process:
                try:
                    process.terminate()
                    await process.wait()
                except Exception:
                    pass

    async def _requests_download(self) -> List[Path]:
        """Download using aiohttp"""
        logger.info(f"aiohttp download with url {self._url}")

        # Extract domain for session management
        parsed = urlparse(self._url)
        domain = parsed.netloc or parsed.path.split("/")[0]

        # Get session from session manager
        session = await session_manager.get_session(domain)

        async with session.get(self._url) as response:
            response.raise_for_status()
            file = Path(self._tempdir.name) / uuid4().hex

            downloaded = 0
            total = int(response.headers.get("content-length", 0))

            with open(file, "wb") as f:
                async for chunk in response.content.iter_chunked(8192):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total > 0:
                        self.download_hook(
                            {
                                "status": "downloading",
                                "downloaded_bytes": downloaded,
                                "total_bytes": total,
                                "_speed_str": "N/A",
                                "_eta_str": "N/A",
                            }
                        )

            # Guess extension
            ext = filetype.guess_extension(file)
            if ext:
                new_name = file.with_suffix(f".{ext}")
                file.rename(new_name)
                return [new_name]

            return [file]

    async def _download(self, formats=None) -> List[Path]:
        """Download file"""
        # Extract domain for rate limiting
        parsed = urlparse(self._url)
        domain = parsed.netloc or parsed.path.split("/")[0]

        # Check circuit breaker
        if not circuit_breaker.should_allow_request(self._url):
            time_until_retry = circuit_breaker.get_time_until_retry(self._url)
            raise ValueError(f"Circuit breaker open for {domain}. Retry in {time_until_retry:.0f}s")

        # Apply rate limiting
        await rate_limiter.wait_if_needed(domain)

        try:
            if settings.enable_aria2:
                files = await self._aria2_download()
            else:
                files = await self._requests_download()

            if files:
                # Record success
                rate_limiter.record_success(domain)
                circuit_breaker.record_success(self._url)
            else:
                # Record failure
                rate_limiter.record_failure(domain, 0)
                circuit_breaker.record_failure(self._url)

            return files
        except Exception as e:
            # Record failure
            rate_limiter.record_failure(domain, 0)
            circuit_breaker.record_failure(self._url)
            raise

    async def _start(self):
        """Start download and upload"""
        downloaded_files = await self._download()
        if not downloaded_files:
            raise ValueError("No files downloaded")
        await self._upload(files=downloaded_files)
