"""Storage commands for managing Pentaract files"""

from pathlib import Path
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
import tempfile

from app.config import settings
from app.utils.logger import get_logger
from app.services.pentaract_storage_service import pentaract_storage
from app.utils.download_utils import sizeof_fmt

logger = get_logger(__name__)

router = Router()


@router.message(Command("storage"))
async def storage_command(message: Message):
    """Handle /storage command - upload file if attached, otherwise show subcommands"""
    # Check if Pentaract is enabled
    if not settings.pentaract_enabled:
        await message.reply("❌ Pentaract storage is not enabled.")
        return
    
    # Check if service is available
    if not await pentaract_storage.is_available():
        await message.reply("❌ Pentaract storage is currently unavailable.")
        return
    
    # Check if there's a document, photo, video, or audio attached
    if message.document:
        logger.info(f"Document detected: {message.document.file_name}")
        await handle_storage_upload(message)
        return
    elif message.photo:
        logger.info("Photo detected, converting to document")
        await message.reply("📸 For photos, please send as a file (not compressed image)")
        return
    elif message.video:
        logger.info("Video detected, converting to document")
        await message.reply("🎥 For videos, please send as a file (not compressed video)")
        return
    elif message.audio:
        logger.info("Audio detected, converting to document")
        await message.reply("🎵 For audio, please send as a file")
        return
    
    # Parse command arguments
    args = message.text.split()[1:] if message.text else []
    
    if not args:
        # Show brief help
        help_text = (
            "📦 <b>Storage</b>\n\n"
            "<b>Upload:</b> Send /storage with a file attached\n\n"
            "<b>Commands:</b>\n"
            "• <code>/storage list</code>\n"
            "• <code>/storage download &lt;code&gt;</code>\n"
            "• <code>/storage delete &lt;code&gt;</code>\n"
            "• <code>/storage stats</code>\n"
            "• <code>/storage info &lt;code&gt;</code>\n\n"
            "Use <code>/help storage</code> for more info"
        )
        await message.reply(help_text, parse_mode="HTML")
        return
    
    # Route to appropriate subcommand
    subcommand = args[0].lower()
    
    if subcommand == "list":
        await storage_list(message)
    elif subcommand == "download":
        if len(args) < 2:
            await message.reply("❌ Specify a code: <code>/storage download ABC123</code>", parse_mode="HTML")
            return
        file_code = args[1].upper()
        await storage_download(message, file_code)
    elif subcommand == "delete":
        if len(args) < 2:
            await message.reply("❌ Specify a code: <code>/storage delete ABC123</code>", parse_mode="HTML")
            return
        file_code = args[1].upper()
        await storage_delete(message, file_code)
    elif subcommand == "stats":
        await storage_stats(message)
    elif subcommand == "info":
        if len(args) < 2:
            await message.reply("❌ Specify a code: <code>/storage info ABC123</code>", parse_mode="HTML")
            return
        file_code = args[1].upper()
        await storage_info(message, file_code)
    elif subcommand == "cleanall":
        await storage_cleanall(message)
    else:
        await message.reply(f"❌ Unknown: {subcommand}", parse_mode="HTML")


