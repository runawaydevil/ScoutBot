"""Inline keyboard callback handlers"""

from aiogram import Bot, Dispatcher
from aiogram.types import CallbackQuery

from app.utils.logger import get_logger
from app.utils.download_utils import detect_downloader_type
from app.downloaders import YoutubeDownload, DirectDownload, InstagramDownload, PixeldrainDownload, KrakenFilesDownload, SpotifyDownload
from app.config import settings

logger = get_logger(__name__)


def setup_inline_actions(dp: Dispatcher, bot: Bot):
    """Setup inline keyboard callback handlers"""
    
    @dp.callback_query(lambda c: c.data and c.data.startswith("action:"))
    async def handle_inline_action(callback: CallbackQuery):
        """Handle inline keyboard callbacks"""
        if not callback.data or not callback.message:
            return
        
        try:
            # Parse callback data: action:type:url
            parts = callback.data.split(":", 2)
            if len(parts) < 3:
                await callback.answer("❌ Invalid action")
                return
            
            action_type = parts[1]
            url = parts[2]
            
            # Acknowledge callback
            await callback.answer("⏳ Processing...")
            
            # Create a message-like object by sending a new message and then processing it
            # We'll create a temporary message to trigger the command handler
            bot_msg = await callback.message.answer("📥 Processing request...")
            
            # Route to appropriate handler based on action type
            if action_type == "download":
                # Use existing download infrastructure
                try:
                    downloader_type = detect_downloader_type(url)
                    
                    if downloader_type == "youtube":
                        downloader = YoutubeDownload(bot, bot_msg, url)
                    elif downloader_type == "spotify":
                        if not settings.spotify_enabled:
                            await bot_msg.edit_text("❌ Spotify downloads are disabled")
                            return
                        if not settings.spotify_client_id or not settings.spotify_client_secret:
                            await bot_msg.edit_text("❌ Spotify credentials not configured")
                            return
                        downloader = SpotifyDownload(bot, bot_msg, url)
                    elif downloader_type == "instagram":
                        downloader = InstagramDownload(bot, bot_msg, url)
                    elif downloader_type == "pixeldrain":
                        downloader = PixeldrainDownload(bot, bot_msg, url)
                    elif downloader_type == "krakenfiles":
                        downloader = KrakenFilesDownload(bot, bot_msg, url)
                    else:
                        downloader = DirectDownload(bot, bot_msg, url)
                    
                    await downloader.start()
                except Exception as e:
                    logger.error(f"Download failed: {e}", exc_info=True)
                    await bot_msg.edit_text(f"❌ Download failed: {str(e)[:500]}")
            
            elif action_type == "audio":
                # Extract audio using media command logic
                from app.commands.media_commands import download_video_for_processing, check_ffmpeg_available
                import ffmpeg
                import tempfile
                from pathlib import Path
                from aiogram.types import FSInputFile
                
                if not settings.enable_ffmpeg or not check_ffmpeg_available():
                    await bot_msg.edit_text("❌ FFmpeg not available for audio extraction")
                    return
                
                try:
                    video_path = await download_video_for_processing(bot, bot_msg, url)
                    if not video_path or not video_path.exists():
                        await bot_msg.edit_text("❌ Failed to download video")
                        return
                    
                    await bot_msg.edit_text("🎵 Extracting audio (MP3)...")
                    
                    output_path = video_path.parent / f"audio_{video_path.stem}.mp3"
                    
                    stream = ffmpeg.input(str(video_path))
                    stream = ffmpeg.output(stream, str(output_path), vn=None, acodec="libmp3lame", audio_bitrate="192k")
                    ffmpeg.run(stream, overwrite_output=True, quiet=True)
                    
                    if output_path.exists() and output_path.stat().st_size > 0:
                        await bot_msg.edit_text("📤 Uploading audio...")
                        file = FSInputFile(output_path)
                        await bot.send_audio(chat_id=callback.message.chat.id, audio=file, caption="Audio (MP3)")
                        await bot_msg.delete()
                    else:
                        await bot_msg.edit_text("❌ Failed to extract audio")
                    
                    # Cleanup
                    try:
                        output_path.unlink()
                        if video_path.parent != Path(tempfile.gettempdir()):
                            video_path.unlink()
                    except Exception:
                        pass
                except Exception as e:
                    logger.error(f"Audio extraction failed: {e}", exc_info=True)
                    await bot_msg.edit_text(f"❌ Audio extraction failed: {str(e)[:500]}")
            
            elif action_type == "clip":
                # Need time parameters - show instructions
                await bot_msg.edit_text(
                    "✂️ <b>Clip Video</b>\n\n"
                    "Please use: /clip &lt;url&gt; &lt;start_time&gt; &lt;duration&gt;\n\n"
                    f"Example: /clip {url} 00:30 00:15"
                )
            
            elif action_type == "gif":
                # Need time parameters - show instructions
                await bot_msg.edit_text(
                    "🎬 <b>Generate GIF</b>\n\n"
                    "Please use: /gif &lt;url&gt; &lt;start_time&gt; &lt;duration&gt;\n\n"
                    f"Example: /gif {url} 00:10 00:05"
                )
            
            elif action_type == "info":
                # Show URL info
                downloader_type = detect_downloader_type(url)
                await bot_msg.edit_text(
                    f"ℹ️ <b>URL Info</b>\n\n"
                    f"URL: {url}\n"
                    f"Type: {downloader_type}\n\n"
                    f"Use /download {url} to download"
                )
            else:
                await bot_msg.edit_text(f"❌ Unknown action: {action_type}")
                
        except Exception as e:
            logger.error(f"Failed to handle inline action: {e}", exc_info=True)
            try:
                await callback.answer("❌ Action failed")
                if 'bot_msg' in locals():
                    await bot_msg.edit_text(f"❌ Action failed: {str(e)[:500]}")
            except Exception:
                pass
    
    logger.debug("✅ Inline actions setup completed")
