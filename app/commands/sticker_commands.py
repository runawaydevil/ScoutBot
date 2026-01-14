"""Sticker factory commands using ImageMagick"""

import tempfile
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


def check_imagemagick_available() -> bool:
    """Check if ImageMagick is available"""
    import shutil
    return shutil.which("convert") is not None or shutil.which("magick") is not None


def setup_sticker_commands(dp: Optional[Dispatcher], bot: Optional[Bot]):
    """Setup sticker factory commands"""
    if not dp or not bot:
        return
    
    @dp.message(Command("sticker"))
    async def sticker_command(message: Message):
        """Convert image to Telegram sticker"""
        # Check flag first (must respect configuration)
        if not settings.enable_imagemagick:
            await message.answer(
                "❌ <b>ImageMagick is disabled.</b>\n\n"
                "Sticker conversion requires ImageMagick to be enabled.\n"
                "Please set ENABLE_IMAGEMAGICK=true in your configuration."
            )
            return
        
        if not settings.enable_stickers:
            await message.answer(
                "❌ <b>Sticker factory is disabled.</b>\n\n"
                "Please set ENABLE_STICKERS=true in your configuration."
            )
            return
        
        # Check availability after flag check
        if not check_imagemagick_available():
            await message.answer(
                "❌ <b>ImageMagick not available.</b>\n\n"
                "Sticker conversion requires ImageMagick to be installed."
            )
            return
        
        # Check if message has a photo/document attached
        if not message.photo and not message.document:
            await message.answer(
                "❌ <b>No image attached.</b>\n\n"
                "Please send an image and use /sticker as a reply, "
                "or send /sticker with an image attached."
            )
            return
        
        bot_msg = await message.answer("📥 Processing image...")
        
        try:
            import subprocess
            import shutil
            
            # Download image
            if message.photo:
                file_info = await bot.get_file(message.photo[-1].file_id)
            elif message.document:
                file_info = await bot.get_file(message.document.file_id)
            else:
                await bot_msg.edit_text("❌ Failed to get file")
                return
            
            # Create temporary directory
            with tempfile.TemporaryDirectory() as tempdir:
                input_path = Path(tempdir) / "input_image"
                output_path = Path(tempdir) / "sticker.webp"
                
                # Download file using utility function
                success = await download_telegram_file(bot, file_info, input_path)
                if not success:
                    await bot_msg.edit_text("❌ Failed to download image")
                    return
                
                await bot_msg.edit_text("🎨 Converting to sticker...")
                
                # Use ImageMagick to convert to sticker
                # Telegram stickers: 512x512, WebP format, <512KB
                # Steps: resize, add padding if needed, convert to WebP
                
                # Check if magick (ImageMagick 7) or convert (ImageMagick 6) is available
                magick_cmd = shutil.which("magick") or shutil.which("convert")
                if not magick_cmd:
                    await bot_msg.edit_text("❌ ImageMagick command not found")
                    return
                
                # Resize to 512x512 while maintaining aspect ratio, add padding if needed
                # Then convert to WebP
                cmd = [
                    magick_cmd,
                    str(input_path),
                    "-resize", "512x512>",  # Resize to fit within 512x512, maintain aspect
                    "-background", "transparent",
                    "-gravity", "center",
                    "-extent", "512x512",  # Extend to exactly 512x512 with transparent padding
                    "-quality", "85",  # WebP quality (adjust to meet size limit)
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
                    await bot_msg.edit_text(f"❌ Conversion failed: {result.stderr[:200]}")
                    return
                
                if not output_path.exists() or output_path.stat().st_size == 0:
                    await bot_msg.edit_text("❌ Failed to create sticker")
                    return
                
                # Check file size (Telegram limit: 512KB for stickers)
                max_size = 512 * 1024  # 512KB
                if output_path.stat().st_size > max_size:
                    # Try with lower quality
                    await bot_msg.edit_text("🎨 Optimizing sticker size...")
                    cmd = [
                        magick_cmd,
                        str(input_path),
                        "-resize", "512x512>",
                        "-background", "transparent",
                        "-gravity", "center",
                        "-extent", "512x512",
                        "-quality", "75",  # Lower quality
                        str(output_path)
                    ]
                    subprocess.run(cmd, capture_output=True, timeout=30)
                    
                    if output_path.stat().st_size > max_size:
                        await bot_msg.edit_text(
                            f"❌ <b>Sticker too large.</b>\n\n"
                            f"Generated sticker is {output_path.stat().st_size / 1024:.1f}KB, "
                            f"maximum is 512KB.\n"
                            f"Try a simpler image or reduce image complexity."
                        )
                        return
                
                await bot_msg.edit_text("📦 Creating ZIP archive...")
                
                # Rename sticker to scoutbot1.webp
                new_sticker_name = output_path.parent / "scoutbot1.webp"
                output_path.rename(new_sticker_name)
                
                # Create ZIP file with standardized name
                zip_path = new_sticker_name.parent / "scoutbotsticker.zip"
                if not create_zip_file(new_sticker_name, zip_path, internal_filename="scoutbot1.webp"):
                    await bot_msg.edit_text("❌ Failed to create ZIP file")
                    return
                
                await bot_msg.edit_text("📤 Uploading ZIP file...")
                
                # Upload ZIP as document
                file = FSInputFile(zip_path, filename=zip_path.name)
                await bot.send_document(
                    chat_id=message.chat.id,
                    document=file,
                    caption="Sticker (ZIP): Ready! Add to your sticker pack."
                )
                
                await bot_msg.delete()
                
        except Exception as e:
            logger.error(f"Sticker command failed: {e}", exc_info=True)
            error_msg = str(e)
            if len(error_msg) > 500:
                error_msg = error_msg[:500] + "..."
            await bot_msg.edit_text(f"❌ Sticker conversion failed: {error_msg}")
    
    logger.debug("✅ Sticker commands setup completed")