async def handle_storage_upload(message: Message):
    """Handle file upload to Pentaract storage"""
    logger.info(f"handle_storage_upload called - document: {message.document is not None}")
    
    user_id = str(message.from_user.id)
    allowed_user_id = str(settings.allowed_user_id) if settings.allowed_user_id else None
    
    logger.info(f"User ID: {user_id}, Allowed: {allowed_user_id}")
    
    if allowed_user_id and user_id != allowed_user_id:
        await message.reply("❌ Unauthorized")
        return
    
    document = message.document
    file_name = document.file_name
    file_size = document.file_size
    
    logger.info(f"Uploading file: {file_name} ({sizeof_fmt(file_size)})")
    
    if file_size > 2 * 1024 * 1024 * 1024:
        await message.reply(f"❌ File too large: {sizeof_fmt(file_size)} (max: 2GB)")
        return
    
    from app.utils.file_security import validate_file_safety
    
    is_safe, reason = validate_file_safety(file_name)
    if not is_safe:
        await message.reply(f"❌ {reason}", parse_mode="HTML")
        return
    
    status_msg = await message.reply(f"⏳ Uploading {file_name}...")
    
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file_name).suffix) as tmp_file:
            tmp_path = Path(tmp_file.name)
        
        try:
            logger.info(f"Downloading to temp: {tmp_path}")
            
            # Get file info first
            file = await message.bot.get_file(document.file_id)
            logger.info(f"File path from API: {file.file_path}")
            
            # Check if using local Bot API and file is accessible locally
            if settings.telegram_use_local_api and file.file_path:
                # Try to access file directly from local Bot API storage
                local_file_path = Path("/var/lib/telegram-bot-api") / file.file_path
                logger.info(f"Trying local file path: {local_file_path}")
                
                if local_file_path.exists():
                    logger.info("File found locally, copying...")
                    import shutil
                    shutil.copy2(local_file_path, tmp_path)
                else:
                    logger.warning(f"Local file not found, falling back to HTTP download")
                    await message.bot.download_file(file.file_path, tmp_path)
            else:
                # Use standard download for cloud Bot API
                await message.bot.download_file(file.file_path, tmp_path)
            
            from app.services.upload_queue_service import upload_queue_service
            
            logger.info("Adding to upload queue...")
            upload_id, file_code, error = await upload_queue_service.add_to_queue(
                file_path=tmp_path,
                user_id=user_id,
                folder="storage"
            )
            
            if not upload_id:
                logger.error(f"Upload failed: {error}")
                await status_msg.edit_text(f"❌ Upload failed: {error}")
                return
            
            logger.info(f"Upload queued: {upload_id}, code: {file_code}")
            await status_msg.edit_text(
                f"✅ Uploaded!\n"
                f"📄 {file_name}\n"
                f"📊 {sizeof_fmt(file_size)}\n"
                f"🔖 Code: <code>{file_code}</code>",
                parse_mode="HTML"
            )
            # Don't delete temp file here - let the upload queue process it first
            # The cleanup service will handle deletion after upload completes
        except Exception as e:
            # Only delete on error
            if tmp_path.exists():
                tmp_path.unlink()
            raise
    
    except Exception as e:
        logger.error(f"Upload error: {e}", exc_info=True)
        await status_msg.edit_text("❌ Upload failed")


async def storage_list(message: Message):
    """List files in Pentaract storage with codes"""
    try:
        # Check if service is available
        if not await pentaract_storage.is_available():
            await message.reply(
                "❌ Pentaract storage service is currently unavailable.\n"
                "Please try again later."
            )
            return
        
        # Get user ID
        user_id = str(message.from_user.id)
        
        # Get files from database
        from app.database import database
        from app.models.pentaract_upload import PentaractUpload
        from sqlmodel import select
        
        try:
            with database.get_session() as session:
                statement = select(PentaractUpload).where(
                    PentaractUpload.user_id == user_id,
                    PentaractUpload.status == "completed"
                ).order_by(PentaractUpload.created_at.desc())
                
                files = session.exec(statement).all()
        except Exception as e:
            logger.error(f"Error querying files: {e}", exc_info=True)
            await message.reply(
                "❌ An error occurred while listing files.\n"
                "Please try again later."
            )
            return
        
        if not files:
            await message.reply(
                "📦 No files found in your storage.\n\n"
                "Upload files by downloading content with the bot.",
                parse_mode="HTML"
            )
            return
        
        # Format file list
        response = f"📦 <b>Your Storage</b>\n\n"
        
        total_size = 0
        for file_item in files:
            code = file_item.file_code
            name = file_item.original_filename
            size = file_item.file_size
            total_size += size
            uploaded_at = file_item.created_at
            
            # Format date
            date_str = ""
            if uploaded_at:
                try:
                    date_str = uploaded_at.strftime("%Y-%m-%d")
                except Exception:
                    pass
            
            response += f"📄 <code>{code}</code> - {name}\n"
            response += f"   💾 {sizeof_fmt(size)}"
            if date_str:
                response += f" • {date_str}"
            response += "\n\n"
        
        response += f"<b>Total:</b> {len(files)} files, {sizeof_fmt(total_size)}\n\n"
        response += "<i>Use </i><code>/storage download CODE</code><i> to download a file</i>"
        
        await message.reply(response, parse_mode="HTML")
    
    except Exception as e:
        logger.error(f"Error listing files: {e}", exc_info=True)
        await message.reply(
            "❌ An error occurred while listing files.\n"
            "Please try again later."
        )


