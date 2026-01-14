"""Media processing commands using FFmpeg"""

import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Tuple

import ffmpeg
from aiogram import Bot, Dispatcher
from aiogram.types import Message, FSInputFile
from aiogram.filters import Command

from app.utils.logger import get_logger
from app.utils.download_utils import detect_downloader_type, sizeof_fmt
from app.utils.file_downloader import download_telegram_file
from app.utils.zip_utils import create_zip_file, create_zip_from_files
from app.downloaders import YoutubeDownload, DirectDownload
from app.config import settings

logger = get_logger(__name__)


async def _record_conversion_stat(conversion_type: str, status: str, chat_id: int, 
                                  input_format: str = None, output_format: str = None,
                                  file_size: int = None, error_message: str = None):
    """Helper to record conversion statistics"""
    try:
        from app.services.statistics_service import statistics_service
        await statistics_service.record_conversion(
            conversion_type=conversion_type,
            status=status,
            chat_id=str(chat_id),
            input_format=input_format,
            output_format=output_format,
            file_size=file_size,
            error_message=error_message,
        )
    except Exception as e:
        logger.debug(f"Failed to record conversion statistic: {e}")


def check_ffmpeg_available() -> bool:
    """Check if FFmpeg is available"""
    return shutil.which("ffmpeg") is not None


def parse_time(time_str: str) -> Optional[float]:
    """Parse time string to seconds. Supports HH:MM:SS, MM:SS, or seconds"""
    if not time_str:
        return None
    
    # Try to parse as seconds (float)
    try:
        return float(time_str)
    except ValueError:
        pass
    
    # Try to parse as HH:MM:SS or MM:SS
    parts = time_str.split(":")
    if len(parts) == 3:  # HH:MM:SS
        try:
            hours, minutes, seconds = map(float, parts)
            return hours * 3600 + minutes * 60 + seconds
        except ValueError:
            pass
    elif len(parts) == 2:  # MM:SS
        try:
            minutes, seconds = map(float, parts)
            return minutes * 60 + seconds
        except ValueError:
            pass
    
    return None


