"""YouTube authentication provider for yt-dlp"""

import os
import shutil
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

from app.config import settings
from app.utils.logger import get_logger, sanitize_cookie_path

logger = get_logger(__name__)


class YoutubeAuthProvider:
    """Manages YouTube authentication for yt-dlp (cookies, browser, PO Token)"""

    def __init__(self):
        """Initialize the auth provider"""
        self.auth_mode = getattr(settings, "ytdlp_auth_mode", "both").lower()
        self.cookies_file = getattr(settings, "ytdlp_cookies_file", None)
        self.cookies_from_browser = getattr(settings, "ytdlp_cookies_from_browser", None)
        self.browser_profile = getattr(settings, "ytdlp_browser_profile", "default")
        self.firefox_container = getattr(settings, "ytdlp_firefox_container", "none")
        self.po_token = getattr(settings, "ytdlp_po_token", None)
        self.chromium_path = getattr(settings, "ytdlp_chromium_path", "/usr/bin/chromium")
        self.enable_po_provider = getattr(settings, "ytdlp_enable_po_provider", False)
        
        # Backward compatibility: if old BROWSERS setting exists and new one doesn't, use it
        if not self.cookies_from_browser and hasattr(settings, "browsers") and settings.browsers:
            # Migrate old BROWSERS setting to new format
            browsers_list = [b.strip() for b in settings.browsers.split(",") if b.strip()]
            if browsers_list:
                self.cookies_from_browser = browsers_list[0]  # Use first browser
                logger.debug(f"Using legacy BROWSERS setting: {self.cookies_from_browser} (migrated to YTDLP_COOKIES_FROM_BROWSER)")
                # If auth_mode is not explicitly set (default is "both"), change to browser mode
                # Check if ytdlp_auth_mode was explicitly set in env (not just using default)
                ytdlp_auth_mode_env = os.getenv("YTDLP_AUTH_MODE")
                if not ytdlp_auth_mode_env:
                    # Not set in env, using default - can safely override for backward compat
                    self.auth_mode = "browser"

    def build_auth_opts(self, tempdir: Optional[str] = None) -> Dict[str, Any]:
        """
        Build authentication options for yt-dlp.

        Args:
            tempdir: Temporary directory path (for copying cookies file if needed)

        Returns:
            Dictionary with yt-dlp authentication options
        """
        opts: Dict[str, Any] = {}

        # Priority 1: cookies-from-browser (most reliable)
        if self.auth_mode in ("browser", "both"):
            browser_opts = self._build_browser_cookies()
            if browser_opts:
                opts.update(browser_opts)
                logger.debug(
                    f"Using cookies from browser: {self.cookies_from_browser} "
                    f"(profile: {self.browser_profile})"
                )

        # Priority 2: cookies file (fallback or if explicitly requested)
        if self.auth_mode in ("cookiefile", "both") or (
            self.auth_mode == "browser" and "cookiesfrombrowser" not in opts
        ):
            cookie_file_opts = self._build_cookie_file_opts(tempdir)
            if cookie_file_opts:
                # Only add if browser cookies weren't set, or if mode is "both"
                if "cookiesfrombrowser" not in opts or self.auth_mode == "both":
                    opts.update(cookie_file_opts)
                    cookie_path = cookie_file_opts.get('cookiefile')
                    logger.debug(f"Using cookies file: {sanitize_cookie_path(cookie_path)}")

        # Build extractor args (for PO Token and Chromium path)
        extractor_args_dict = self._build_extractor_args()
        if extractor_args_dict:
            opts["extractor_args"] = extractor_args_dict

        # Log final auth method
        if not opts.get("cookiesfrombrowser") and not opts.get("cookiefile"):
            logger.warning("No YouTube authentication configured - downloads may fail")

        return opts

    def _build_browser_cookies(self) -> Optional[Dict[str, Any]]:
        """Build cookies-from-browser options"""
        if not self.cookies_from_browser:
            return None

        browser = self.cookies_from_browser.strip().lower()

        # Build tuple format for yt-dlp
        if browser == "firefox" and self.firefox_container != "none":
            # Firefox with container: (browser, profile, container)
            cookies_tuple: Tuple[str, ...] = (
                browser,
                self.browser_profile,
                self.firefox_container,
            )
        elif self.browser_profile != "default":
            # Browser with custom profile: (browser, profile)
            cookies_tuple = (browser, self.browser_profile)
        else:
            # Browser with default profile: (browser,)
            cookies_tuple = (browser,)

        return {"cookiesfrombrowser": cookies_tuple}

    def _build_cookie_file_opts(self, tempdir: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Build cookie file options"""
        # Check configured path first
        cookie_paths = []
        if self.cookies_file:
            cookie_paths.append(self.cookies_file)

        # Add default paths (only absolute paths to avoid creating files in project root)
        cookie_paths.extend(
            [
                "/app/youtube-cookies.txt",
                "/secrets/youtube-cookies.txt",
            ]
        )

        for path in cookie_paths:
            if os.path.isfile(path) and os.path.getsize(path) > 100:
                # If tempdir is provided, copy to temp (yt-dlp may need to write)
                if tempdir:
                    temp_cookie_file = os.path.join(tempdir, "youtube-cookies.txt")
                    try:
                        shutil.copy2(path, temp_cookie_file)
                        return {"cookiefile": temp_cookie_file}
                    except Exception as e:
                        # Sanitize error message to avoid exposing cookie paths
                        error_msg = str(e)
                        if "cookie" in error_msg.lower() or any(kw in error_msg.lower() for kw in ["/secrets/", "/tmp/", "youtube-cookies"]):
                            error_msg = "Failed to copy cookies file to temp directory"
                        logger.warning(f"Failed to copy cookies file to temp: {error_msg}")
                        # Fallback to original path
                        return {"cookiefile": path}
                else:
                    return {"cookiefile": path}

        return None

    def _build_extractor_args(self) -> Optional[Dict[str, Any]]:
        """Build extractor args for PO Token and Chromium path"""
        extractor_args: Dict[str, Any] = {}

        # Only configure PO Token Provider if explicitly enabled or manual PO token is set
        should_use_po_provider = self.enable_po_provider or self.po_token

        if should_use_po_provider:
            # Check if Chromium path needs to be configured
            chromium_path = self.chromium_path
            if chromium_path and chromium_path != "/usr/bin/chromium":
                # Verify Chromium exists at specified path
                if os.path.isfile(chromium_path) and os.access(chromium_path, os.X_OK):
                    extractor_args["youtubepot-wpc"] = {"browser_path": chromium_path}
                    logger.debug(f"Configured Chromium path: {chromium_path}")
                else:
                    logger.warning(
                        f"Chromium not found at {chromium_path}, using default path"
                    )
            elif self.enable_po_provider:
                # PO Provider is enabled but using default Chromium path
                # yt-dlp-getpot-wpc will use default path automatically
                logger.debug("PO Token Provider enabled, using default Chromium path")
        else:
            # Explicitly log that PO Provider is disabled
            # This helps debug if yt-dlp-getpot-wpc is being activated automatically
            logger.debug("PO Token Provider disabled (YTDLP_ENABLE_PO_PROVIDER=false), using cookies only")
            # Ensure youtubepot-wpc is NOT in extractor_args when disabled
            # This prevents any accidental inclusion

        # PO Token manual (fallback, rarely needed)
        if self.po_token:
            # PO Token is passed via youtube extractor args
            if "youtube" not in extractor_args:
                extractor_args["youtube"] = {}
            # Format: po_token=TOKEN
            extractor_args["youtube"]["po_token"] = self.po_token
            logger.info("Using manual PO Token (fallback mode)")

        # Final verification: ensure youtubepot-wpc is not included when disabled
        if not should_use_po_provider and "youtubepot-wpc" in extractor_args:
            logger.warning("Removing youtubepot-wpc from extractor_args (PO Provider disabled)")
            extractor_args.pop("youtubepot-wpc", None)

        # Debug log: show what extractor_args will be returned
        if extractor_args:
            # Sanitize for logging (remove sensitive data)
            log_args = {}
            for key, value in extractor_args.items():
                if key == "youtube" and isinstance(value, dict) and "po_token" in value:
                    log_args[key] = {k: "[REDACTED]" if k == "po_token" else v for k, v in value.items()}
                else:
                    log_args[key] = value
            logger.debug(f"Built extractor_args: {log_args}")
        else:
            logger.debug("No extractor_args configured (PO Provider disabled, using cookies only)")

        return extractor_args if extractor_args else None

    def detect_cookie_errors(self, error_msg: str) -> bool:
        """
        Detect if error is related to invalid cookies.

        Args:
            error_msg: Error message from yt-dlp

        Returns:
            True if error is cookie-related
        """
        cookie_error_indicators = [
            "cookies are no longer valid",
            "cookies have likely been rotated",
            "Sign in to confirm you're not a bot",
            "authentication required",
            "cookies expired",
        ]
        error_lower = error_msg.lower()
        return any(indicator in error_lower for indicator in cookie_error_indicators)