async def storage_download(message: Message, file_code: str):
    """Download file from Pentaract storage by code"""
    try:
        # Check if service is available
        if not await pentaract_storage.is_available():
            await message.reply(
                "❌ Pentaract storage service is currently unavailable.\n"
                "Please try again later."
            )
            return
        
        # Get user ID
        user_id = str(message.from_user.id)
        
        # Find file by code
        from app.database import database
        from app.models.pentaract_upload import PentaractUpload
        from sqlmodel import select
        
        try:
            with database.get_session() as session:
                statement = select(PentaractUpload).where(
                    PentaractUpload.user_id == user_id,
                    PentaractUpload.file_code == file_code,
                    PentaractUpload.status == "completed"
                )
                file_record = session.exec(statement).first()
        except Exception as e:
            logger.error(f"Error querying file: {e}", exc_info=True)
            await message.reply(
                "❌ An error occurred while searching for the file.\n"
                "Please try again later."
            )
            return
        
        if not file_record:
            await message.reply(
                f"❌ File not found with code: <code>{file_code}</code>\n\n"
                f"Use <code>/storage list</code> to see your files.",
                parse_mode="HTML"
            )
            return
        
        # Send status message
        status_msg = await message.reply(
            f"⏳ Downloading <code>{file_record.original_filename}</code>...",
            parse_mode="HTML"
        )
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file_record.original_filename).suffix) as tmp_file:
            tmp_path = Path(tmp_file.name)
        
        try:
            # Download from Pentaract
            # Add folder prefix if not already present
            download_path = file_record.remote_path
            if not download_path.startswith("storage/"):
                download_path = f"storage/{download_path}"
            
            result = await pentaract_storage.download_file(
                remote_path=download_path,
                local_path=tmp_path
            )
            
            if not result.get("success"):
                error_msg = result.get("error", "Unknown error")
                await status_msg.edit_text(
                    f"❌ Failed to download file: {error_msg}",
                    parse_mode="HTML"
                )
                return
            
            # Send file to user
            await status_msg.edit_text(
                f"📤 Sending <code>{file_record.original_filename}</code>...",
                parse_mode="HTML"
            )
            
            file_size = tmp_path.stat().st_size
            file_input = FSInputFile(tmp_path, filename=file_record.original_filename)
            
            # Send as document
            await message.reply_document(
                document=file_input,
                caption=(
                    f"📦 Downloaded from storage\n"
                    f"🔖 Code: <code>{file_code}</code>\n"
                    f"📊 Size: {sizeof_fmt(file_size)}"
                ),
                parse_mode="HTML"
            )
            
            # Delete status message
            await status_msg.delete()
        
        finally:
            # Clean up temporary file
            if tmp_path.exists():
                tmp_path.unlink()
    
    except Exception as e:
        logger.error(f"Error downloading file: {e}", exc_info=True)
        await message.reply(
            "❌ An error occurred while downloading the file.\n"
            "Please try again later."
        )


