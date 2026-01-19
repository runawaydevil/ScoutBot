"""Commands module initialization"""

from typing import Optional
from aiogram import Dispatcher, Bot

from app.commands.feed_commands import setup_feed_commands
from app.commands.download_commands import setup_download_commands
from app.commands.media_commands import setup_media_commands
from app.commands.sticker_commands import setup_sticker_commands
from app.commands.meme_commands import setup_meme_commands
from app.commands.ocr_commands import setup_ocr_commands
from app.commands.image_commands import setup_image_commands
from app.commands.storage_commands import router as storage_router
from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def setup_commands(dp: Optional[Dispatcher], bot: Optional[Bot]):
    """Setup all bot commands"""
    if not dp:
        return

    try:
        # Setup feed commands
        await setup_feed_commands(dp, bot)
        # Setup download commands
        await setup_download_commands(dp, bot)
        # Setup media commands
        setup_media_commands(dp, bot)
        # Setup sticker commands
        setup_sticker_commands(dp, bot)
        # Setup meme commands
        setup_meme_commands(dp, bot)
        # Setup OCR commands
        setup_ocr_commands(dp, bot)
        # Setup image conversion commands
        setup_image_commands(dp, bot)
        # Setup storage commands (always register, check availability at runtime)
        dp.include_router(storage_router)
        if settings.pentaract_enabled:
            logger.debug("✅ Storage commands registered (Pentaract enabled)")
        else:
            logger.debug("✅ Storage commands registered (Pentaract disabled - will show info message)")
        logger.debug("✅ Commands setup completed")
    except Exception as e:
        logger.error(f"Failed to setup commands: {e}")
        raise
