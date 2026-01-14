"""Image format conversion commands"""

import tempfile
from pathlib import Path
from typing import Optional, List

from aiogram import Bot, Dispatcher
from aiogram.types import Message, FSInputFile
from aiogram.filters import Command

from app.config import settings
from app.utils.logger import get_logger
from app.utils.image_converter import (
    convert_image_format,
    is_format_supported,
    normalize_format
)
from app.utils.file_downloader import download_telegram_file
from app.utils.zip_utils import create_zip_file, create_zip_from_files

logger = get_logger(__name__)


def setup_image_commands(dp: Optional[Dispatcher], bot: Optional[Bot]):
    """Setup image conversion commands"""
    if not dp or not bot:
        return
    
    @dp.message(Command("convert"))
    async def convert_command(message: Message):
        """Convert image to specified format"""
        # Check both message.text and message.caption (for photos with caption)
        message_text = message.text or message.caption or ""
        parts = message_text.split()
        
        if len(parts) < 2:
            await message.answer(
                "❌ <b>Invalid syntax.</b>\n\n"
                "Usage: /convert &lt;format&gt;\n\n"
                "Supported formats: PNG, JPG, JPEG, WEBP, BMP, GIF, ICO\n\n"
                "Examples:\n"
                "• /convert webp (with image attached)\n"
                "• /convert png (with image attached)\n"
                "• /convert jpg (with image attached)"
            )
            return
        
        format_str = parts[1].lower()
        
        # Validate format
        if not is_format_supported(format_str):
            await message.answer(
                f"❌ <b>Unsupported format: {format_str}</b>\n\n"
                "Supported formats: PNG, JPG, JPEG, WEBP, BMP, GIF, ICO"
            )
            return
        
        # Collect all images (support batch processing up to 20 images)
        image_files: List = []
        
        # Check if image is attached to current message
        if message.photo:
            # If multiple photos in album, get all
            image_files.extend(message.photo)
        elif message.document:
            mime_type = message.document.mime_type or ""
            if mime_type.startswith("image/"):
                image_files.append(message.document)
        
        # Check if replying to a message with image(s)
        if message.reply_to_message:
            reply = message.reply_to_message
            if reply.photo:
                image_files.extend(reply.photo)
            elif reply.document:
                mime_type = reply.document.mime_type or ""
                if mime_type.startswith("image/"):
                    image_files.append(reply.document)
        
        if not image_files:
            await message.answer(
                "❌ <b>No image attached.</b>\n\n"
                "Please send an image and use /convert as a reply, "
                "or send /convert &lt;format&gt; with an image attached.\n\n"
                "<b>Batch support:</b> Send up to 20 images to convert them all at once."
            )
            return
        
        # Limit to 20 images for batch processing
        if len(image_files) > 20:
            image_files = image_files[:20]
            await message.answer(f"⚠️ Limiting to 20 images (received {len(image_files)}). Processing first 20...")
        
        is_batch = len(image_files) > 1
        bot_msg = await message.answer(
            f"📥 Processing {len(image_files)} image{'s' if is_batch else ''}..."
        )
        
        try:
            with tempfile.TemporaryDirectory() as tempdir:
                converted_files: List[Path] = []
                temp_dir = Path(tempdir)
                
                # Process each image
                for idx, image_file in enumerate(image_files):
                    try:
                        # Update progress for batch
                        if is_batch:
                            await bot_msg.edit_text(
                                f"📥 Processing image {idx + 1}/{len(image_files)}..."
                            )
                        
                        # Download image
                        file_info = await bot.get_file(image_file.file_id)
                        input_path = temp_dir / f"input_{idx}.tmp"
                        output_path = temp_dir / f"converted_{idx}.{normalize_format(format_str)}"
                        
                        # Use utility function that handles both local and cloud Bot API
                        success = await download_telegram_file(bot, file_info, input_path)
                        if not success:
                            logger.warning(f"Failed to download image {idx + 1}")
                            continue
                        
                        # Convert image
                        converted_path = convert_image_format(
                            input_path,
                            format_str,
                            output_path,
                            quality=95
                        )
                        
                        if converted_path and converted_path.exists():
                            # Rename to scoutbot{num}.{format}
                            normalized_format = normalize_format(format_str)
                            new_name = temp_dir / f"scoutbot{len(converted_files) + 1}.{normalized_format}"
                            converted_path.rename(new_name)
                            converted_files.append(new_name)
                        else:
                            logger.warning(f"Failed to convert image {idx + 1}")
                    except Exception as e:
                        logger.error(f"Error processing image {idx + 1}: {e}")
                        continue
                
                if not converted_files:
                    await bot_msg.edit_text("❌ Failed to convert any images")
                    return
                
                await bot_msg.edit_text(f"📦 Creating ZIP archive...")
                
                # Create ZIP file with standardized names
                normalized_format = normalize_format(format_str)
                zip_path = temp_dir / f"scoutbot{normalized_format}.zip"
                
                # Generate internal names for files in ZIP
                internal_names = [f.name for f in converted_files]  # scoutbot1.png, scoutbot2.png, etc.
                
                if is_batch:
                    # Batch: create single ZIP with all converted images
                    if not create_zip_from_files(converted_files, zip_path, internal_names=internal_names):
                        await bot_msg.edit_text("❌ Failed to create ZIP file")
                        return
                    caption = f"Batch conversion: {len(converted_files)} images converted to {format_str.upper()} (ZIP)"
                else:
                    # Single: create ZIP with single converted image
                    if not create_zip_file(converted_files[0], zip_path, internal_filename=internal_names[0]):
                        await bot_msg.edit_text("❌ Failed to create ZIP file")
                        return
                    caption = f"Converted to {format_str.upper()} (ZIP)"
                
                await bot_msg.edit_text("📤 Uploading ZIP file...")
                
                # Upload ZIP as document
                file = FSInputFile(zip_path, filename=zip_path.name)
                await bot.send_document(
                    chat_id=message.chat.id,
                    document=file,
                    caption=caption
                )
                
                # Record conversion statistic
                try:
                    from app.services.statistics_service import statistics_service
                    chat_id = str(message.chat.id)
                    for converted_file in converted_files:
                        input_ext = converted_file.suffix.lower().replace(".", "")
                        await statistics_service.record_conversion(
                            conversion_type="convert",
                            status="success",
                            chat_id=chat_id,
                            input_format=input_ext,
                            output_format=normalized_format,
                            file_size=converted_file.stat().st_size if converted_file.exists() else None,
                        )
                except Exception as e:
                    logger.debug(f"Failed to record conversion statistic: {e}")
                
                await bot_msg.delete()
                
        except Exception as e:
            logger.error(f"Convert command failed: {e}", exc_info=True)
            # Record failed conversion
            try:
                from app.services.statistics_service import statistics_service
                chat_id = str(message.chat.id)
                await statistics_service.record_conversion(
                    conversion_type="convert",
                    status="failed",
                    chat_id=chat_id,
                    error_message=str(e)[:200],
                )
            except Exception:
                pass
            
            error_msg = str(e)
            if len(error_msg) > 500:
                error_msg = error_msg[:500] + "..."
            await bot_msg.edit_text(f"❌ Conversion failed: {error_msg}")
    
    logger.debug("✅ Image conversion commands setup completed")