async def storage_delete(message: Message, file_code: str):
    """Delete file from Pentaract storage by code with confirmation"""
    try:
        # Check if service is available
        if not await pentaract_storage.is_available():
            await message.reply(
                "❌ Pentaract storage service is currently unavailable.\n"
                "Please try again later."
            )
            return
        
        # Get user ID
        user_id = str(message.from_user.id)
        
        # Find file by code
        from app.database import database
        from app.models.pentaract_upload import PentaractUpload
        from sqlmodel import select
        
        try:
            with database.get_session() as session:
                statement = select(PentaractUpload).where(
                    PentaractUpload.user_id == user_id,
                    PentaractUpload.file_code == file_code,
                    PentaractUpload.status == "completed"
                )
                file_record = session.exec(statement).first()
        except Exception as e:
            logger.error(f"Error querying file: {e}", exc_info=True)
            await message.reply(
                "❌ An error occurred while searching for the file.\n"
                "Please try again later."
            )
            return
        
        if not file_record:
            await message.reply(
                f"❌ File not found with code: <code>{file_code}</code>\n\n"
                f"Use <code>/storage list</code> to see your files.",
                parse_mode="HTML"
            )
            return
        
        # Create confirmation buttons
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Yes, delete",
                    callback_data=f"storage_delete_confirm:{file_code}"
                ),
                InlineKeyboardButton(
                    text="❌ Cancel",
                    callback_data="storage_delete_cancel"
                )
            ]
        ])
        
        # Show confirmation
        await message.reply(
            f"⚠️ <b>Confirm Deletion</b>\n\n"
            f"Are you sure you want to delete this file?\n\n"
            f"🔖 Code: <code>{file_code}</code>\n"
            f"📄 Name: <code>{file_record.original_filename}</code>\n"
            f"📊 Size: {sizeof_fmt(file_record.file_size)}\n\n"
            f"<b>This action cannot be undone!</b>",
            parse_mode="HTML",
            reply_markup=keyboard
        )
    
    except Exception as e:
        logger.error(f"Error preparing delete: {e}", exc_info=True)
        await message.reply(
            "❌ An error occurred while preparing to delete the file.\n"
            "Please try again later."
        )


@router.callback_query(F.data.startswith("storage_delete_confirm:"))
async def storage_delete_confirm(callback: CallbackQuery):
    """Handle delete confirmation"""
    try:
        # Extract file code from callback data
        file_code = callback.data.split(":", 1)[1]
        
        # Get user ID
        user_id = str(callback.from_user.id)
        
        # Find file by code
        from app.database import database
        from app.models.pentaract_upload import PentaractUpload
        from sqlmodel import select
        
        try:
            with database.get_session() as session:
                statement = select(PentaractUpload).where(
                    PentaractUpload.user_id == user_id,
                    PentaractUpload.file_code == file_code,
                    PentaractUpload.status == "completed"
                )
                file_record = session.exec(statement).first()
                
                if not file_record:
                    await callback.message.edit_text(
                        f"❌ File not found with code: <code>{file_code}</code>",
                        parse_mode="HTML"
                    )
                    await callback.answer()
                    return
                
                # Delete file from Pentaract
                # Add folder prefix if not already present
                delete_path = file_record.remote_path
                if not delete_path.startswith("storage/"):
                    delete_path = f"storage/{delete_path}"
                
                success = await pentaract_storage.delete_file(delete_path)
                
                if success:
                    # Update database record
                    file_record.status = "deleted"
                    session.add(file_record)
                    session.commit()
                    
                    await callback.message.edit_text(
                        f"✅ File deleted successfully:\n"
                        f"🔖 Code: <code>{file_code}</code>\n"
                        f"📄 Name: <code>{file_record.original_filename}</code>",
                        parse_mode="HTML"
                    )
                else:
                    await callback.message.edit_text(
                        f"❌ Failed to delete file:\n"
                        f"🔖 Code: <code>{file_code}</code>",
                        parse_mode="HTML"
                    )
        except Exception as e:
            logger.error(f"Error in delete confirmation: {e}", exc_info=True)
            await callback.message.edit_text(
                "❌ An error occurred while deleting the file."
            )
        
        await callback.answer()
    
    except Exception as e:
        logger.error(f"Error deleting file: {e}", exc_info=True)
        await callback.message.edit_text(
            "❌ An error occurred while deleting the file."
        )
        await callback.answer()


