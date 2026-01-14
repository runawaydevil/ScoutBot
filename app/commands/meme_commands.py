"""Meme generator commands using ImageMagick"""

import tempfile
import subprocess
import shutil
from pathlib import Path
from typing import Optional

from aiogram import Bot, Dispatcher
from aiogram.types import Message, FSInputFile
from aiogram.filters import Command

from app.config import settings
from app.utils.logger import get_logger
from app.utils.file_downloader import download_telegram_file
from app.utils.zip_utils import create_zip_file

logger = get_logger(__name__)


def setup_meme_commands(dp: Optional[Dispatcher], bot: Optional[Bot]):
    """Setup meme generator commands"""
    if not dp or not bot:
        return
    
    @dp.message(Command("meme"))
    async def meme_command(message: Message):
        """Create meme from image with text"""
        # Check flag first (must respect configuration)
        if not settings.enable_imagemagick:
            await message.answer(
                "❌ <b>ImageMagick is disabled.</b>\n\n"
                "Meme generation requires ImageMagick to be enabled.\n"
                "Please set ENABLE_IMAGEMAGICK=true in your configuration."
            )
            return
        
        if not settings.enable_memes:
            await message.answer(
                "❌ <b>Meme generator is disabled.</b>\n\n"
                "Please set ENABLE_MEMES=true in your configuration."
            )
            return
        
        # Check availability after flag check
        if not check_imagemagick_available():
            await message.answer("❌ <b>ImageMagick not available.</b>")
            return
        
        message_text = message.text or ""
        parts = message_text.split()
        
        # Check if message has image and text
        has_image = message.photo or message.document
        has_text = len(parts) >= 2
        
        if not has_image and not has_text:
            await message.answer(
                "❌ <b>Invalid syntax.</b>\n\n"
                "Usage: /meme &lt;top_text&gt; &lt;bottom_text&gt; (reply to image)\n"
                "       /meme &lt;image&gt; &lt;top_text&gt; &lt;bottom_text&gt;\n\n"
                "Example: /meme Top Text Bottom Text (with image attached)"
            )
            return
        
        # Parse text
        if has_image:
            # Text is in command (parts[1:])
            if len(parts) < 3:
                await message.answer(
                    "❌ <b>Missing text.</b>\n\n"
                    "Please provide both top and bottom text:\n"
                    "/meme Top Text Bottom Text"
                )
                return
            # Find where text starts (after /meme)
            text_parts = parts[1:]
            # Try to split into top and bottom (split by "|" or take first/last)
            if "|" in " ".join(text_parts):
                top_text = " ".join(text_parts[:text_parts.index("|")])
                bottom_text = " ".join(text_parts[text_parts.index("|")+1:])
            else:
                # Split in half
                mid = len(text_parts) // 2
                top_text = " ".join(text_parts[:mid])
                bottom_text = " ".join(text_parts[mid:])
        else:
            await message.answer("❌ <b>No image provided.</b> Please attach an image.")
            return
        
        bot_msg = await message.answer("📥 Processing image...")
        
        try:
            # Download image
            if message.photo:
                file_info = await bot.get_file(message.photo[-1].file_id)
            elif message.document:
                file_info = await bot.get_file(message.document.file_id)
            else:
                await bot_msg.edit_text("❌ Failed to get file")
                return
            
            with tempfile.TemporaryDirectory() as tempdir:
                input_path = Path(tempdir) / "input_image"
                output_path = Path(tempdir) / "meme.jpg"
                
                # Download file using utility function
                success = await download_telegram_file(bot, file_info, input_path)
                if not success:
                    await bot_msg.edit_text("❌ Failed to download image")
                    return
                
                await bot_msg.edit_text("🎨 Creating meme...")
                
                # Use ImageMagick to add text
                magick_cmd = shutil.which("magick") or shutil.which("convert")
                if not magick_cmd:
                    await bot_msg.edit_text("❌ ImageMagick command not found")
                    return
                
                # Create meme with text overlay
                # Top text: white, bold, large font, with black outline
                # Bottom text: same style
                cmd = [
                    magick_cmd,
                    str(input_path),
                    "-gravity", "North",
                    "-font", "Arial-Bold",
                    "-pointsize", "48",
                    "-fill", "white",
                    "-stroke", "black",
                    "-strokewidth", "3",
                    f"label:{top_text}",
                    "-gravity", "South",
                    f"label:{bottom_text}",
                    "-append",  # Combine image and text
                    str(output_path)
                ]
                
                # Simpler approach: overlay text on image
                # Get image dimensions first
                probe_cmd = [magick_cmd, "identify", "-format", "%wx%h", str(input_path)]
                probe_result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=10)
                
                if probe_result.returncode == 0:
                    dimensions = probe_result.stdout.strip()
                    width = int(dimensions.split('x')[0])
                    height = int(dimensions.split('x')[1])
                    
                    # Calculate font size based on image width
                    font_size = max(24, min(72, width // 15))
                    
                    # Create meme with text annotations
                    cmd = [
                        magick_cmd,
                        str(input_path),
                        "-gravity", "North",
                        "-font", "Arial-Bold",
                        "-pointsize", str(font_size),
                        "-fill", "white",
                        "-stroke", "black",
                        "-strokewidth", "2",
                        "-annotate", "+0+20", top_text,
                        "-gravity", "South",
                        "-annotate", "+0+20", bottom_text,
                        str(output_path)
                    ]
                else:
                    # Fallback: simple text overlay
                    cmd = [
                        magick_cmd,
                        str(input_path),
                        "-gravity", "North",
                        "-pointsize", "48",
                        "-fill", "white",
                        "-stroke", "black",
                        "-strokewidth", "2",
                        "-annotate", "+0+20", top_text,
                        "-gravity", "South",
                        "-annotate", "+0+20", bottom_text,
                        str(output_path)
                    ]
                
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if result.returncode != 0:
                    logger.error(f"ImageMagick error: {result.stderr}")
                    # Try simpler command
                    cmd = [
                        magick_cmd,
                        str(input_path),
                        "-gravity", "North",
                        "-pointsize", "36",
                        "-fill", "white",
                        "-annotate", "+0+10", top_text,
                        "-gravity", "South",
                        "-annotate", "+0+10", bottom_text,
                        str(output_path)
                    ]
                    result = subprocess.run(cmd, capture_output=True, timeout=30)
                    
                    if result.returncode != 0:
                        await bot_msg.edit_text(f"❌ Meme creation failed: {result.stderr[:200] if hasattr(result, 'stderr') else 'Unknown error'}")
                        return
                
                if not output_path.exists() or output_path.stat().st_size == 0:
                    await bot_msg.edit_text("❌ Failed to create meme")
                    return
                
                await bot_msg.edit_text("📦 Creating ZIP archive...")
                
                # Rename meme to scoutbot1.jpg
                new_meme_name = output_path.parent / "scoutbot1.jpg"
                output_path.rename(new_meme_name)
                
                # Create ZIP file with standardized name
                zip_path = new_meme_name.parent / "scoutbotmeme.zip"
                if not create_zip_file(new_meme_name, zip_path, internal_filename="scoutbot1.jpg"):
                    await bot_msg.edit_text("❌ Failed to create ZIP file")
                    return
                
                await bot_msg.edit_text("📤 Uploading ZIP file...")
                
                # Upload ZIP as document
                file = FSInputFile(zip_path, filename=zip_path.name)
                await bot.send_document(
                    chat_id=message.chat.id,
                    document=file,
                    caption=f"Meme (ZIP): {top_text}\n{bottom_text}"
                )
                
                await bot_msg.delete()
                
        except Exception as e:
            logger.error(f"Meme command failed: {e}", exc_info=True)
            error_msg = str(e)
            if len(error_msg) > 500:
                error_msg = error_msg[:500] + "..."
            await bot_msg.edit_text(f"❌ Meme creation failed: {error_msg}")
    
    logger.debug("✅ Meme commands setup completed")


def check_imagemagick_available() -> bool:
    """Check if ImageMagick is available"""
    return shutil.which("convert") is not None or shutil.which("magick") is not None
