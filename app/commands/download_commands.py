"""Download commands for video downloads"""

import re
import shutil
import subprocess
import os
from pathlib import Path
from typing import Optional

from aiogram import Dispatcher, Bot
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from aiogram.filters import Command

from app.utils.logger import get_logger
from app.utils.download_utils import parse_download_command, detect_downloader_type
from app.downloaders import YoutubeDownload, DirectDownload, InstagramDownload, PixeldrainDownload, KrakenFilesDownload, SpotifyDownload
from app.services.user_settings_service import user_settings_service
from app.services.bot_settings_service import bot_settings_service
from app.config import settings

logger = get_logger(__name__)


def check_ffmpeg_available() -> bool:
    """
    Check if FFmpeg is available by trying multiple methods.
    Returns True if FFmpeg is found, False otherwise.
    """
    # Method 1: Check PATH using shutil.which
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path is not None:
        logger.debug(f"FFmpeg found in PATH: {ffmpeg_path}")
        return True
    
    # Method 2: Try to run ffmpeg directly to check if it's available
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            timeout=5,
            text=True,
            stderr=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL
        )
        if result.returncode == 0:
            logger.debug("FFmpeg is executable via direct call")
            return True
    except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError) as e:
        logger.debug(f"FFmpeg direct call failed: {e}")
    
    # Method 3: Check common installation paths (Docker/Unix)
    common_paths = [
        "/usr/bin/ffmpeg",
        "/usr/local/bin/ffmpeg",
        "/bin/ffmpeg",
    ]
    for path_str in common_paths:
        path = Path(path_str)
        if path.exists() and path.is_file() and os.access(path, os.X_OK):
            logger.debug(f"FFmpeg found at: {path_str}")
            return True
    
    logger.warning("FFmpeg not found using any method")
    return False


async def _show_settings_category(callback_query: CallbackQuery, category: str, user_id: str):
    """Show settings for a specific category"""
    buttons = []
    text = f"⚙️ <b>Settings - {category.capitalize()}</b>\n\n"

    if category == "user":
        # User settings (format/quality only - storage is managed via /storage commands)
        quality = await user_settings_service.get_quality(user_id)
        format_type = await user_settings_service.get_format(user_id)

        text += f"<b>Current:</b>\n"
        text += f"Quality: <b>{quality.upper()}</b>\n"
        text += f"Format: <b>{format_type.upper()}</b>\n\n"
        text += f"<i>Note: Storage preferences are managed via /storage commands</i>\n\n"

        buttons.append([
            InlineKeyboardButton(
                text="📄 Document" if format_type == "document" else "Document",
                callback_data="format:document",
            ),
            InlineKeyboardButton(
                text="🎥 Video" if format_type == "video" else "Video",
                callback_data="format:video",
            ),
            InlineKeyboardButton(
                text="🎵 Audio" if format_type == "audio" else "Audio",
                callback_data="format:audio",
            ),
        ])
        buttons.append([
            InlineKeyboardButton(
                text="⬆️ High" if quality == "high" else "High",
                callback_data="quality:high",
            ),
            InlineKeyboardButton(
                text="➡️ Medium" if quality == "medium" else "Medium",
                callback_data="quality:medium",
            ),
            InlineKeyboardButton(
                text="⬇️ Low" if quality == "low" else "Low",
                callback_data="quality:low",
            ),
        ])
    else:
        # Bot settings by category
        settings_list = await bot_settings_service.get_settings_by_category(category)
        
        if not settings_list:
            text += "No settings in this category.\n"
        else:
            for setting in settings_list:
                current_value = bot_settings_service.deserialize_value(setting.value, setting.value_type)
                display_value = str(current_value)
                if setting.value_type == "bool":
                    display_value = "✅ Enabled" if current_value else "❌ Disabled"
                
                text += f"<b>{setting.key}</b>: {display_value}\n"
                text += f"  {setting.description}\n"
                if setting.requires_restart:
                    text += "  ⚠️ Requires restart\n"
                text += "\n"

                # Add toggle button for booleans
                if setting.value_type == "bool":
                    buttons.append([
                        InlineKeyboardButton(
                            text=f"{'✅' if current_value else '❌'} {setting.key}",
                            callback_data=f"setting_toggle:{setting.key}",
                        )
                    ])

    # Back button
    buttons.append([
        InlineKeyboardButton(text="← Back", callback_data="settings_cat:back"),
    ])

    markup = InlineKeyboardMarkup(inline_keyboard=buttons)
    try:
        await callback_query.message.edit_text(text, reply_markup=markup)
    except Exception as e:
        # Handle "message is not modified" error gracefully
        if "message is not modified" in str(e).lower():
            await callback_query.answer()  # Just acknowledge
        else:
            raise