@router.callback_query(F.data == "storage_delete_cancel")
async def storage_delete_cancel(callback: CallbackQuery):
    """Handle delete cancellation"""
    await callback.message.edit_text("❌ Deletion cancelled.")
    await callback.answer()


async def storage_stats(message: Message):
    """Show storage statistics"""
    try:
        # Check if service is available
        if not await pentaract_storage.is_available():
            await message.reply(
                "❌ Pentaract storage service is currently unavailable.\n"
                "Please try again later."
            )
            return
        
        # Get user ID
        user_id = str(message.from_user.id)
        
        # Get upload statistics from database
        from app.database import database
        from app.models.pentaract_upload import PentaractUpload
        from sqlmodel import select, func
        from datetime import datetime, timedelta
        
        try:
            with database.get_session() as session:
                # Total files (completed uploads)
                total_files = session.exec(
                    select(func.count(PentaractUpload.id)).where(
                        PentaractUpload.user_id == user_id,
                        PentaractUpload.status == "completed"
                    )
                ).first() or 0
                
                # Total size
                total_size = session.exec(
                    select(func.sum(PentaractUpload.file_size)).where(
                        PentaractUpload.user_id == user_id,
                        PentaractUpload.status == "completed"
                    )
                ).first() or 0
                
                # Total uploads (all statuses)
                total_uploads = session.exec(
                    select(func.count(PentaractUpload.id)).where(
                        PentaractUpload.user_id == user_id
                    )
                ).first() or 0
                
                # Successful uploads
                successful_uploads = session.exec(
                    select(func.count(PentaractUpload.id)).where(
                        PentaractUpload.user_id == user_id,
                        PentaractUpload.status == "completed"
                    )
                ).first() or 0
                
                # Uploads in last 24 hours
                yesterday = datetime.utcnow() - timedelta(hours=24)
                recent_uploads = session.exec(
                    select(func.count(PentaractUpload.id)).where(
                        PentaractUpload.user_id == user_id,
                        PentaractUpload.created_at >= yesterday
                    )
                ).first() or 0
                
                # Calculate success rate
                success_rate = (successful_uploads / total_uploads * 100) if total_uploads > 0 else 0
                
                # Calculate average upload time
                avg_time_query = session.exec(
                    select(
                        func.avg(
                            func.julianday(PentaractUpload.upload_completed_at) -
                            func.julianday(PentaractUpload.upload_started_at)
                        ) * 86400  # Convert days to seconds
                    ).where(
                        PentaractUpload.user_id == user_id,
                        PentaractUpload.status == "completed",
                        PentaractUpload.upload_started_at.isnot(None),
                        PentaractUpload.upload_completed_at.isnot(None)
                    )
                ).first()
                
                avg_upload_time = avg_time_query if avg_time_query else 0
        
        except Exception as e:
            logger.warning(f"Failed to get upload statistics: {e}")
            await message.reply(
                "❌ Failed to retrieve storage statistics.\n"
                "Please try again later."
            )
            return
        
        # Format response
        response = (
            "📊 <b>Storage Statistics</b>\n\n"
            f"📦 <b>Files:</b> {total_files}\n"
            f"💾 <b>Total Size:</b> {sizeof_fmt(total_size)}\n\n"
            f"📤 <b>Uploads (24h):</b> {recent_uploads}\n"
            f"✅ <b>Success Rate:</b> {success_rate:.1f}%\n"
        )
        
        if avg_upload_time and avg_upload_time > 0:
            response += f"⏱️ <b>Avg Upload Time:</b> {avg_upload_time:.1f}s\n"
        
        await message.reply(response, parse_mode="HTML")
    
    except Exception as e:
        logger.error(f"Error getting stats: {e}", exc_info=True)
        await message.reply(
            "❌ An error occurred while retrieving statistics.\n"
            "Please try again later."
        )


