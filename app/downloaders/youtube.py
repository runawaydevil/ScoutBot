"""YouTube downloader using yt-dlp"""

import asyncio
import copy
import os
import random
import shutil
from pathlib import Path
from typing import List, Optional
from urllib.parse import urlparse

import yt_dlp

from app.config import settings
from app.utils.logger import get_logger
from app.utils.download_utils import is_youtube
from app.utils.rate_limiter import rate_limiter
from app.utils.circuit_breaker import circuit_breaker
from app.utils.ytdlp_config import build_ytdlp_common_opts
from app.utils.youtube_auth import YoutubeAuthProvider
from app.utils.logger import sanitize_cookie_path
from app.downloaders.base import BaseDownloader

logger = get_logger(__name__)

# Verify required tools at module level
NODE_AVAILABLE = shutil.which("node") is not None
if not NODE_AVAILABLE:
    logger.warning("Node.js not found in PATH - some YouTube formats may be unavailable")

# Available YouTube clients for rotation
YOUTUBE_CLIENTS = [
    "web",
    "ios",
    "android",
    "android_sdkless",
    "web_safari",
    "tv",
    "tv_downgraded",
]


def match_filter(info_dict):
    """Filter out live videos"""
    if info_dict.get("is_live"):
        raise NotImplementedError("Skipping live video")
    return None


class GeoRestrictionError(Exception):
    """Exception raised when video is geo-restricted and cannot be downloaded"""
    pass


