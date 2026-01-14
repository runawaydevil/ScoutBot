"""Bot service using aiogram"""

from typing import Optional, Dict, Any
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, BotCommand, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer

from app.config import settings
from app.utils.logger import get_logger
from app.database import database
from app.commands import setup_commands
from app.services.bot_state_service import bot_state_service
from app.scheduler import scheduler

logger = get_logger(__name__)


class BotService:
    """Bot service for Telegram bot using aiogram"""

    def __init__(self):
        self.bot: Optional[Bot] = None
        self.dp: Optional[Dispatcher] = None
        self.bot_username: Optional[str] = None
        self.bot_id: Optional[int] = None
        self.is_polling = False
        self._polling_task = None

    async def initialize(self):
        """Initialize bot"""
        try:
            logger.debug("🔧 Initializing bot service...")

            # Create bot instance with optional local Bot API Server
            if settings.telegram_use_local_api and settings.telegram_bot_api_server_url:
                logger.debug(f"🌐 Using local Telegram Bot API Server: {settings.telegram_bot_api_server_url}")
                custom_server = TelegramAPIServer.from_base(settings.telegram_bot_api_server_url)
                session = AiohttpSession(api=custom_server)
            else:
                logger.debug("☁️ Using default Telegram Bot API (cloud)")
                session = AiohttpSession()
            
            self.bot = Bot(
                token=settings.bot_token,
                session=session,
                default=DefaultBotProperties(parse_mode=ParseMode.HTML),
            )

            # Create dispatcher
            self.dp = Dispatcher()

            # Get bot info
            me = await self.bot.get_me()
            self.bot_username = me.username
            self.bot_id = me.id

            logger.debug(f"✅ Bot initialized: @{self.bot_username} ({me.first_name})")

            # Setup middleware
            self._setup_middleware()

            # Setup commands
            await self._setup_commands()

            # Setup command handlers
            self._setup_handlers()
            
            # Setup inline action handlers
            self._setup_inline_actions()

            # Register bot commands
            await self._set_bot_commands()

            logger.debug("✅ Bot service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize bot: {e}")
            raise

    def _setup_middleware(self):
        """Setup bot middleware"""
        if not self.dp:
            return

        # Bot state middleware (check if bot is stopped)
        @self.dp.message.middleware()
        async def bot_state_middleware(handler, event: Message, data: Dict[str, Any]):
            """Check if bot is stopped"""
            # Allow /start and /stop commands even when stopped
            if event.text:
                command = event.text.split()[0].lower() if event.text.split() else ""
                if command in ["/start", "/stop", "/ping"]:
                    return await handler(event, data)
            
            # Check if bot is stopped
            is_stopped = await bot_state_service.is_stopped()
            if is_stopped:
                await event.answer("🛑 <b>Bot is stopped</b>\n\nUse /start to resume operations.")
                return  # Block processing
            
            return await handler(event, data)

        # Authentication middleware for messages (must be after state check)
        @self.dp.message.middleware()
        async def auth_middleware(handler, event: Message, data: Dict[str, Any]):
            """Check if user is allowed to use the bot"""
            # If ALLOWED_USER_ID is not set, allow all users
            if not settings.allowed_user_id:
                return await handler(event, data)
            
            # Get user ID from message
            user_id = event.from_user.id if event.from_user else None
            
            # If no user ID (e.g., channel post), block
            if not user_id:
                logger.warning(
                    f"Blocked message from unknown user (chat_id: {event.chat.id if event.chat else None})"
                )
                return  # Block processing
            
            # Check if user is allowed
            if user_id != settings.allowed_user_id:
                logger.warning(
                    f"Unauthorized access attempt from user {user_id} (allowed: {settings.allowed_user_id})"
                )
                await event.answer("❌ You are not authorized to use this bot.")
                return  # Block processing
            
            # User is authorized, continue
            return await handler(event, data)

        # Authentication middleware for callback queries
        @self.dp.callback_query.middleware()
        async def auth_callback_middleware(handler, event: CallbackQuery, data: Dict[str, Any]):
            """Check if user is allowed to use the bot (for callbacks)"""
            # If ALLOWED_USER_ID is not set, allow all users
            if not settings.allowed_user_id:
                return await handler(event, data)
            
            # Get user ID from callback
            user_id = event.from_user.id if event.from_user else None
            
            # If no user ID, block
            if not user_id:
                logger.warning("Blocked callback from unknown user")
                await event.answer("❌ Unauthorized", show_alert=True)
                return  # Block processing
            
            # Check if user is allowed
            if user_id != settings.allowed_user_id:
                logger.warning(
                    f"Unauthorized callback attempt from user {user_id} (allowed: {settings.allowed_user_id})"
                )
                await event.answer("❌ You are not authorized to use this bot.", show_alert=True)
                return  # Block processing
            
            # User is authorized, continue
            return await handler(event, data)

        # Link router middleware (must be before logging to detect URLs)
        from app.middleware.link_router import LinkRouterMiddleware
        self.dp.message.middleware(LinkRouterMiddleware())

        # Statistics middleware (record messages)
        @self.dp.message.middleware()
        async def statistics_middleware(handler, event: Message, data: Dict[str, Any]):
            """Record message statistics"""
            try:
                from app.services.statistics_service import statistics_service
                chat_id = str(event.chat.id) if event.chat else None
                
                # Extract command if present
                command = None
                if event.text and event.text.startswith("/"):
                    command = event.text.split()[0].replace("/", "").split("@")[0]
                
                # Record received message
                await statistics_service.record_message(
                    message_type="received",
                    chat_id=chat_id,
                    command=command,
                )
            except Exception as e:
                logger.debug(f"Failed to record message statistic: {e}")
            
            result = await handler(event, data)
            
            # Record sent message if handler sent a response
            try:
                from app.services.statistics_service import statistics_service
                chat_id = str(event.chat.id) if event.chat else None
                command = None
                if event.text and event.text.startswith("/"):
                    command = event.text.split()[0].replace("/", "").split("@")[0]
                await statistics_service.record_message(
                    message_type="sent",
                    chat_id=chat_id,
                    command=command,
                )
            except Exception:
                pass
            
            return result

        # Logging middleware
        @self.dp.message.middleware()
        async def logging_middleware(handler, event: Message, data: Dict[str, Any]):
            user = event.from_user.first_name if event.from_user else "Unknown"
            chat_type = event.chat.type if event.chat else "unknown"
            text = event.text or ""
            logger.debug(
                f"📨 Message received: '{text}' from {user} in {chat_type} chat",
                extra={
                    "chatId": event.chat.id if event.chat else None,
                    "userId": event.from_user.id if event.from_user else None,
                },
            )
            return await handler(event, data)

    def _setup_inline_actions(self):
        """Setup inline keyboard callback handlers"""
        if not self.dp or not self.bot:
            return
        
        from app.handlers.inline_actions import setup_inline_actions
        setup_inline_actions(self.dp, self.bot)

    def _setup_handlers(self):
        """Setup message handlers"""
        if not self.dp:
            return

        # Start command
        @self.dp.message(CommandStart())
        async def start_command(message: Message):
            # Check if bot was stopped and resume
            is_stopped = await bot_state_service.is_stopped()
            if is_stopped:
                await bot_state_service.start()
                # Resume scheduler
                from app.scheduler import scheduler
                if scheduler.scheduler and not scheduler.running:
                    try:
                        scheduler.scheduler.resume()
                        scheduler.running = True
                    except Exception as e:
                        logger.warning(f"Failed to resume scheduler: {e}")
                await message.answer("✅ <b>Bot started</b>\n\nAll operations resumed.")
                return

            welcome_text = """
ScoutBot v0.03

Welcome! I'm here to help you monitor RSS feeds, download videos, and send notifications to Telegram.

<b>Basic Commands:</b>
/start - Start the bot
/help - Show help message
/ping - Check if bot is alive

<b>Feed Management:</b>
/list - List your feeds
/add - Add a new feed
/remove - Remove a feed
/enable - Enable a feed
/disable - Disable a feed
/health - Check system health

<b>Video Download:</b>
/download - Download from supported sites
/settings - Configure settings

<b>Information & Statistics:</b>
/stats - Show bot statistics
/blockstats - Show anti-blocking statistics

Type /help for detailed information about all commands.
"""
            await message.answer(welcome_text)

        # Help command with pagination
        @self.dp.message(Command("help"))
        async def help_command(message: Message):
            # Page 1: Basic + Feed commands
            help_text_page1 = """
ScoutBot v0.03 - Help

<b>Basic Commands:</b>
/start - Start the bot
/stop - Stop all bot operations
/help - Show help message
/ping - Check if bot is alive

<b>Feed Management:</b>
/add - Add a new RSS feed
/remove - Remove a feed
/list - List all your feeds
/enable - Enable a feed
/disable - Disable a feed
/health - Check system health

<b>About:</b>
ScoutBot v0.4 by runawaydevil
"""
            markup = InlineKeyboardMarkup(
                inline_keyboard=[[
                    InlineKeyboardButton(text="More commands →", callback_data="help_page_2")
                ]]
            )
            await message.answer(help_text_page1, reply_markup=markup)

        # Help callback for pagination
        @self.dp.callback_query(lambda c: c.data and c.data.startswith("help_page_"))
        async def help_callback(callback_query: CallbackQuery):
            """Handle help pagination callbacks"""
            try:
                page = callback_query.data.split("_")[-1]
                logger.debug(f"Help callback received: page={page}, data={callback_query.data}")
                
                if page == "2":
                    # Page 2: Downloads + Media + Statistics
                    help_text_page2 = """
ScoutBot v0.03 - Help (Page 2)

<b>Video Download:</b>
/download - Download from supported sites
/settings - Configure all bot settings

<b>Media Tools:</b>
/convert - Convert image formats
/gif - Create GIF from video
/clip - Extract video clip
/audio - Extract audio from video
/compress - Compress video
/frames - Extract frames from video
/meme - Generate meme
/sticker - Create sticker
/subs - Extract subtitles
/ocr - Extract text from image

<b>Information & Statistics:</b>
/stats - Show bot statistics
/blockstats - Show anti-blocking statistics
"""
                    markup = InlineKeyboardMarkup(
                        inline_keyboard=[[
                            InlineKeyboardButton(text="← Back", callback_data="help_page_1")
                        ]]
                    )
                    await callback_query.message.edit_text(help_text_page2, reply_markup=markup)
                else:
                    # Page 1
                    help_text_page1 = """
ScoutBot v0.03 - Help

<b>Basic Commands:</b>
/start - Start the bot
/stop - Stop all bot operations
/help - Show help message
/ping - Check if bot is alive

<b>Feed Management:</b>
/add - Add a new RSS feed
/remove - Remove a feed
/list - List all your feeds
/enable - Enable a feed
/disable - Disable a feed
/health - Check system health

<b>About:</b>
ScoutBot v0.4 by runawaydevil
"""
                    markup = InlineKeyboardMarkup(
                        inline_keyboard=[[
                            InlineKeyboardButton(text="More commands →", callback_data="help_page_2")
                        ]]
                    )
                    await callback_query.message.edit_text(help_text_page1, reply_markup=markup)
                
                await callback_query.answer()
            except Exception as e:
                logger.error(f"Failed to handle help callback: {e}", exc_info=True)
                try:
                    await callback_query.answer("❌ Failed to load help page", show_alert=True)
                except Exception:
                    pass

        # Stop command
        @self.dp.message(Command("stop"))
        async def stop_command(message: Message):
            user_id = str(message.from_user.id) if message.from_user else None
            await bot_state_service.stop(user_id=user_id, reason="User requested stop")
            
            # Pause scheduler
            from app.scheduler import scheduler
            if scheduler.scheduler and scheduler.running:
                try:
                    scheduler.scheduler.pause()
                    scheduler.running = False
                except Exception as e:
                    logger.warning(f"Failed to pause scheduler: {e}")
            
            await message.answer("🛑 <b>Bot stopped</b>\n\nAll operations paused. Use /start to resume.")

        # Ping command
        @self.dp.message(Command("ping"))
        async def ping_command(message: Message):
            is_stopped = await bot_state_service.is_stopped()
            if is_stopped:
                await message.answer("🏓 Pong! Bot is alive but <b>stopped</b>. Use /start to resume.")
            else:
                await message.answer("🏓 Pong! Bot is alive and running.")

    async def _setup_commands(self):
        """Setup command handlers from commands module"""
        try:
            await setup_commands(self.dp, self.bot)
        except Exception as e:
            logger.error(f"Failed to setup commands: {e}")

    async def _set_bot_commands(self):
        """Register bot commands with Telegram"""
        if not self.bot:
            return

        commands = [
            BotCommand(command="start", description="Start the bot"),
            BotCommand(command="help", description="Show help message"),
            BotCommand(command="ping", description="Check if bot is alive"),
            BotCommand(command="list", description="List all your feeds"),
            BotCommand(command="add", description="Add a new RSS feed"),
            BotCommand(command="remove", description="Remove a feed"),
            BotCommand(command="enable", description="Enable a feed"),
            BotCommand(command="disable", description="Disable a feed"),
            BotCommand(command="health", description="Check feed health status"),
            BotCommand(command="download", description="Download video/audio from supported sites (YouTube, Spotify, Instagram, Pixeldrain, KrakenFiles, direct URLs)"),
            BotCommand(command="settings", description="Configure download quality and format"),
            BotCommand(command="stats", description="Show bot statistics"),
            BotCommand(command="blockstats", description="Show anti-blocking system statistics"),
        ]

        try:
            await self.bot.set_my_commands(commands)
            logger.debug("✅ Bot commands registered")
        except Exception as e:
            logger.error(f"Failed to register bot commands: {e}")

    async def setup_webhook(self, webhook_url: str, secret_token: Optional[str] = None) -> bool:
        """Setup webhook for Telegram updates"""
        if not self.bot:
            raise RuntimeError("Bot not initialized. Call initialize() first.")
        
        try:
            logger.debug(f"🔧 Setting up webhook: {webhook_url}")
            
            # Set webhook
            await self.bot.set_webhook(
                url=webhook_url,
                secret_token=secret_token,
                drop_pending_updates=True
            )
            
            # Verify webhook was set
            webhook_info = await self.bot.get_webhook_info()
            if webhook_info.url == webhook_url:
                logger.debug("✅ Webhook setup successfully")
                return True
            else:
                logger.warning(f"Webhook URL mismatch: expected {webhook_url}, got {webhook_info.url}")
                return False
        except Exception as e:
            logger.error(f"Failed to setup webhook: {e}", exc_info=True)
            return False
    
    async def remove_webhook(self) -> bool:
        """Remove webhook and return to polling"""
        if not self.bot:
            return False
        
        try:
            logger.debug("🔧 Removing webhook...")
            await self.bot.delete_webhook(drop_pending_updates=True)
            logger.debug("✅ Webhook removed")
            return True
        except Exception as e:
            logger.error(f"Failed to remove webhook: {e}", exc_info=True)
            return False
    
    async def start_polling(self):
        """Start bot polling"""
        if not self.bot or not self.dp:
            raise RuntimeError("Bot not initialized. Call initialize() first.")

        if self.is_polling:
            logger.warn("Bot is already polling")
            return

        try:
            logger.debug("🔧 Starting bot polling...")

            # Clear webhook first
            try:
                await self.bot.delete_webhook(drop_pending_updates=True)
                logger.debug("✅ Webhook cleared")
            except Exception as e:
                logger.warning(f"Failed to clear webhook (may not be set): {e}")

            # Start polling (this is a blocking call, but we run it in a task)
            self.is_polling = True
            # Store the task so we can cancel it later
            import asyncio

            self._polling_task = asyncio.create_task(self.dp.start_polling(self.bot))
            logger.debug("✅ Bot polling started")
        except Exception as e:
            self.is_polling = False
            logger.error(f"Failed to start polling: {e}")
            raise

    async def stop_polling(self):
        """Stop bot polling"""
        if not self.is_polling:
            return

        try:
            logger.debug("🛑 Stopping bot polling...")
            if self._polling_task:
                self._polling_task.cancel()
                try:
                    await self._polling_task
                except asyncio.CancelledError:
                    pass
            if self.dp:
                await self.dp.stop_polling()
            self.is_polling = False
            self._polling_task = None
            logger.debug("✅ Bot polling stopped")
        except Exception as e:
            logger.error(f"Failed to stop polling: {e}")
            self.is_polling = False

    async def is_polling_active(self) -> bool:
        """Check if bot polling is active"""
        if not self.bot:
            return False

        try:
            # Try to get bot info to verify connection
            await self.bot.get_me()
            return self.is_polling
        except Exception:
            return False

    async def restart_polling_if_needed(self) -> bool:
        """Restart polling if it's not active"""
        try:
            if not await self.is_polling_active():
                logger.warn("Bot polling is not active - restarting...")
                await self.stop_polling()
                await self.start_polling()
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to restart polling: {e}")
            return False

    async def send_message(self, chat_id: int, text: str, **kwargs) -> Optional[Message]:
        """Send a message"""
        if not self.bot:
            raise RuntimeError("Bot not initialized")

        try:
            return await self.bot.send_message(chat_id=chat_id, text=text, **kwargs)
        except Exception as e:
            logger.error(f"Failed to send message to {chat_id}: {e}")
            return None

    async def get_metrics(self) -> Dict[str, Any]:
        """Get bot metrics"""
        return {
            "bot_username": self.bot_username,
            "bot_id": self.bot_id,
            "is_polling": self.is_polling,
        }

    async def get_stats(self) -> Dict[str, Any]:
        """Get bot statistics"""
        # Get feed stats from database
        stats = {
            "bot": {
                "username": self.bot_username,
                "id": self.bot_id,
                "polling": self.is_polling,
            }
        }

        if database:
            db_stats = await database.get_stats()
            stats.update(db_stats)

        return stats

    async def close(self):
        """Close bot connections"""
        try:
            await self.stop_polling()
            if self.bot:
                session = self.bot.session
                if session:
                    await session.close()
            logger.debug("✅ Bot service closed")
        except Exception as e:
            logger.error(f"Error closing bot service: {e}")


# Global bot instance
bot_service = BotService()
