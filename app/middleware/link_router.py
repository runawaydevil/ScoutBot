"""Link detection middleware for automatic action suggestions"""

import re
from typing import Any, Dict, Callable, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command

from app.utils.logger import get_logger
from app.utils.download_utils import detect_downloader_type

logger = get_logger(__name__)

# URL pattern
URL_PATTERN = re.compile(
    r'https?://(?:[-\w.])+(?:[:\d]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:#(?:\w)*)?)?',
    re.IGNORECASE
)


class LinkRouterMiddleware(BaseMiddleware):
    """Middleware to detect URLs and offer action buttons"""
    
    def __init__(self):
        super().__init__()
        self.enabled = True  # Can be controlled via settings
    
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        """Process message and detect URLs"""
        
        # Skip if message is a command
        if event.text and event.text.startswith('/'):
            return await handler(event, data)
        
        # Skip if middleware is disabled
        if not self.enabled:
            return await handler(event, data)
        
        # Check if message contains URLs
        if not event.text:
            return await handler(event, data)
        
        urls = URL_PATTERN.findall(event.text)
        if not urls:
            return await handler(event, data)
        
        # Get first URL
        url = urls[0]
        
        # Detect downloader type
        downloader_type = detect_downloader_type(url)
        
        # Skip if not a supported URL
        if downloader_type == "direct" and not url.startswith(('http://', 'https://')):
            return await handler(event, data)
        
        # Create inline keyboard with actions
        keyboard_buttons = []
        
        # Common actions for all URLs
        keyboard_buttons.append([
            InlineKeyboardButton(text="📥 Download", callback_data=f"action:download:{url}")
        ])
        
        # Audio action (for video URLs)
        if downloader_type in ["youtube", "direct"]:
            keyboard_buttons.append([
                InlineKeyboardButton(text="🎵 Audio (MP3)", callback_data=f"action:audio:{url}")
            ])
        
        # Media actions (for video URLs)
        if downloader_type in ["youtube", "direct"]:
            keyboard_buttons.append([
                InlineKeyboardButton(text="✂️ Clip", callback_data=f"action:clip:{url}"),
                InlineKeyboardButton(text="🎬 GIF", callback_data=f"action:gif:{url}")
            ])
        
        # Info action
        keyboard_buttons.append([
            InlineKeyboardButton(text="ℹ️ Info", callback_data=f"action:info:{url}")
        ])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        
        # Send message with action buttons (don't block handler, just add suggestion)
        try:
            # Use reply to the original message
            await event.reply(
                f"🔗 <b>Link detected:</b> {url[:50]}{'...' if len(url) > 50 else ''}\n\n"
                "Choose an action:",
                reply_markup=keyboard
            )
        except Exception as e:
            logger.error(f"Failed to send link router message: {e}")
        
        # Continue with normal handler
        return await handler(event, data)