class YoutubeDownload(BaseDownloader):
    """YouTube downloader using yt-dlp"""

    @staticmethod
    def get_format(m: int) -> List[str]:
        """Get format strings for specific height"""
        return [
            f"bestvideo[ext=mp4][height={m}][protocol!*=sabr]+bestaudio[ext=m4a]",
            f"bestvideo[ext=mp4][height={m}]+bestaudio[ext=m4a]",
            f"bestvideo[vcodec^=avc][height={m}][protocol!*=sabr]+bestaudio[acodec^=mp4a]/best[vcodec^=avc]/best",
            f"bestvideo[vcodec^=avc][height={m}]+bestaudio[acodec^=mp4a]/best[vcodec^=avc]/best",
        ]

    def _setup_formats(self) -> Optional[List[str]]:
        """Setup download formats based on user quality and format settings"""
        if not is_youtube(self._url):
            return [None]

        quality = self._quality
        format_type = self._format

        formats = []
        defaults = [
            # webm, vp9 and av01 are not streamable on telegram, so we'll extract only mp4
            # Avoid SABR streaming formats when possible
            "bestvideo[ext=mp4][vcodec!*=av01][vcodec!*=vp09][protocol!*=sabr]+bestaudio[ext=m4a]/bestvideo+bestaudio",
            "bestvideo[ext=mp4][vcodec!*=av01][vcodec!*=vp09]+bestaudio[ext=m4a]/bestvideo+bestaudio",
            "bestvideo[vcodec^=avc][protocol!*=sabr]+bestaudio[acodec^=mp4a]/best[vcodec^=avc]/best",
            "bestvideo[vcodec^=avc]+bestaudio[acodec^=mp4a]/best[vcodec^=avc]/best",
            None,
        ]
        audio = settings.audio_format or "m4a"
        
        # Optimized audio format selection: try simpler formats first
        # Start with bestaudio (no restrictions) for better compatibility
        if audio.lower() == "mp3":
            audio_formats = [
                "bestaudio",  # Try best audio first (most compatible, no restrictions)
                "bestaudio[ext=mp3]",  # Then try MP3 directly if available
                "bestaudio[ext=m4a]",  # Fallback to M4A (will be converted to MP3)
                "bestaudio[ext=webm]",  # Fallback to WebM (will be converted to MP3)
                "best[height<=480]/best",  # Fallback: get video and extract audio if pure audio fails
            ]
        else:
            audio_formats = [
                "bestaudio",  # Try best audio first (most compatible)
                f"bestaudio[ext={audio}]",  # Then try specific format
                "best[height<=480]/best",  # Fallback: get video and extract audio if pure audio fails
            ]
        
        maps = {
            "high-audio": audio_formats,
            "high-video": defaults,
            "high-document": defaults,
            "medium-audio": audio_formats,
            "medium-video": self.get_format(720),
            "medium-document": self.get_format(720),
            "low-audio": audio_formats,
            "low-video": self.get_format(480),
            "low-document": self.get_format(480),
            "custom-audio": audio_formats,
            "custom-video": [],
            "custom-document": [],
        }

        if quality == "custom":
            # TODO: Not supported yet - would need interactive format selection
            logger.warning("Custom quality not yet supported, using high quality")
            quality = "high"

        formats.extend(maps.get(f"{quality}-{format_type}", defaults))
        # Extend default formats if not high*
        if quality != "high":
            formats.extend(defaults)

        return formats

    def _is_geo_restriction_error(self, error_msg: str) -> bool:
        """Check if error is due to geo-restriction"""
        geo_indicators = [
            "not made this video available in your country",
            "not available in your country",
            "video is not available",
            "geo-restricted",
            "geographic restrictions",
            "uploader has not made this video available",
        ]
        return any(indicator.lower() in error_msg.lower() for indicator in geo_indicators)

    def _build_base_ydl_opts(self) -> dict:
        """Build base yt-dlp options using unified configuration"""
        output = Path(self._tempdir.name, "%(title).70s.%(ext)s").as_posix()
        
        # Start with unified common options
        ydl_opts = build_ytdlp_common_opts(tempdir=Path(self._tempdir.name))
        
        # Add YouTube-specific options
        ydl_opts.update({
            "progress_hooks": [lambda d: self.download_hook(d)],
            "outtmpl": output,
            "restrictfilenames": False,
            "quiet": True,
            "no_warnings": False,  # Keep warnings to detect issues, but reduce verbosity
            "match_filter": match_filter,
            "buffersize": 4194304,
            "embed_metadata": True,
            "embed_thumbnail": True,
            "writethumbnail": False,
            "http_chunk_size": 10485760,  # 10MB chunks for smoother downloads
            "ignoreerrors": False,  # Keep to detect real problems
        })
        
        # Add JavaScript runtime if available
        if NODE_AVAILABLE:
            # yt-dlp expects js_runtimes as a dict: {runtime: {config}}
            # Empty dict allows yt-dlp to find node in PATH automatically
            ydl_opts["js_runtimes"] = {"node": {}}
            logger.debug("Node.js detected, enabling JavaScript runtime for yt-dlp")
        else:
            logger.warning("Node.js not found, some YouTube formats may be unavailable")

        # Authentication is already handled by build_ytdlp_common_opts() for YouTube URLs
        # But we need to detect cookie errors for better logging
        if is_youtube(self._url):
            # Log which auth method is being used
            auth_provider = YoutubeAuthProvider()
            if ydl_opts.get("cookiesfrombrowser"):
                logger.debug("YouTube authentication: using cookies from browser")
            elif ydl_opts.get("cookiefile"):
                logger.debug(f"YouTube authentication: using cookies file: {sanitize_cookie_path(ydl_opts.get('cookiefile'))}")
            else:
                logger.warning("YouTube authentication: no cookies configured - downloads may fail")

        return ydl_opts

    def _build_extractor_args(self, player_clients: Optional[List[str]] = None) -> List[str]:
        """Build extractor args with optional player clients"""
        extractor_args = []
        
        # Add geo_bypass to attempt bypassing geo-restrictions
        # geo_bypass=True enables automatic geo-bypass
        # geo_bypass_country can specify a country code (e.g., "BR", "AR", "MX")
        extractor_args.append("geo_bypass=True")
        # Try to bypass using a country from the allowed list (Latin America)
        # The yt-dlp will try to use a proxy-like approach internally
        extractor_args.append("geo_bypass_country=BR")
        
        # Use specified player clients or default rotation
        if player_clients:
            client_string = ",".join(player_clients)
            extractor_args.append(f"player_client={client_string}")
            logger.debug(f"Using YouTube clients: {client_string}")
        elif settings.youtube_rotate_clients:
            clients = [c.strip() for c in settings.youtube_player_clients.split(",") if c.strip()]
            
            # Filter out 'web' if possible, prioritize mobile clients
            mobile_clients = [c for c in clients if c in ["ios", "android", "tv_embedded", "tv"]]
            
            if mobile_clients:
                sample_size = min(3, len(mobile_clients))
                selected = random.sample(mobile_clients, sample_size) if mobile_clients else []
            else:
                # Fallback to all clients if no mobile clients available
                sample_size = min(3, len(clients))
                selected = random.sample(clients, sample_size) if clients else []
            
            if selected:
                client_string = ",".join(selected)
                extractor_args.append(f"player_client={client_string}")
                logger.debug(f"Using YouTube clients: {client_string} (mobile clients prioritized)")
        
        # Skip webpage client which has more detection
        extractor_args.append("player_skip=webpage")
        
        return extractor_args

    async def _try_download_with_clients(
        self, 
        ydl_opts: dict, 
        formats: List[str], 
        player_clients_list: List[List[str]]
    ) -> Optional[List[Path]]:
        """Try downloading with different player clients"""
        for client_group in player_clients_list:
            # Build extractor args with this client group
            extractor_args = self._build_extractor_args(client_group)
            # Make a deep copy to avoid modifying the original dict
            ydl_opts_copy = copy.deepcopy(ydl_opts)
            ydl_opts_copy["extractor_args"] = {"youtube": extractor_args}
            
            for fmt in formats:
                ydl_opts_copy["format"] = fmt
                logger.debug(f"Trying format: {fmt} with clients: {','.join(client_group)}")
                
                try:
                    with yt_dlp.YoutubeDL(ydl_opts_copy) as ydl:
                        ydl.download([self._url])
                    all_files = list(Path(self._tempdir.name).glob("*"))
                    # Filter out temporary files (cookies, metadata, thumbnails, etc.)
                    files = self._filter_downloaded_files(all_files)
                    if files:
                        logger.debug(f"Successfully downloaded with format: {fmt} and clients: {','.join(client_group)}")
                        return files
                except Exception as e:
                    error_msg = str(e)
                    logger.debug(f"Format {fmt} with clients {','.join(client_group)} failed: {error_msg}")
                    
                    # Check for geo-restriction - if detected, stop trying immediately
                    if self._is_geo_restriction_error(error_msg):
                        logger.warning(f"Geo-restriction detected with client {','.join(client_group)}. Stopping attempts.")
                        raise GeoRestrictionError(
                            "Este vídeo não está disponível no seu país. "
                            "O uploader não disponibilizou este vídeo na sua região."
                        )
                    
                    # Detect cookie errors and log alert
                    auth_provider = YoutubeAuthProvider()
                    if auth_provider.detect_cookie_errors(error_msg):
                        logger.error(
                            f"⚠️ YouTube cookie authentication error detected: {error_msg[:200]}\n"
                            f"Cookies may be invalid or rotated. Please refresh cookies using the method configured in YTDLP_AUTH_MODE."
                        )
                    continue
        
        return None

    async def _download(self, formats: Optional[List[str]] = None) -> List[Path]:
        """Download video using yt-dlp"""
        if formats is None:
            formats = self._setup_formats()

        # Extract domain for rate limiting
        parsed = urlparse(self._url)
        domain = parsed.netloc or parsed.path.split("/")[0]

        # Check circuit breaker
        if not circuit_breaker.should_allow_request(self._url):
            time_until_retry = circuit_breaker.get_time_until_retry(self._url)
            raise ValueError(f"Circuit breaker open for {domain}. Retry in {time_until_retry:.0f}s")

        # Apply rate limiting
        await rate_limiter.wait_if_needed(domain)

        # Add sleep interval before download (anti-blocking)
        if settings.youtube_sleep_interval > 0:
            sleep_time = random.uniform(
                settings.youtube_sleep_interval,
                settings.youtube_max_sleep_interval
            )
            logger.debug(f"Sleeping {sleep_time:.1f}s before download (anti-blocking)")
            await asyncio.sleep(sleep_time)

        # Build base yt-dlp options
        ydl_opts = self._build_base_ydl_opts()
        
        # Setup extractor args for YouTube only
        if is_youtube(self._url):
            extractor_args = self._build_extractor_args()
            if extractor_args:
                ydl_opts["extractor_args"] = {"youtube": extractor_args}

        if self._url.startswith("https://drive.google.com"):
            # Always use the `source` format for Google Drive URLs
            formats = ["source"] + formats

        files = None
        geo_restriction_detected = False
        
        try:
            # Try to get format info first to check for SABR streaming issues
            format_info = None
            try:
                # Disable retries for format info extraction to avoid repeated geo-restriction errors
                format_opts = {**ydl_opts, "quiet": True, "no_warnings": False, "retries": 0, "extractor_retries": 0}
                with yt_dlp.YoutubeDL(format_opts) as ydl:
                    info = ydl.extract_info(self._url, download=False)
                    format_info = info.get("formats", [])
                    if format_info:
                        # Log available formats for debugging
                        available_formats = [f.get("format_id", "unknown") for f in format_info]
                        logger.debug(f"Available formats: {len(available_formats)} formats found")
                        # Check for SABR streaming formats
                        sabr_formats = [f for f in format_info if "SABR" in str(f.get("format_note", "")).upper() or "sabr" in str(f.get("format_id", "")).lower()]
                        if sabr_formats:
                            logger.info(f"Found {len(sabr_formats)} SABR streaming formats (may have missing URLs)")
            except Exception as e:
                error_msg = str(e)
                if self._is_geo_restriction_error(error_msg):
                    geo_restriction_detected = True
                    logger.warning("Geo-restriction detected during format info extraction. Will try different player clients.")
                    # Don't continue with normal download - go straight to client rotation
                    # But first disable retries to avoid repeated errors
                    ydl_opts["retries"] = 0
                    ydl_opts["fragment_retries"] = 0
                    ydl_opts["extractor_retries"] = 0
                else:
                    logger.debug(f"Could not extract format info: {e}")
            
            # Try normal download first
            for fmt in formats:
                ydl_opts["format"] = fmt
                logger.debug(f"Trying format: {fmt}")
                try:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.download([self._url])
                    all_files = list(Path(self._tempdir.name).glob("*"))
                    # Filter out temporary files (cookies, metadata, thumbnails, etc.)
                    files = self._filter_downloaded_files(all_files)
                    if files:
                        # Record success
                        rate_limiter.record_success(domain)
                        circuit_breaker.record_success(self._url)
                        logger.debug(f"Successfully downloaded with format: {fmt}")
                        break
                except Exception as e:
                    error_msg = str(e)
                    
                    # Check for geo-restriction error
                    if self._is_geo_restriction_error(error_msg):
                        geo_restriction_detected = True
                        logger.warning(f"Geo-restriction detected with format {fmt}. Will try different player clients.")
                        # Disable retries to avoid repeated errors
                        ydl_opts["retries"] = 0
                        ydl_opts["fragment_retries"] = 0
                        ydl_opts["extractor_retries"] = 0
                        # Don't break - continue to try other formats first, then try client rotation
                        continue
                    
                    # Intelligent error detection and handling
                    if "cookies are no longer valid" in error_msg or "cookies have likely been rotated" in error_msg:
                        logger.warning(f"Format {fmt} failed: Cookies expired/rotated. Consider updating cookies or configuring YTDLP_AUTH_MODE/YTDLP_COOKIES_FROM_BROWSER in .env")
                        # Don't continue trying other formats if cookies are invalid - they'll all fail
                        if formats and fmt == formats[0]:  # Only skip if this is the first format
                            logger.error("Cookies are invalid. Please update youtube-cookies.txt or configure YTDLP_AUTH_MODE/YTDLP_COOKIES_FROM_BROWSER in .env")
                            break
                    elif "Sign in to confirm you're not a bot" in error_msg:
                        logger.warning(f"Format {fmt} failed: Bot detection triggered. Trying next format with different client...")
                        # Continue trying - might work with different format/client combination
                    elif "SABR" in error_msg or "format" in error_msg.lower() or "url" in error_msg.lower():
                        logger.warning(f"Format {fmt} failed (possibly SABR streaming issue): {e}")
                    else:
                        logger.warning(f"Failed to download with format {fmt}: {e}")
                    continue

            # If geo-restriction was detected, try different player clients (only once)
            if geo_restriction_detected and not files:
                logger.info("Attempting geo-restriction bypass with different player clients...")
                
                # Disable retries for geo-restriction attempts to avoid repeated errors
                ydl_opts_geo = copy.deepcopy(ydl_opts)
                ydl_opts_geo["retries"] = 0
                ydl_opts_geo["fragment_retries"] = 0
                ydl_opts_geo["extractor_retries"] = 0
                
                # List of client combinations to try (prioritize mobile clients)
                client_combinations = [
                    ["ios"],  # Try iOS first (often has less geo-restriction)
                    ["android"],  # Then Android
                    ["tv_embedded"],  # TV embedded
                    ["tv"],  # TV
                    ["ios", "android"],  # Combined mobile
                    ["web"],  # Web as last resort
                ]
                
                files = await self._try_download_with_clients(ydl_opts_geo, formats, client_combinations)
                
                if files:
                    logger.info("Successfully bypassed geo-restriction with alternative player client")
                    rate_limiter.record_success(domain)
                    circuit_breaker.record_success(self._url)
                else:
                    # All attempts failed - this is a definitive geo-restriction
                    logger.warning(f"Video is geo-restricted and cannot be downloaded: {self._url}")
                    rate_limiter.record_failure(domain, 0)
                    circuit_breaker.record_failure(self._url)
                    raise GeoRestrictionError(
                        "Este vídeo não está disponível no seu país. "
                        "O uploader não disponibilizou este vídeo na sua região."
                    )

            if not files:
                # Record failure
                rate_limiter.record_failure(domain, 0)
                circuit_breaker.record_failure(self._url)
                raise ValueError(f"Failed to download {self._url} with any available format")
        except Exception as e:
            # Record failure
            rate_limiter.record_failure(domain, 0)
            circuit_breaker.record_failure(self._url)
            raise

        return files

    async def _start(self):
        """Start download and upload"""
        default_formats = self._setup_formats()
        
        files = await self._download(default_formats)
        await self._upload(files=files)