async def storage_info(message: Message, file_code: str):
    """Show file information by code"""
    try:
        # Check if service is available
        if not await pentaract_storage.is_available():
            await message.reply(
                "❌ Pentaract storage service is currently unavailable.\n"
                "Please try again later."
            )
            return
        
        # Get user ID
        user_id = str(message.from_user.id)
        
        # Find file by code
        from app.database import database
        from app.models.pentaract_upload import PentaractUpload
        from sqlmodel import select
        
        try:
            with database.get_session() as session:
                statement = select(PentaractUpload).where(
                    PentaractUpload.user_id == user_id,
                    PentaractUpload.file_code == file_code,
                    PentaractUpload.status == "completed"
                )
                file_record = session.exec(statement).first()
        except Exception as e:
            logger.error(f"Error querying file: {e}", exc_info=True)
            await message.reply(
                "❌ An error occurred while searching for the file.\n"
                "Please try again later."
            )
            return
        
        if not file_record:
            await message.reply(
                f"❌ File not found with code: <code>{file_code}</code>\n\n"
                f"Use <code>/storage list</code> to see your files.",
                parse_mode="HTML"
            )
            return
        
        # Format date
        date_str = "Unknown"
        if file_record.created_at:
            try:
                date_str = file_record.created_at.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                pass
        
        # Format response
        response = (
            f"📄 <b>File Information</b>\n\n"
            f"🔖 <b>Code:</b> <code>{file_code}</code>\n"
            f"📝 <b>Name:</b> <code>{file_record.original_filename}</code>\n"
            f"📊 <b>Size:</b> {sizeof_fmt(file_record.file_size)}\n"
            f"📦 <b>Type:</b> {file_record.mime_type or 'Unknown'}\n"
            f"📅 <b>Uploaded:</b> {date_str}\n\n"
            f"<i>Use </i><code>/storage download {file_code}</code><i> to download</i>"
        )
        
        await message.reply(response, parse_mode="HTML")
    
    except Exception as e:
        logger.error(f"Error getting file info: {e}", exc_info=True)
        await message.reply(
            "❌ An error occurred while retrieving file information.\n"
            "Please try again later."
        )


async def storage_cleanall(message: Message):
    """
    SECRET COMMAND: Delete ALL files from storage
    Only accessible by authorized user
    """
    try:
        # Check if user is authorized
        user_id = str(message.from_user.id)
        allowed_user_id = str(settings.allowed_user_id) if settings.allowed_user_id else None
        
        if not allowed_user_id or user_id != allowed_user_id:
            # Don't reveal the command exists to unauthorized users
            await message.reply(
                f"❌ Unknown subcommand: cleanall\n"
                "Use <code>/storage</code> to see available commands.",
                parse_mode="HTML"
            )
            return
        
        # Check if service is available
        if not await pentaract_storage.is_available():
            await message.reply(
                "❌ Pentaract storage service is currently unavailable.\n"
                "Please try again later."
            )
            return
        
        # Create confirmation buttons
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🗑️ YES, DELETE EVERYTHING",
                    callback_data="storage_cleanall_confirm"
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Cancel",
                    callback_data="storage_cleanall_cancel"
                )
            ]
        ])
        
        # Get current stats from database
        from app.database import database
        from app.models.pentaract_upload import PentaractUpload
        from sqlmodel import select, func
        
        try:
            with database.get_session() as session:
                statement = select(func.count(PentaractUpload.id)).where(
                    PentaractUpload.user_id == user_id,
                    PentaractUpload.status == "completed"
                )
                total_files = session.exec(statement).first() or 0
                
                statement = select(func.sum(PentaractUpload.file_size)).where(
                    PentaractUpload.user_id == user_id,
                    PentaractUpload.status == "completed"
                )
                total_size = session.exec(statement).first() or 0
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            total_files = 0
            total_size = 0
        
        # Show confirmation
        await message.reply(
            f"⚠️ <b>DANGER: DELETE ALL FILES</b>\n\n"
            f"This will permanently delete ALL files from your Pentaract storage:\n\n"
            f"📦 <b>Files to delete:</b> {total_files}\n"
            f"💾 <b>Total size:</b> {sizeof_fmt(total_size)}\n\n"
            f"<b>⚠️ THIS ACTION CANNOT BE UNDONE!</b>\n\n"
            f"Are you absolutely sure?",
            parse_mode="HTML",
            reply_markup=keyboard
        )
    
    except Exception as e:
        logger.error(f"Error preparing cleanall: {e}", exc_info=True)
        await message.reply(
            "❌ An error occurred while preparing to clean storage.\n"
            "Please try again later."
        )


