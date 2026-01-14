"""OCR commands using Tesseract"""

import tempfile
from pathlib import Path
from typing import Optional

from aiogram import Bot, Dispatcher
from aiogram.types import Message, FSInputFile
from aiogram.filters import Command

from app.config import settings
from app.utils.logger import get_logger
from app.utils.file_downloader import download_telegram_file

logger = get_logger(__name__)


def check_tesseract_available() -> bool:
    """Check if Tesseract OCR is available"""
    import shutil
    return shutil.which("tesseract") is not None


def setup_ocr_commands(dp: Optional[Dispatcher], bot: Optional[Bot]):
    """Setup OCR commands"""
    if not dp or not bot:
        return
    
    @dp.message(Command("ocr"))
    async def ocr_command(message: Message):
        """Extract text from image using OCR"""
        if not settings.enable_ocr:
            await message.answer(
                "❌ <b>OCR is disabled.</b>\n\n"
                "Please set ENABLE_OCR=true in your configuration."
            )
            return
        
        if not check_tesseract_available():
            await message.answer(
                "❌ <b>Tesseract OCR not available.</b>\n\n"
                "OCR requires Tesseract to be installed."
            )
            return
        
        # Check if message has a photo/document attached
        if not message.photo and not message.document:
            await message.answer(
                "❌ <b>No image attached.</b>\n\n"
                "Please send an image and use /ocr as a reply, "
                "or send /ocr with an image attached."
            )
            return
        
        bot_msg = await message.answer("📥 Processing image...")
        
        try:
            import pytesseract
            from PIL import Image
            import subprocess
            
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
                
                # Download file using utility function
                success = await download_telegram_file(bot, file_info, input_path)
                if not success:
                    await bot_msg.edit_text("❌ Failed to download image")
                    return
                
                await bot_msg.edit_text("🔍 Extracting text...")
                
                # Preprocess image for better OCR results
                image = Image.open(input_path)
                
                # Convert to RGB if needed
                if image.mode != 'RGB':
                    image = image.convert('RGB')
                
                # Enhance image for OCR (optional preprocessing)
                # Could add: deskew, denoise, enhance contrast, etc.
                
                # Perform OCR
                lang = settings.tesseract_lang or "por+eng"
                try:
                    text = pytesseract.image_to_string(image, lang=lang)
                except Exception as e:
                    # Fallback to English if language not available
                    logger.warning(f"OCR with {lang} failed, trying English: {e}")
                    text = pytesseract.image_to_string(image, lang="eng")
                
                if not text or not text.strip():
                    await bot_msg.edit_text("❌ No text found in image")
                    return
                
                # Clean up text
                text = text.strip()
                
                # Limit text length for Telegram message (4096 characters)
                if len(text) > 4000:
                    text = text[:4000] + "\n\n... (truncated)"
                
                await bot_msg.edit_text("📤 Sending extracted text...")
                
                # Send as text message
                await bot.send_message(
                    chat_id=message.chat.id,
                    text=f"📝 <b>Extracted Text:</b>\n\n<code>{text}</code>",
                    parse_mode="HTML"
                )
                
                await bot_msg.delete()
                
        except Exception as e:
            logger.error(f"OCR command failed: {e}", exc_info=True)
            error_msg = str(e)
            if len(error_msg) > 500:
                error_msg = error_msg[:500] + "..."
            await bot_msg.edit_text(f"❌ OCR failed: {error_msg}")
    
    logger.debug("✅ OCR commands setup completed")