def format_time(seconds: float) -> str:
    """Format seconds to HH:MM:SS"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


async def download_video_for_processing(bot: Bot, bot_msg: Message, url: str) -> Optional[Path]:
    """Download video using existing downloader infrastructure"""
    try:
        downloader_type = detect_downloader_type(url)
        
        if downloader_type == "youtube":
            downloader = YoutubeDownload(bot, bot_msg, url)
        else:
            downloader = DirectDownload(bot, bot_msg, url)
        
        # Force video format
        downloader._force_format = "video"
        downloader._force_quality = "high"
        
        # Download the video
        files = await downloader._download()
        
        if files and len(files) > 0:
            return files[0]
        return None
    except Exception as e:
        from app.downloaders.youtube import GeoRestrictionError
        if isinstance(e, GeoRestrictionError):
            logger.warning(f"Video is geo-restricted: {url}")
            # Return None to indicate failure, but don't log as error
        else:
            logger.error(f"Failed to download video for processing: {e}")
        return None


async def download_video_from_message(bot: Bot, message: Message) -> Optional[Path]:
    """Download video from Telegram message (attached or reply)"""
    temp_dir = None
    try:
        video_file = None
        
        # Check if video is attached to current message
        if message.video:
            video_file = message.video
        elif message.document:
            # Check if document is a video file
            mime_type = message.document.mime_type or ""
            if mime_type.startswith("video/"):
                video_file = message.document
        
        # Check if replying to a message with video
        if not video_file and message.reply_to_message:
            reply = message.reply_to_message
            if reply.video:
                video_file = reply.video
            elif reply.document:
                mime_type = reply.document.mime_type or ""
                if mime_type.startswith("video/"):
                    video_file = reply.document
        
        if not video_file:
            return None
        
        # Check file size before downloading (limit to 200MB for safety)
        max_file_size = 200 * 1024 * 1024  # 200 MB
        if hasattr(video_file, 'file_size') and video_file.file_size:
            if video_file.file_size > max_file_size:
                logger.warning(f"Video file too large: {sizeof_fmt(video_file.file_size)}")
                return None
        
        # Download file
        file_info = await bot.get_file(video_file.file_id)
        
        # Create temporary directory for video
        temp_dir = Path(tempfile.mkdtemp(prefix="scoutbot-gif-"))
        file_path = temp_dir / file_info.file_path.split("/")[-1] if file_info.file_path else "video"
        
        # Use utility function that handles both local and cloud Bot API
        success = await download_telegram_file(bot, file_info, file_path)
        if not success:
            logger.error("Failed to download video from message")
            return None
        
        if file_path.exists() and file_path.stat().st_size > 0:
            return file_path
        
        return None
    except Exception as e:
        logger.error(f"Failed to download video from message: {e}", exc_info=True)
        # Cleanup temp directory on error
        if temp_dir and temp_dir.exists():
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception:
                pass
        return None


def setup_media_commands(dp: Optional[Dispatcher], bot: Optional[Bot]):
    """Setup media processing commands"""
    if not dp or not bot:
        return
    
    @dp.message(Command("clip"))
    async def clip_command(message: Message):
        """Extract video segment"""
        if not settings.enable_ffmpeg:
            await message.answer(
                "❌ <b>FFmpeg is disabled.</b>\n\n"
                "Video clipping requires FFmpeg to be enabled.\n"
                "Please set ENABLE_FFMPEG=true in your configuration."
            )
            return
        
        if not check_ffmpeg_available():
            await message.answer(
                "❌ <b>FFmpeg not available.</b>\n\n"
                "Video clipping requires FFmpeg to be installed."
            )
            return
        
        message_text = message.text or ""
        parts = message_text.split()
        
        if len(parts) < 4:
            await message.answer(
                "❌ <b>Invalid syntax.</b>\n\n"
                "Usage: /clip &lt;url&gt; &lt;start_time&gt; &lt;duration&gt;\n\n"
                "Examples:\n"
                "• /clip https://youtube.com/watch?v=... 00:30 00:15\n"
                "• /clip https://youtube.com/watch?v=... 1:30 30\n"
                "• /clip https://youtube.com/watch?v=... 90 15"
            )
            return
        
        url = parts[1]
        start_time_str = parts[2]
        duration_str = parts[3]
        
        # Parse times
        start_time = parse_time(start_time_str)
        duration = parse_time(duration_str)
        
        if start_time is None or duration is None:
            await message.answer(
                "❌ <b>Invalid time format.</b>\n\n"
                "Time can be in format:\n"
                "• HH:MM:SS (e.g., 01:30:45)\n"
                "• MM:SS (e.g., 1:30)\n"
                "• Seconds (e.g., 90)"
            )
            return
        
        bot_msg = await message.answer("📥 Downloading video...")
        
        try:
            # Download video
            video_path = await download_video_for_processing(bot, bot_msg, url)
            if not video_path or not video_path.exists():
                await bot_msg.edit_text("❌ Failed to download video")
                return
            
            await bot_msg.edit_text(f"✂️ Clipping segment ({format_time(start_time)} - {format_time(start_time + duration)})...")
            
            # Create output file
            output_path = video_path.parent / f"clip_{int(start_time)}_{int(duration)}.mp4"
            
            # Extract segment using FFmpeg
            stream = ffmpeg.input(str(video_path), ss=start_time, t=duration)
            stream = ffmpeg.output(stream, str(output_path), vcodec="copy", acodec="copy")
            ffmpeg.run(stream, overwrite_output=True, quiet=True)
            
            if not output_path.exists() or output_path.stat().st_size == 0:
                await bot_msg.edit_text("❌ Failed to create clip")
                return
            
            await bot_msg.edit_text("📦 Creating ZIP archive...")
            
            # Rename clip to scoutbot1.mp4
            new_clip_name = output_path.parent / "scoutbot1.mp4"
            output_path.rename(new_clip_name)
            
            # Create ZIP file with standardized name
            zip_path = new_clip_name.parent / "scoutbotmp4.zip"
            if not create_zip_file(new_clip_name, zip_path, internal_filename="scoutbot1.mp4"):
                await bot_msg.edit_text("❌ Failed to create ZIP file")
                return
            
            await bot_msg.edit_text("📤 Uploading ZIP file...")
            
            # Upload ZIP as document
            file = FSInputFile(zip_path, filename=zip_path.name)
            await bot.send_document(
                chat_id=message.chat.id,
                document=file,
                caption=f"Clip (ZIP): {format_time(start_time)} - {format_time(start_time + duration)}"
            )
            
            # Record conversion statistic
            await _record_conversion_stat(
                "clip", "success", message.chat.id,
                input_format="mp4", output_format="mp4",
                file_size=new_clip_name.stat().st_size if new_clip_name.exists() else None,
            )
            
            await bot_msg.delete()
            
            # Cleanup
            try:
                new_clip_name.unlink()
                zip_path.unlink()
                if video_path.parent != Path(tempfile.gettempdir()):
                    video_path.unlink()
            except Exception:
                pass
                
        except Exception as e:
            logger.error(f"Clip command failed: {e}", exc_info=True)
            error_msg = str(e)
            if len(error_msg) > 500:
                error_msg = error_msg[:500] + "..."
            await bot_msg.edit_text(f"❌ Clip failed: {error_msg}")
    
    @dp.message(Command("gif"))
    async def gif_command(message: Message):
        """Generate optimized GIF from video"""
        if not settings.enable_ffmpeg:
            await message.answer(
                "❌ <b>FFmpeg is disabled.</b>\n\n"
                "GIF generation requires FFmpeg to be enabled."
            )
            return
        
        if not check_ffmpeg_available():
            await message.answer("❌ <b>FFmpeg not available.</b>")
            return
        
        message_text = message.text or ""
        parts = message_text.split()
        
        # Check if video is attached or in reply
        video_path = None
        url = None
        start_time_str = None
        duration_str = None
        
        # Try to get video from message first
        video_path = await download_video_from_message(bot, message)
        
        if video_path:
            # Video from message - parameters are optional
            if len(parts) >= 3:
                start_time_str = parts[1]
                duration_str = parts[2]
            elif len(parts) >= 2:
                # Only duration provided, start at 0
                start_time_str = "0"
                duration_str = parts[1]
            # If no parameters, will use defaults
        else:
            # No video in message - must be URL with required parameters
            if len(parts) < 4:
                await message.answer(
                    "❌ <b>Invalid syntax.</b>\n\n"
                    "Usage:\n"
                    "• /gif &lt;url&gt; &lt;start_time&gt; &lt;duration&gt; (for URLs)\n"
                    "• /gif [start_time] [duration] (with video attached or as reply)\n\n"
                    "Examples:\n"
                    "• /gif https://youtube.com/watch?v=... 00:10 00:05\n"
                    "• /gif 0 5 (with video attached)\n"
                    "• /gif (with video attached, uses defaults)"
                )
                return
            
            url = parts[1]
            start_time_str = parts[2]
            duration_str = parts[3]
        
        # Parse times (use defaults if not provided for video from message)
        start_time = parse_time(start_time_str) if start_time_str else 0.0
        duration = parse_time(duration_str) if duration_str else None
        
        if start_time is None:
            start_time = 0.0
        
        if duration is None:
            # Default duration: 5 seconds or video length if shorter
            duration = 5.0
            # Try to get video duration if video is already downloaded
            if video_path and video_path.exists():
                try:
                    probe = ffmpeg.probe(str(video_path))
                    video_stream = next((s for s in probe.get("streams", []) if s.get("codec_type") == "video"), None)
                    if video_stream:
                        video_duration = float(video_stream.get("duration", 0))
                        if video_duration > 0:
                            duration = min(5.0, video_duration)
                except Exception:
                    pass  # Use default 5 seconds
        
        if duration is None or duration <= 0:
            await message.answer("❌ <b>Invalid time format.</b>")
            return
        
        # Limit duration to 15 seconds max
        max_duration = getattr(settings, 'gif_duration_limit', 15)
        if duration > max_duration:
            await message.answer(
                f"❌ <b>Duration too long.</b>\n\n"
                f"Maximum duration is {max_duration} seconds for GIFs."
            )
            return
        
        bot_msg = await message.answer("📥 Downloading video..." if url else "📥 Processing video...")
        
        try:
            # Download video if URL provided
            if url and not video_path:
                video_path = await download_video_for_processing(bot, bot_msg, url)
                if not video_path or not video_path.exists():
                    await bot_msg.edit_text("❌ Failed to download video")
                    return
            
            await bot_msg.edit_text("🎬 Generating GIF...")
            
            # Create temporary files for palette and GIF
            palette_path = video_path.parent / "palette.png"
            gif_path = video_path.parent / f"gif_{int(start_time)}_{int(duration)}.gif"
            
            # Step 1: Generate palette
            palette_stream = ffmpeg.input(str(video_path), ss=start_time, t=duration)
            palette_stream = ffmpeg.filter(palette_stream, 'fps', fps=10, round='up')
            palette_stream = ffmpeg.filter(palette_stream, 'scale', w=320, h=-1)
            palette_stream = ffmpeg.filter(palette_stream, 'palettegen', reserve_transparent=0)
            palette_output = ffmpeg.output(palette_stream, str(palette_path), vframes=1)
            ffmpeg.run(palette_output, overwrite_output=True, quiet=True)
            
            # Step 2: Generate GIF with palette
            video_stream = ffmpeg.input(str(video_path), ss=start_time, t=duration)
            video_stream = ffmpeg.filter(video_stream, 'fps', fps=10, round='up')
            video_stream = ffmpeg.filter(video_stream, 'scale', w=320, h=-1)
            palette_input = ffmpeg.input(str(palette_path))
            gif_stream = ffmpeg.filter([video_stream, palette_input], 'paletteuse', dither='bayer')
            gif_output = ffmpeg.output(gif_stream, str(gif_path))
            ffmpeg.run(gif_output, overwrite_output=True, quiet=True)
            
            # Cleanup palette
            try:
                palette_path.unlink()
            except Exception:
                pass
            
            if not gif_path.exists() or gif_path.stat().st_size == 0:
                await bot_msg.edit_text("❌ Failed to generate GIF")
                return
            
            # Check file size (max 10MB for Telegram)
            max_size = getattr(settings, 'max_gif_size', 10) * 1024 * 1024
            if gif_path.stat().st_size > max_size:
                await bot_msg.edit_text(
                    f"❌ <b>GIF too large.</b>\n\n"
                    f"Generated GIF is {sizeof_fmt(gif_path.stat().st_size)}, "
                    f"maximum is {sizeof_fmt(max_size)}.\n"
                    f"Try a shorter duration."
                )
                return
            
            await bot_msg.edit_text("📦 Creating ZIP archive...")
            
            # Rename GIF to scoutbot1.gif
            new_gif_name = gif_path.parent / "scoutbot1.gif"
            gif_path.rename(new_gif_name)
            
            # Create ZIP file with standardized name
            zip_path = new_gif_name.parent / "scoutbotgif.zip"
            if not create_zip_file(new_gif_name, zip_path, internal_filename="scoutbot1.gif"):
                await bot_msg.edit_text("❌ Failed to create ZIP file")
                return
            
            await bot_msg.edit_text("📤 Uploading ZIP file...")
            
            # Upload ZIP as document
            file = FSInputFile(zip_path, filename=zip_path.name)
            await bot.send_document(
                chat_id=message.chat.id,
                document=file,
                caption=f"GIF (ZIP): {format_time(start_time)} - {format_time(start_time + duration)}"
            )
            
            # Record conversion statistic
            await _record_conversion_stat(
                "gif", "success", message.chat.id,
                input_format="mp4", output_format="gif",
                file_size=new_gif_name.stat().st_size if new_gif_name.exists() else None,
            )
            
            await bot_msg.delete()
            
            # Cleanup
            try:
                new_gif_name.unlink()
                zip_path.unlink()
                # Cleanup video if it was downloaded from message (in temp dir)
                if video_path and video_path.exists():
                    # Check if video is in a temp directory we created
                    if "scoutbot-gif-" in str(video_path.parent):
                        # Remove entire temp directory
                        shutil.rmtree(video_path.parent, ignore_errors=True)
                    elif video_path.parent != Path(tempfile.gettempdir()):
                        video_path.unlink()
            except Exception:
                pass
                
        except Exception as e:
            logger.error(f"GIF command failed: {e}", exc_info=True)
            error_msg = str(e)
            if len(error_msg) > 500:
                error_msg = error_msg[:500] + "..."
            await bot_msg.edit_text(f"❌ GIF generation failed: {error_msg}")
    
    @dp.message(Command("subs"))
    async def subs_command(message: Message):
        """Download subtitles from video"""
        message_text = message.text or ""
        parts = message_text.split()
        
        if len(parts) < 2:
            await message.answer(
                "❌ <b>Invalid syntax.</b>\n\n"
                "Usage: /subs &lt;url&gt;\n\n"
                "Example: /subs https://youtube.com/watch?v=..."
            )
            return
        
        url = parts[1]
        bot_msg = await message.answer("📥 Downloading subtitles...")
        
        try:
            # Use yt-dlp to extract subtitles
            import yt_dlp
            
            ydl_opts = {
                'writesubtitles': True,
                'writeautomaticsub': True,
                'subtitleslangs': ['en', 'pt', 'es', 'fr', 'de', 'it', 'ru', 'ja', 'ko', 'zh'],
                'skip_download': True,
                'quiet': True,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                if 'subtitles' not in info and 'automatic_captions' not in info:
                    await bot_msg.edit_text("❌ No subtitles available for this video")
                    return
                
                # Download subtitles
                with tempfile.TemporaryDirectory() as tempdir:
                    ydl_opts['outtmpl'] = str(Path(tempdir) / '%(title)s.%(ext)s')
                    ydl.download([url])
                    
                    # Find subtitle files
                    subtitle_files = list(Path(tempdir).glob("*.vtt")) + list(Path(tempdir).glob("*.srt"))
                    
                    if not subtitle_files:
                        await bot_msg.edit_text("❌ Failed to download subtitles")
                        return
                    
                    await bot_msg.edit_text("📦 Creating ZIP archive...")
                    
                    # Rename subtitle files to scoutbot1.{ext}, scoutbot2.{ext}, etc.
                    renamed_subs = []
                    internal_names = []
                    for idx, sub_file in enumerate(subtitle_files, 1):
                        ext = sub_file.suffix  # .vtt, .srt, etc.
                        new_name = sub_file.parent / f"scoutbot{idx}{ext}"
                        sub_file.rename(new_name)
                        renamed_subs.append(new_name)
                        internal_names.append(f"scoutbot{idx}{ext}")
                    
                    # Create ZIP file with standardized name
                    zip_path = renamed_subs[0].parent / "scoutbotsubs.zip"
                    if not create_zip_from_files(renamed_subs, zip_path, internal_names=internal_names):
                        await bot_msg.edit_text("❌ Failed to create ZIP file")
                        return
                    
                    await bot_msg.edit_text("📤 Uploading ZIP file...")
                    
                    # Upload ZIP as document
                    file = FSInputFile(zip_path, filename=zip_path.name)
                    await bot.send_document(
                        chat_id=message.chat.id,
                        document=file,
                        caption=f"Subtitles (ZIP): {info.get('title', 'Video')}"
                    )
                    
                    await bot_msg.delete()
                    
                    # Cleanup
                    try:
                        for renamed_sub in renamed_subs:
                            renamed_sub.unlink()
                        zip_path.unlink()
                    except Exception:
                        pass
                    
        except Exception as e:
            logger.error(f"Subs command failed: {e}", exc_info=True)
            error_msg = str(e)
            if len(error_msg) > 500:
                error_msg = error_msg[:500] + "..."
            await bot_msg.edit_text(f"❌ Failed to download subtitles: {error_msg}")
    
    @dp.message(Command("frames"))
    async def frames_command(message: Message):
        """Generate thumbnail grid from video"""
        if not settings.enable_ffmpeg:
            await message.answer(
                "❌ <b>FFmpeg is disabled.</b>\n\n"
                "Frame extraction requires FFmpeg to be enabled."
            )
            return
        
        if not check_ffmpeg_available():
            await message.answer("❌ <b>FFmpeg not available.</b>")
            return
        
        message_text = message.text or ""
        parts = message_text.split()
        
        if len(parts) < 2:
            await message.answer(
                "❌ <b>Invalid syntax.</b>\n\n"
                "Usage: /frames &lt;url&gt; [count]\n\n"
                "Example: /frames https://youtube.com/watch?v=... 9"
            )
            return
        
        url = parts[1]
        frame_count = 9  # Default
        
        if len(parts) >= 3:
            try:
                frame_count = int(parts[2])
                if frame_count < 1 or frame_count > 20:
                    frame_count = 9
            except ValueError:
                pass
        
        bot_msg = await message.answer("📥 Downloading video...")
        
        try:
            # Download video
            video_path = await download_video_for_processing(bot, bot_msg, url)
            if not video_path or not video_path.exists():
                await bot_msg.edit_text("❌ Failed to download video")
                return
            
            await bot_msg.edit_text(f"🖼️ Extracting {frame_count} frames...")
            
            # Get video duration
            probe = ffmpeg.probe(str(video_path))
            streams = probe.get('streams', [])
            if not streams:
                await bot_msg.edit_text("❌ Could not determine video duration")
                return
            duration = float(streams[0].get('duration', 0))
            
            if duration == 0:
                await bot_msg.edit_text("❌ Could not determine video duration")
                return
            
            # Extract frames evenly distributed
            frame_interval = duration / (frame_count + 1)
            frame_paths = []
            
            with tempfile.TemporaryDirectory() as tempdir:
                for i in range(1, frame_count + 1):
                    timestamp = frame_interval * i
                    frame_path = Path(tempdir) / f"frame_{i:02d}.jpg"
                    
                    stream = ffmpeg.input(str(video_path), ss=timestamp)
                    stream = ffmpeg.output(stream, str(frame_path), vframes=1, **{'qscale:v': 2})
                    ffmpeg.run(stream, overwrite_output=True, quiet=True)
                    
                    if frame_path.exists():
                        frame_paths.append(frame_path)
                
                if not frame_paths:
                    await bot_msg.edit_text("❌ Failed to extract frames")
                    return
                
                await bot_msg.edit_text("📦 Creating ZIP archive...")
                
                # Rename frames to scoutbot1.jpg, scoutbot2.jpg, etc.
                renamed_frames = []
                internal_names = []
                for idx, frame_path in enumerate(frame_paths, 1):
                    new_name = frame_path.parent / f"scoutbot{idx}.jpg"
                    frame_path.rename(new_name)
                    renamed_frames.append(new_name)
                    internal_names.append(f"scoutbot{idx}.jpg")
                
                # Create ZIP file with standardized name
                zip_path = renamed_frames[0].parent / "scoutbotframes.zip"
                if not create_zip_from_files(renamed_frames, zip_path, internal_names=internal_names):
                    await bot_msg.edit_text("❌ Failed to create ZIP file")
                    return
                
                await bot_msg.edit_text("📤 Uploading ZIP file...")
                
                # Upload ZIP as document
                file = FSInputFile(zip_path, filename=zip_path.name)
                await bot.send_document(
                    chat_id=message.chat.id,
                    document=file,
                    caption=f"Video frames (ZIP): {len(frame_paths)} frames extracted"
                )
                
                await bot_msg.delete()
                
                # Cleanup
                try:
                    for renamed_frame in renamed_frames:
                        renamed_frame.unlink()
                    zip_path.unlink()
                    if video_path.parent != Path(tempfile.gettempdir()):
                        video_path.unlink()
                except Exception:
                    pass
                
        except Exception as e:
            logger.error(f"Frames command failed: {e}", exc_info=True)
            error_msg = str(e)
            if len(error_msg) > 500:
                error_msg = error_msg[:500] + "..."
            await bot_msg.edit_text(f"❌ Frame extraction failed: {error_msg}")
    
    @dp.message(Command("compress"))
    async def compress_command(message: Message):
        """Compress video/audio for Telegram"""
        if not settings.enable_ffmpeg:
            await message.answer(
                "❌ <b>FFmpeg is disabled.</b>\n\n"
                "Compression requires FFmpeg to be enabled."
            )
            return
        
        if not check_ffmpeg_available():
            await message.answer("❌ <b>FFmpeg not available.</b>")
            return
        
        # Check if message has a document/video/audio attached
        if not message.document and not message.video and not message.audio:
            await message.answer(
                "❌ <b>No file attached.</b>\n\n"
                "Please send a video, audio, or document file and use /compress as a reply, "
                "or use /compress &lt;url&gt; to compress a video from URL."
            )
            return
        
        bot_msg = await message.answer("📥 Processing file...")
        
        try:
            file_to_compress = None
            file_path = None
            
            # Handle file from message
            if message.document:
                file_to_compress = message.document
            elif message.video:
                file_to_compress = message.video
            elif message.audio:
                file_to_compress = message.audio
            
            if file_to_compress:
                # Download file
                file_info = await bot.get_file(file_to_compress.file_id)
                file_path = Path(tempfile.gettempdir()) / (file_info.file_path.split("/")[-1] if file_info.file_path else "file")
                
                await bot_msg.edit_text("📥 Downloading file...")
                # Use utility function that handles both local and cloud Bot API
                success = await download_telegram_file(bot, file_info, file_path)
                if not success:
                    await bot_msg.edit_text("❌ Failed to download file")
                    return
            
            if not file_path or not file_path.exists():
                await bot_msg.edit_text("❌ Failed to download file")
                return
            
            await bot_msg.edit_text("🗜️ Compressing file...")
            
            # Determine file type and compress accordingly
            output_path = file_path.parent / f"{file_path.stem}_compressed{file_path.suffix}"
            
            try:
                probe = ffmpeg.probe(str(file_path))
                streams = probe.get("streams", [])
                has_video = any(s.get("codec_type") == "video" for s in streams)
                has_audio = any(s.get("codec_type") == "audio" for s in streams)
                
                if has_video:
                    # Compress video: reduce resolution and bitrate
                    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
                    width = video_stream.get("width", 1280) if video_stream else 1280
                    height = video_stream.get("height", 720) if video_stream else 720
                    
                    # Get original bitrate to determine compression strategy
                    original_bitrate = video_stream.get("bit_rate")
                    if original_bitrate:
                        try:
                            original_bitrate = int(original_bitrate)
                        except (ValueError, TypeError):
                            original_bitrate = None
                    
                    # Scale down if too large (max 1280x720)
                    if width > 1280 or height > 720:
                        scale_filter = "scale='min(1280,iw)':'min(720,ih)':force_original_aspect_ratio=decrease"
                    else:
                        scale_filter = None
                    
                    # Use more aggressive compression settings
                    # CRF 32 = more compression, lower quality
                    # Preset "fast" = faster encoding, smaller file
                    stream = ffmpeg.input(str(file_path))
                    if scale_filter:
                        stream = ffmpeg.filter(stream, 'scale', 'min(1280,iw)', 'min(720,ih)')
                    
                    output_kwargs = {
                        "vcodec": "libx264",
                        "crf": 32,  # More aggressive compression (higher CRF = smaller file)
                        "preset": "fast",  # Faster encoding, smaller file size
                        "acodec": "aac",
                        "movflags": "+faststart",  # Optimize for streaming
                    }
                    if has_audio:
                        output_kwargs["audio_bitrate"] = "96k"  # Lower audio bitrate for better compression
                    stream = ffmpeg.output(stream, str(output_path), **output_kwargs)
                    ffmpeg.run(stream, overwrite_output=True, quiet=True)
                elif has_audio:
                    # Compress audio: reduce bitrate
                    stream = ffmpeg.input(str(file_path))
                    stream = ffmpeg.output(
                        stream,
                        str(output_path),
                        acodec="libmp3lame",
                        audio_bitrate="128k",
                    )
                    ffmpeg.run(stream, overwrite_output=True, quiet=True)
                else:
                    await bot_msg.edit_text("❌ Unsupported file type")
                    return
                
                if not output_path.exists() or output_path.stat().st_size == 0:
                    await bot_msg.edit_text("❌ Compression failed")
                    return
                
                # Check if compression actually reduced size
                original_size = file_path.stat().st_size
                compressed_size = output_path.stat().st_size
                
                # If compression didn't reduce size, try more aggressive compression
                if compressed_size >= original_size and has_video:
                    logger.info(f"First compression attempt didn't reduce size. Trying more aggressive compression...")
                    await bot_msg.edit_text("🗜️ Trying more aggressive compression...")
                    
                    # Try even more aggressive settings
                    try:
                        probe = ffmpeg.probe(str(file_path))
                        streams = probe.get("streams", [])
                        video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
                        width = video_stream.get("width", 1280) if video_stream else 1280
                        height = video_stream.get("height", 720) if video_stream else 720
                        
                        # Force scale down to 720p or smaller
                        target_width = min(width, 1280)
                        target_height = min(height, 720)
                        if width > target_width or height > target_height:
                            # Maintain aspect ratio
                            aspect = width / height
                            if aspect > target_width / target_height:
                                target_height = int(target_width / aspect)
                            else:
                                target_width = int(target_height * aspect)
                        
                        stream = ffmpeg.input(str(file_path))
                        stream = ffmpeg.filter(stream, 'scale', target_width, target_height)
                        
                        output_kwargs = {
                            "vcodec": "libx264",
                            "crf": 35,  # Very aggressive compression
                            "preset": "ultrafast",  # Fastest encoding
                            "acodec": "aac",
                            "audio_bitrate": "64k",  # Very low audio bitrate
                            "movflags": "+faststart",
                        }
                        stream = ffmpeg.output(stream, str(output_path), **output_kwargs)
                        ffmpeg.run(stream, overwrite_output=True, quiet=True)
                        
                        # Check again
                        compressed_size = output_path.stat().st_size
                    except Exception as e:
                        logger.warning(f"More aggressive compression failed: {e}")
                
                # If still didn't reduce size, use original file but inform user
                if compressed_size >= original_size:
                    logger.warning(f"Compression didn't reduce size: {sizeof_fmt(original_size)} -> {sizeof_fmt(compressed_size)}")
                    # Use original file if compression didn't help
                    output_path.unlink()
                    output_path = file_path
                    compressed_size = original_size
                    compression_note = "⚠️ Compression didn't reduce size, sending original file"
                else:
                    compression_note = f"✅ Compressed: {sizeof_fmt(original_size)} → {sizeof_fmt(compressed_size)}"
                
                await bot_msg.edit_text("📦 Creating ZIP archive...")
                
                # Rename file to scoutbot1.{original_extension}
                original_ext = output_path.suffix  # .mp4, .mp3, etc.
                new_compressed_name = output_path.parent / f"scoutbot1{original_ext}"
                
                # Only rename if it's not the original file
                if output_path != file_path:
                    output_path.rename(new_compressed_name)
                else:
                    # Copy original to new name for consistency
                    shutil.copy2(output_path, new_compressed_name)
                
                # Create ZIP file with standardized name
                zip_path = new_compressed_name.parent / "scoutbotcompressed.zip"
                if not create_zip_file(new_compressed_name, zip_path, internal_filename=f"scoutbot1{original_ext}"):
                    await bot_msg.edit_text("❌ Failed to create ZIP file")
                    return
                
                await bot_msg.edit_text("📤 Uploading ZIP file...")
                
                # Upload ZIP as document
                file = FSInputFile(zip_path, filename=zip_path.name)
                await bot.send_document(
                    chat_id=message.chat.id,
                    document=file,
                    caption=f"Compressed (ZIP)\n{compression_note}"
                )
                
                await bot_msg.delete()
                
                # Cleanup
                try:
                    # Only delete compressed file if it's different from original
                    if new_compressed_name.exists() and new_compressed_name != file_path:
                        new_compressed_name.unlink()
                    zip_path.unlink()
                    # Only delete original if it's in temp directory and different from compressed
                    if file_path.parent == Path(tempfile.gettempdir()) and file_path != new_compressed_name:
                        file_path.unlink()
                except Exception as e:
                    logger.debug(f"Cleanup error (non-critical): {e}")
                    pass
                    
            except Exception as e:
                logger.error(f"Compression failed: {e}", exc_info=True)
                raise
                
        except Exception as e:
            logger.error(f"Compress command failed: {e}", exc_info=True)
            error_msg = str(e)
            if len(error_msg) > 500:
                error_msg = error_msg[:500] + "..."
            await bot_msg.edit_text(f"❌ Compression failed: {error_msg}")
    
    @dp.message(Command("audio"))
    async def audio_command(message: Message):
        """Extract audio from video with format options"""
        if not settings.enable_ffmpeg:
            await message.answer(
                "❌ <b>FFmpeg is disabled.</b>\n\n"
                "Audio extraction requires FFmpeg to be enabled."
            )
            return
        
        if not check_ffmpeg_available():
            await message.answer("❌ <b>FFmpeg not available.</b>")
            return
        
        message_text = message.text or ""
        parts = message_text.split()
        
        if len(parts) < 2:
            await message.answer(
                "❌ <b>Invalid syntax.</b>\n\n"
                "Usage: /audio &lt;url&gt; [format] [options]\n\n"
                "Formats: mp3, m4a, opus, wav (default: mp3)\n"
                "Options:\n"
                "• --normalize: Normalize audio volume\n"
                "• --remove-silence: Remove silence from audio\n\n"
                "Examples:\n"
                "• /audio https://youtube.com/watch?v=...\n"
                "• /audio https://youtube.com/watch?v=... m4a\n"
                "• /audio https://youtube.com/watch?v=... mp3 --normalize"
            )
            return
        
        url = parts[1]
        audio_format = "mp3"  # Default
        normalize = False
        remove_silence = False
        
        # Parse format and options
        for part in parts[2:]:
            if part.lower() in ["mp3", "m4a", "opus", "wav"]:
                audio_format = part.lower()
            elif part.lower() == "--normalize":
                normalize = True
            elif part.lower() == "--remove-silence":
                remove_silence = True
        
        bot_msg = await message.answer("📥 Downloading video...")
        
        try:
            # Download video
            video_path = await download_video_for_processing(bot, bot_msg, url)
            if not video_path or not video_path.exists():
                await bot_msg.edit_text("❌ Failed to download video")
                return
            
            await bot_msg.edit_text(f"🎵 Extracting audio ({audio_format.upper()})...")
            
            # Create output file
            output_path = video_path.parent / f"audio_{video_path.stem}.{audio_format}"
            
            # Build FFmpeg command
            stream = ffmpeg.input(str(video_path))
            
            # Apply filters if requested
            if normalize:
                stream = ffmpeg.filter(stream, 'loudnorm', I=-16, TP=-1.5, LRA=11)
            
            if remove_silence:
                # Remove silence using silenceremove filter
                stream = ffmpeg.filter(stream, 'silenceremove', start_periods=1, start_duration=0.1, start_threshold='-50dB', stop_periods=-1, stop_duration=0.1, stop_threshold='-50dB')
            
            # Set output codec based on format
            codec_map = {
                "mp3": "libmp3lame",
                "m4a": "aac",
                "opus": "libopus",
                "wav": "pcm_s16le"
            }
            
            acodec = codec_map.get(audio_format, "libmp3lame")
            
            output_kwargs = {
                "vn": None,  # No video
                "acodec": acodec,
            }
            if audio_format != "wav":
                audio_bitrate = "192k" if audio_format == "mp3" else "128k"
                output_kwargs["audio_bitrate"] = audio_bitrate
            
            stream = ffmpeg.output(stream, str(output_path), **output_kwargs)
            
            ffmpeg.run(stream, overwrite_output=True, quiet=True)
            
            if not output_path.exists() or output_path.stat().st_size == 0:
                await bot_msg.edit_text("❌ Failed to extract audio")
                return
            
            await bot_msg.edit_text("📦 Creating ZIP archive...")
            
            # Rename audio to scoutbot1.{format}
            new_audio_name = output_path.parent / f"scoutbot1.{audio_format}"
            output_path.rename(new_audio_name)
            
            # Create ZIP file with standardized name
            zip_path = new_audio_name.parent / f"scoutbot{audio_format}.zip"
            if not create_zip_file(new_audio_name, zip_path, internal_filename=f"scoutbot1.{audio_format}"):
                await bot_msg.edit_text("❌ Failed to create ZIP file")
                return
            
            await bot_msg.edit_text("📤 Uploading ZIP file...")
            
            # Upload ZIP as document
            file = FSInputFile(zip_path, filename=zip_path.name)
            await bot.send_document(
                chat_id=message.chat.id,
                document=file,
                caption=f"Audio ({audio_format.upper()}) (ZIP)"
            )
            
            # Record conversion statistic
            await _record_conversion_stat(
                "audio", "success", message.chat.id,
                input_format="mp4", output_format=audio_format,
                file_size=new_audio_name.stat().st_size if new_audio_name.exists() else None,
            )
            
            await bot_msg.delete()
            
            # Cleanup
            try:
                new_audio_name.unlink()
                zip_path.unlink()
                if video_path.parent != Path(tempfile.gettempdir()):
                    video_path.unlink()
            except Exception:
                pass
                
        except Exception as e:
            logger.error(f"Audio command failed: {e}", exc_info=True)
            error_msg = str(e)
            if len(error_msg) > 500:
                error_msg = error_msg[:500] + "..."
            await bot_msg.edit_text(f"❌ Audio extraction failed: {error_msg}")
    
    logger.debug("✅ Media commands setup completed")