@router.callback_query(F.data == "storage_cleanall_confirm")
async def storage_cleanall_confirm(callback: CallbackQuery):
    """Handle cleanall confirmation"""
    try:
        # Double-check authorization
        user_id = str(callback.from_user.id)
        allowed_user_id = str(settings.allowed_user_id) if settings.allowed_user_id else None
        
        if not allowed_user_id or user_id != allowed_user_id:
            await callback.answer("❌ Unauthorized", show_alert=True)
            return
        
        # Update message to show progress
        await callback.message.edit_text(
            "🗑️ <b>Deleting all files...</b>\n\n"
            "This may take a while. Please wait...",
            parse_mode="HTML"
        )
        
        # Get all files from database
        from app.database import database
        from app.models.pentaract_upload import PentaractUpload
        from sqlmodel import select
        
        try:
            with database.get_session() as session:
                statement = select(PentaractUpload).where(
                    PentaractUpload.user_id == user_id,
                    PentaractUpload.status == "completed"
                )
                files = session.exec(statement).all()
                
                if not files:
                    await callback.message.edit_text(
                        "✅ Storage is already empty.\n"
                        "No files to delete."
                    )
                    await callback.answer()
                    return
                
                # Delete all files
                deleted_count = 0
                failed_count = 0
                
                for file_record in files:
                    # Add folder prefix if not already present
                    delete_path = file_record.remote_path
                    if not delete_path.startswith("storage/"):
                        delete_path = f"storage/{delete_path}"
                    
                    success = await pentaract_storage.delete_file(delete_path)
                    if success:
                        # Update database record
                        file_record.status = "deleted"
                        session.add(file_record)
                        deleted_count += 1
                    else:
                        failed_count += 1
                
                # Commit all changes
                session.commit()
        except Exception as e:
            logger.error(f"Error in cleanall: {e}", exc_info=True)
            await callback.message.edit_text(
                "❌ An error occurred while cleaning storage.\n"
                "Some files may have been deleted."
            )
            await callback.answer("❌ Error occurred", show_alert=True)
            return
        
        # Show result
        result_text = f"✅ <b>Storage Cleaned</b>\n\n"
        result_text += f"🗑️ <b>Deleted:</b> {deleted_count} files\n"
        
        if failed_count > 0:
            result_text += f"❌ <b>Failed:</b> {failed_count} files\n"
        
        result_text += f"\n📦 Your storage is now {'empty' if failed_count == 0 else 'mostly empty'}."
        
        await callback.message.edit_text(result_text, parse_mode="HTML")
        await callback.answer("✅ Storage cleaned successfully")
        
        logger.warning(
            f"User {user_id} executed CLEANALL command: "
            f"deleted {deleted_count} files, {failed_count} failed"
        )
    
    except Exception as e:
        logger.error(f"Error executing cleanall: {e}", exc_info=True)
        await callback.message.edit_text(
            "❌ An error occurred while cleaning storage.\n"
            "Some files may have been deleted."
        )
        await callback.answer("❌ Error occurred", show_alert=True)


@router.callback_query(F.data == "storage_cleanall_cancel")
async def storage_cleanall_cancel(callback: CallbackQuery):
    """Handle cleanall cancellation"""
    await callback.message.edit_text(
        "✅ Operation cancelled.\n"
        "No files were deleted."
    )
    await callback.answer("Cancelled")