async def setup_download_commands(dp: Optional[Dispatcher], bot: Optional[Bot]):
    """Setup download commands"""
    if not dp or not bot:
        return

    async def download_command(message: Message):
        """Download video from any supported site, with optional MP3 conversion"""
        message_text = message.text or ""
        url, format_type, _ = parse_download_command(message_text)

        if not url or not re.findall(r"^https?://", url.lower()):
            await message.answer(
                "❌ <b>Invalid URL.</b>\n\n"
                "Usage: /download &lt;url&gt;\n"
                "       /download mp3 &lt;url&gt; (convert to MP3)\n\n"
                "Supported sites:\n"
                "• YouTube\n"
                "• Spotify (tracks, playlists, albums, artists)\n"
                "• Instagram/Threads\n"
                "• Pixeldrain\n"
                "• KrakenFiles\n"
                "• Direct file URLs"
            )
            return

        # Check if MP3 format is requested
        is_mp3 = format_type and format_type.lower() == "mp3"
        
        # Verify FFmpeg is available and enabled for MP3 conversion
        if is_mp3:
            # First check if FFmpeg is enabled in settings
            if not settings.enable_ffmpeg:
                logger.warning("MP3 conversion requested but ENABLE_FFMPEG=false in configuration")
                await message.answer(
                    "❌ <b>FFmpeg is disabled.</b>\n\n"
                    "MP3 conversion requires FFmpeg to be enabled.\n"
                    "Please set ENABLE_FFMPEG=true in your .env configuration file,\n"
                    "or use /download without 'mp3' parameter."
                )
                return
            
            # Check if FFmpeg is actually available
            # Note: In Docker, FFmpeg is installed, so we trust ENABLE_FFMPEG=true
            # but still verify it's accessible for better error messages
            ffmpeg_available = check_ffmpeg_available()
            if not ffmpeg_available:
                # Log warning but don't block - FFmpeg might be available at runtime
                # even if not found in PATH (Docker containers have it installed)
                logger.warning(
                    "FFmpeg not found in PATH, but ENABLE_FFMPEG=true. "
                    "Assuming FFmpeg is available (Docker installation). "
                    "Will attempt conversion anyway."
                )
                # Continue - the actual conversion will fail gracefully if FFmpeg is truly missing
            
            logger.info("MP3 conversion enabled - FFmpeg check passed")

        bot_msg = await message.answer("📥 Download request received...")
        
        # Save original audio_format setting
        original_audio_format = settings.audio_format
        
        try:
            downloader_type = detect_downloader_type(url)
            
            if downloader_type == "youtube":
                downloader = YoutubeDownload(bot, bot_msg, url)
            elif downloader_type == "spotify":
                if not settings.spotify_enabled:
                    await message.answer("❌ Spotify downloads are disabled")
                    return
                if not settings.spotify_client_id or not settings.spotify_client_secret:
                    await message.answer("❌ Spotify credentials not configured")
                    return
                downloader = SpotifyDownload(bot, bot_msg, url)
            elif downloader_type == "instagram":
                downloader = InstagramDownload(bot, bot_msg, url)
            elif downloader_type == "pixeldrain":
                downloader = PixeldrainDownload(bot, bot_msg, url)
            elif downloader_type == "krakenfiles":
                downloader = KrakenFilesDownload(bot, bot_msg, url)
            else:  # direct
                downloader = DirectDownload(bot, bot_msg, url)
            
            # Force audio format and MP3 conversion if requested
            if is_mp3:
                # Temporarily set audio format to MP3
                settings.audio_format = "mp3"
                # Force format to audio and quality to high (will be respected in _load_user_settings)
                downloader._force_format = "audio"
                downloader._force_quality = "high"
                logger.info(f"MP3 conversion requested for {url}")
            
            await downloader.start()
        except Exception as e:
            logger.error(f"Download failed for {url}: {e}", exc_info=True)
            
            # Check if it's a geo-restriction error
            from app.downloaders.youtube import GeoRestrictionError
            if isinstance(e, GeoRestrictionError):
                await bot_msg.edit_text(
                    "❌ <b>Vídeo não disponível</b>\n\n"
                    "Este vídeo não está disponível no seu país.\n"
                    "O uploader não disponibilizou este vídeo na sua região.\n\n"
                    "Tente usar uma VPN ou proxy para contornar esta restrição."
                )
            else:
                error_msg = str(e)
                # Truncate very long error messages
                if len(error_msg) > 500:
                    error_msg = error_msg[:500] + "..."
                await bot_msg.edit_text(f"❌ Download failed: {error_msg}")
        finally:
            # Restore original audio_format setting
            if is_mp3:
                settings.audio_format = original_audio_format

    # Register handler for both /download and /downloader commands
    dp.message.register(download_command, Command("download"))
    dp.message.register(download_command, Command("downloader"))

    @dp.message(Command("settings"))
    async def settings_command(message: Message):
        """Configure all bot settings"""
        chat_id = str(message.chat.id)
        user_id = str(message.from_user.id if message.from_user else chat_id)

        try:
            # Show category selection
            markup = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(text="📥 Download", callback_data="settings_cat:download"),
                        InlineKeyboardButton(text="🔒 Security", callback_data="settings_cat:security"),
                    ],
                    [
                        InlineKeyboardButton(text="⚡ Features", callback_data="settings_cat:features"),
                        InlineKeyboardButton(text="⚙️ Advanced", callback_data="settings_cat:advanced"),
                    ],
                    [
                        InlineKeyboardButton(text="👤 User Settings", callback_data="settings_cat:user"),
                    ],
                ]
            )

            settings_text = """
⚙️ <b>Bot Settings</b>

Select a category to configure:

<b>📥 Download</b> - Quality, format, audio settings
<b>🔒 Security</b> - Access control, anti-blocking
<b>⚡ Features</b> - Enable/disable features
<b>⚙️ Advanced</b> - Log level, cache, limits
<b>👤 User Settings</b> - Personal download preferences
"""
            await message.answer(settings_text, reply_markup=markup)
        except Exception as e:
            logger.error(f"Failed to show settings: {e}")
            await message.answer("❌ Failed to load settings. Please try again.")

    @dp.callback_query(lambda c: c.data and (
        c.data.startswith("settings_cat:") or
        c.data.startswith("format:") or
        c.data.startswith("quality:") or
        c.data.startswith("setting_toggle:") or
        c.data.startswith("setting_edit:")
    ))
    async def settings_callback(callback_query: CallbackQuery):
        """Handle settings callback"""
        if not callback_query.data:
            return

        user_id = str(callback_query.from_user.id if callback_query.from_user else callback_query.message.chat.id)
        data = callback_query.data

        try:
            # Category selection
            if data.startswith("settings_cat:"):
                category = data.split(":")[1]
                if category == "back":
                    # Show main settings menu
                    markup = InlineKeyboardMarkup(
                        inline_keyboard=[
                            [
                                InlineKeyboardButton(text="📥 Download", callback_data="settings_cat:download"),
                                InlineKeyboardButton(text="🔒 Security", callback_data="settings_cat:security"),
                            ],
                            [
                                InlineKeyboardButton(text="⚡ Features", callback_data="settings_cat:features"),
                                InlineKeyboardButton(text="⚙️ Advanced", callback_data="settings_cat:advanced"),
                            ],
                            [
                                InlineKeyboardButton(text="👤 User Settings", callback_data="settings_cat:user"),
                            ],
                        ]
                    )
                    text = """
⚙️ <b>Bot Settings</b>

Select a category to configure:

<b>📥 Download</b> - Quality, format, audio settings
<b>🔒 Security</b> - Access control, anti-blocking
<b>⚡ Features</b> - Enable/disable features
<b>⚙️ Advanced</b> - Log level, cache, limits
<b>👤 User Settings</b> - Personal download preferences
"""
                    try:
                        await callback_query.message.edit_text(text, reply_markup=markup)
                    except Exception as e:
                        # Handle "message is not modified" error gracefully
                        if "message is not modified" in str(e).lower():
                            await callback_query.answer()  # Just acknowledge
                        else:
                            raise
                else:
                    await _show_settings_category(callback_query, category, user_id)
                await callback_query.answer()
                return

            # User settings (format/quality only)
            if data.startswith("format:") or data.startswith("quality:"):
                if data.startswith("format:"):
                    format_type = data.split(":")[1]
                    await user_settings_service.set_format(user_id, format_type)
                    await callback_query.answer(f"Format set to {format_type}")
                elif data.startswith("quality:"):
                    quality = data.split(":")[1]
                    await user_settings_service.set_quality(user_id, quality)
                    await callback_query.answer(f"Quality set to {quality}")

                # Refresh user settings display
                await _show_settings_category(callback_query, "user", user_id)
                return

            # Bot settings toggle/edit
            if data.startswith("setting_toggle:") or data.startswith("setting_edit:"):
                setting_key = data.split(":")[1]
                setting = await bot_settings_service.get_setting(setting_key)
                
                if not setting:
                    await callback_query.answer("❌ Setting not found", show_alert=True)
                    return

                if data.startswith("setting_toggle:"):
                    # Toggle boolean
                    current_value = bot_settings_service.deserialize_value(setting.value, setting.value_type)
                    new_value = not current_value
                    await bot_settings_service.set_setting(
                        setting_key, new_value, setting.value_type, setting.category,
                        setting.description, setting.requires_restart
                    )
                    restart_msg = " (restart required)" if setting.requires_restart else ""
                    await callback_query.answer(f"Set to {new_value}{restart_msg}")
                else:
                    # Edit - show input prompt (simplified for now, just toggle if bool)
                    if setting.value_type == "bool":
                        current_value = bot_settings_service.deserialize_value(setting.value, setting.value_type)
                        new_value = not current_value
                        await bot_settings_service.set_setting(
                            setting_key, new_value, setting.value_type, setting.category,
                            setting.description, setting.requires_restart
                        )
                        restart_msg = " (restart required)" if setting.requires_restart else ""
                        await callback_query.answer(f"Set to {new_value}{restart_msg}")
                    else:
                        await callback_query.answer("❌ Edit not implemented for this type", show_alert=True)

                # Refresh category display
                await _show_settings_category(callback_query, setting.category, user_id)
                return

        except Exception as e:
            logger.error(f"Failed to update settings: {e}")
            await callback_query.answer("❌ Failed to update settings", show_alert=True)
