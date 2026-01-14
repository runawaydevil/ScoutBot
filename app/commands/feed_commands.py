"""Feed management commands"""

from typing import Optional
from aiogram import Dispatcher, Bot
from aiogram.types import Message
from aiogram.filters import Command

from app.services.feed_service import feed_service
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def setup_feed_commands(dp: Optional[Dispatcher], bot: Optional[Bot]):
    """Setup feed management commands"""
    if not dp:
        return

    # List feeds command
    @dp.message(Command("list"))
    async def list_feeds_command(message: Message):
        """List all feeds for the chat"""
        chat_id = str(message.chat.id)

        try:
            feeds = await feed_service.list_feeds(chat_id)

            if not feeds:
                await message.answer("📋 <b>No feeds configured.</b>\n\nUse /add to add a feed.")
                return

            feed_list = []
            for i, feed in enumerate(feeds, 1):
                status = "✅" if feed.enabled else "❌"
                feed_list.append(f"{i}. {status} <b>{feed.name}</b>\n🔗 {feed.url}")

            response = f"📋 <b>Your RSS Feeds ({len(feeds)}):</b>\n\n" + "\n\n".join(feed_list)
            await message.answer(response)
        except Exception as e:
            logger.error(f"Failed to list feeds for {chat_id}: {e}")
            await message.answer("❌ Failed to list feeds. Please try again.")

    # Add feed command
    @dp.message(Command("add"))
    async def add_feed_command(message: Message):
        """Add a new feed"""
        chat_id = str(message.chat.id)
        args = message.text.split()[1:] if message.text else []

        if len(args) < 2:
            await message.answer(
                "❌ <b>Invalid syntax.</b>\n\n"
                "Usage: /add &lt;name&gt; &lt;url&gt;\n\n"
                "Examples:\n"
                "• RSS: /add MyFeed https://example.com/rss\n"
                "• Reddit: /add Subreddit https://reddit.com/r/subreddit\n"
                "• YouTube: /add Channel youtube.com/@username\n"
                "• YouTube: /add Channel youtube.com/channel/UCxxxxx"
            )
            return

        name = args[0]
        url = " ".join(args[1:])  # URL might contain spaces

        try:
            result = await feed_service.add_feed(chat_id, name, url)

            if result.get("success"):
                await message.answer(
                    f"✅ <b>Feed added successfully!</b>\n\n" f"Name: <b>{name}</b>\n" f"URL: {url}"
                )
            else:
                error = result.get("error", "Unknown error")
                await message.answer(f"❌ <b>Failed to add feed:</b> {error}")
        except Exception as e:
            logger.error(f"Failed to add feed for {chat_id}: {e}")
            await message.answer("❌ Failed to add feed. Please try again.")

    # Remove feed command
    @dp.message(Command("remove"))
    async def remove_feed_command(message: Message):
        """Remove a feed"""
        chat_id = str(message.chat.id)
        args = message.text.split()[1:] if message.text else []

        if len(args) < 1:
            await message.answer(
                "❌ <b>Invalid syntax.</b>\n\n"
                "Usage: /remove &lt;name&gt;\n\n"
                "Example: /remove MyFeed"
            )
            return

        name = args[0]

        try:
            result = await feed_service.remove_feed(chat_id, name)

            if result.get("success"):
                await message.answer(f"✅ <b>Feed removed:</b> {name}")
            else:
                error = result.get("error", "Feed not found")
                await message.answer(f"❌ <b>Failed to remove feed:</b> {error}")
        except Exception as e:
            logger.error(f"Failed to remove feed for {chat_id}: {e}")
            await message.answer("❌ Failed to remove feed. Please try again.")

    # Enable feed command
    @dp.message(Command("enable"))
    async def enable_feed_command(message: Message):
        """Enable a feed"""
        chat_id = str(message.chat.id)
        args = message.text.split()[1:] if message.text else []

        if len(args) < 1:
            await message.answer(
                "❌ <b>Invalid syntax.</b>\n\n"
                "Usage: /enable &lt;name&gt;\n\n"
                "Example: /enable MyFeed"
            )
            return

        name = args[0]

        try:
            result = await feed_service.enable_feed(chat_id, name)

            if result.get("success"):
                await message.answer(f"✅ <b>Feed enabled:</b> {name}")
            else:
                error = result.get("error", "Feed not found")
                await message.answer(f"❌ <b>Failed to enable feed:</b> {error}")
        except Exception as e:
            logger.error(f"Failed to enable feed for {chat_id}: {e}")
            await message.answer("❌ Failed to enable feed. Please try again.")

    # Disable feed command
    @dp.message(Command("disable"))
    async def disable_feed_command(message: Message):
        """Disable a feed"""
        chat_id = str(message.chat.id)
        args = message.text.split()[1:] if message.text else []

        if len(args) < 1:
            await message.answer(
                "❌ <b>Invalid syntax.</b>\n\n"
                "Usage: /disable &lt;name&gt;\n\n"
                "Example: /disable MyFeed"
            )
            return

        name = args[0]

        try:
            result = await feed_service.disable_feed(chat_id, name)

            if result.get("success"):
                await message.answer(f"❌ <b>Feed disabled:</b> {name}")
            else:
                error = result.get("error", "Feed not found")
                await message.answer(f"❌ <b>Failed to disable feed:</b> {error}")
        except Exception as e:
            logger.error(f"Failed to disable feed for {chat_id}: {e}")
            await message.answer("❌ Failed to disable feed. Please try again.")

    # Check feed health command
    @dp.message(Command("health"))
    async def health_command(message: Message):
        """Check system health (Redis, Database, Bot API, Feeds)"""
        chat_id = str(message.chat.id)

        try:
            response = "🏥 <b>System Health Report</b>\n\n"
            all_healthy = True

            # Check Redis
            try:
                from app.utils.cache import cache_service
                redis_ok = await cache_service.ping()
                if redis_ok:
                    response += "✅ <b>Redis:</b> Connected\n"
                else:
                    response += "❌ <b>Redis:</b> Connection failed\n"
                    all_healthy = False
            except Exception as e:
                response += f"❌ <b>Redis:</b> Error - {str(e)[:50]}\n"
                all_healthy = False

            # Check Database
            try:
                from app.database import database
                db_ok = await database.health_check()
                if db_ok:
                    response += "✅ <b>Database:</b> Connected\n"
                else:
                    response += "❌ <b>Database:</b> Connection failed\n"
                    all_healthy = False
            except Exception as e:
                response += f"❌ <b>Database:</b> Error - {str(e)[:50]}\n"
                all_healthy = False

            # Check Bot API
            try:
                from app.bot import bot_service
                if bot_service.bot:
                    me = await bot_service.bot.get_me()
                    response += f"✅ <b>Bot API:</b> Connected (@{me.username})\n"
                else:
                    response += "❌ <b>Bot API:</b> Not initialized\n"
                    all_healthy = False
            except Exception as e:
                response += f"❌ <b>Bot API:</b> Error - {str(e)[:50]}\n"
                all_healthy = False

            # Check Feeds
            try:
                feeds = await feed_service.list_feeds(chat_id)
                problem_feeds = [f for f in feeds if f.failures >= 3]
                healthy_feeds = [f for f in feeds if f.failures < 3]

                if problem_feeds:
                    response += f"⚠️ <b>Feeds:</b> {len(healthy_feeds)} healthy, {len(problem_feeds)} with issues\n"
                    all_healthy = False
                else:
                    response += f"✅ <b>Feeds:</b> {len(healthy_feeds)} healthy\n"
            except Exception as e:
                response += f"❌ <b>Feeds:</b> Error - {str(e)[:50]}\n"
                all_healthy = False

            # Overall status
            response += "\n"
            if all_healthy:
                response += "✅ <b>Overall Status: Healthy</b>"
            else:
                response += "⚠️ <b>Overall Status: Degraded</b>"

            await message.answer(response)
        except Exception as e:
            logger.error(f"Failed to check system health: {e}")
            await message.answer("❌ Failed to check system health. Please try again.")

    # Next check command
    @dp.message(Command("nextcheck"))
    async def nextcheck_command(message: Message):
        """Show when the next RSS feed check will run"""
        try:
            from app.scheduler import scheduler
            from datetime import datetime, timezone
            
            jobs = scheduler.get_jobs()
            feed_job = next((j for j in jobs if j.id == "check_feeds"), None)
            
            if feed_job and feed_job.next_run_time:
                next_run = feed_job.next_run_time
                # Ensure both datetimes are timezone-aware
                if next_run.tzinfo is None:
                    # If next_run is naive, assume UTC
                    next_run = next_run.replace(tzinfo=timezone.utc)
                now = datetime.now(timezone.utc)
                time_until = next_run - now
                
                # Calculate time components
                total_seconds = int(time_until.total_seconds())
                if total_seconds < 0:
                    # Job should have run already, calculate next interval
                    minutes_until = 5 - (abs(total_seconds) % 300)
                    seconds_until = 0
                    next_run = now.replace(second=0, microsecond=0)
                    # Round up to next 5-minute mark
                    current_minute = next_run.minute
                    next_minute = ((current_minute // 5) + 1) * 5
                    if next_minute >= 60:
                        next_run = next_run.replace(hour=next_run.hour + 1, minute=0)
                    else:
                        next_run = next_run.replace(minute=next_minute)
                    time_until = next_run - now
                    total_seconds = int(time_until.total_seconds())
                    minutes_until = total_seconds // 60
                    seconds_until = total_seconds % 60
                else:
                    minutes_until = total_seconds // 60
                    seconds_until = total_seconds % 60
                
                # Format response
                response = "📅 <b>Próxima Verificação RSS</b>\n\n"
                response += f"⏰ <b>Data/Hora:</b> {next_run.strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
                
                if minutes_until > 0:
                    response += f"⏳ <b>Tempo restante:</b> {minutes_until} min {seconds_until} seg"
                else:
                    response += f"⏳ <b>Tempo restante:</b> {seconds_until} seg"
                
                response += f"\n\nℹ️ O job roda a cada <b>5 minutos</b> e verifica quais feeds precisam ser checados baseado no intervalo configurado de cada feed."
                
                await message.answer(response)
            else:
                await message.answer(
                    "❌ <b>Job de verificação RSS não encontrado</b>\n\n"
                    "O scheduler pode não estar inicializado ou o job não foi registrado."
                )
        except Exception as e:
            logger.error(f"Failed to get next check time: {e}", exc_info=True)
            await message.answer("❌ Falha ao verificar próxima execução. Tente novamente.")

    # Block stats command
    @dp.message(Command("blockstats"))
    async def blockstats_command(message: Message):
        """Show blocking statistics"""
        try:
            from app.database import database
            from app.services.blocking_stats_service import BlockingStatsService

            response = "📊 <b>Anti-Blocking Statistics</b>\n\n"

            # Get database statistics
            with database.get_session() as session:
                stats_service = BlockingStatsService(session)
                summary = stats_service.get_summary()
                all_stats = stats_service.get_all_stats()

                # Overall summary
                if summary["total_requests"] > 0:
                    response += "<b>📈 Overall Performance:</b>\n"
                    response += f"• Total Requests: {summary['total_requests']}\n"
                    response += f"• Success Rate: {summary['overall_success_rate']:.1f}%\n"
                    response += f"• Blocked (403): {summary['blocked_requests']}\n"
                    response += f"• Rate Limited (429): {summary['rate_limited_requests']}\n"
                    response += f"• Domains Tracked: {summary['total_domains']}\n\n"

                # Per-domain statistics (top 10 by request count)
                if all_stats:
                    sorted_stats = sorted(all_stats, key=lambda x: x.total_requests, reverse=True)
                    response += "<b>🌐 Top Domains:</b>\n"
                    for stat in sorted_stats[:10]:
                        success_rate = (
                            (stat.successful_requests / stat.total_requests * 100)
                            if stat.total_requests > 0
                            else 0.0
                        )
                        status_icon = (
                            "✅" if success_rate >= 80 else "⚠️" if success_rate >= 50 else "❌"
                        )
                        response += f"{status_icon} <b>{stat.domain}</b>\n"
                        response += f"  Success: {success_rate:.1f}% ({stat.successful_requests}/{stat.total_requests})\n"
                        if stat.blocked_requests > 0:
                            response += f"  Blocked: {stat.blocked_requests}\n"
                        if stat.rate_limited_requests > 0:
                            response += f"  Rate Limited: {stat.rate_limited_requests}\n"
                        response += f"  Delay: {stat.current_delay:.1f}s\n"
                        if stat.circuit_breaker_state != "closed":
                            cb_icon = "🔴" if stat.circuit_breaker_state == "open" else "🟡"
                            response += f"  {cb_icon} Circuit: {stat.circuit_breaker_state}\n"
                    response += "\n"

                # Circuit breaker summary
                if summary["circuit_breaker_open"] > 0 or summary["circuit_breaker_half_open"] > 0:
                    response += "<b>⚡ Circuit Breakers:</b>\n"
                    if summary["circuit_breaker_open"] > 0:
                        response += f"🔴 Open: {summary['circuit_breaker_open']}\n"
                    if summary["circuit_breaker_half_open"] > 0:
                        response += f"🟡 Testing: {summary['circuit_breaker_half_open']}\n"
                    response += "\n"

                # Low success rate domains
                low_success_domains = stats_service.get_domains_with_low_success_rate(
                    threshold=50.0
                )
                if low_success_domains:
                    response += "<b>⚠️ Low Success Rate Domains:</b>\n"
                    for stat in low_success_domains[:5]:
                        success_rate = (
                            (stat.successful_requests / stat.total_requests * 100)
                            if stat.total_requests > 0
                            else 0.0
                        )
                        response += f"• {stat.domain}: {success_rate:.1f}%\n"
                    response += "\n"

                if summary["total_requests"] == 0:
                    response += "ℹ️ No blocking data yet.\n"

            await message.answer(response)
        except Exception as e:
            logger.error(f"Failed to get block stats: {e}")
            await message.answer("❌ Failed to get statistics. Please try again.")

    # Stats command
    @dp.message(Command("stats"))
    async def stats_command(message: Message):
        """Show comprehensive bot statistics"""
        chat_id = str(message.chat.id)

        try:
            from app.database import database
            from app.services.statistics_service import statistics_service
            from datetime import datetime

            response = "📊 <b>Bot Statistics</b>\n\n"

            # Message Statistics
            msg_stats = await statistics_service.get_message_stats(days=30)
            response += "💬 <b>Messages (Last 30 days)</b>\n"
            response += f"Sent: {msg_stats['total_sent']} | Received: {msg_stats['total_received']}\n"
            response += f"Errors: {msg_stats['total_errors']} ({msg_stats['error_rate']:.1f}%)\n\n"

            # Download Statistics
            dl_stats = await statistics_service.get_download_stats(days=30)
            response += "📥 <b>Downloads (Last 30 days)</b>\n"
            response += f"Total: {dl_stats['total']} | Success: {dl_stats['success']} | Failed: {dl_stats['failed']}\n"
            response += f"Success Rate: {dl_stats['success_rate']:.1f}%\n"
            if dl_stats['avg_file_size_mb'] > 0:
                response += f"Avg Size: {dl_stats['avg_file_size_mb']:.2f} MB\n"
            if dl_stats['by_type']:
                response += "By Type: "
                type_list = [f"{k}({v})" for k, v in list(dl_stats['by_type'].items())[:3]]
                response += ", ".join(type_list) + "\n"
            response += "\n"

            # Conversion Statistics
            conv_stats = await statistics_service.get_conversion_stats(days=30)
            response += "🔄 <b>Conversions (Last 30 days)</b>\n"
            response += f"Total: {conv_stats['total']} | Success: {conv_stats['success']} | Failed: {conv_stats['failed']}\n"
            response += f"Success Rate: {conv_stats['success_rate']:.1f}%\n"
            if conv_stats['by_type']:
                response += "By Type: "
                type_list = [f"{k}({v})" for k, v in list(conv_stats['by_type'].items())[:3]]
                response += ", ".join(type_list) + "\n"
            response += "\n"

            # Feed Statistics
            with database.get_session() as session:
                from sqlmodel import select
                from app.models.feed import Feed

                feeds = session.exec(select(Feed).where(Feed.chat_id == chat_id)).all()
                enabled_feeds = [f for f in feeds if f.enabled]
                disabled_feeds = [f for f in feeds if not f.enabled]

                response += "📋 <b>Feeds</b>\n"
                response += f"Enabled: {len(enabled_feeds)} | Disabled: {len(disabled_feeds)} | Total: {len(feeds)}\n"

                if feeds:
                    # Calculate feed success rate
                    total_checks = sum(f.failures + 1 for f in feeds if f.last_check)  # Approximate
                    total_failures = sum(f.failures for f in feeds)
                    if total_checks > 0:
                        feed_success_rate = ((total_checks - total_failures) / total_checks * 100) if total_checks > 0 else 0.0
                        response += f"Success Rate: {feed_success_rate:.1f}%\n"

                    # Most active feeds
                    feeds_with_notifications = [f for f in feeds if f.last_notified_at is not None]
                    if feeds_with_notifications:
                        sorted_feeds = sorted(
                            feeds_with_notifications,
                            key=lambda x: x.last_notified_at or datetime.min,
                            reverse=True,
                        )[:3]

                        response += "Most Active: "
                        active_list = [f.name for f in sorted_feeds]
                        response += ", ".join(active_list) + "\n"

                    # Feed health section
                    feeds_with_issues = [f for f in feeds if f.failures > 0 or not f.enabled]
                    if feeds_with_issues:
                        response += "\n📈 <b>Feed Health</b>\n"
                        for feed in feeds_with_issues[:5]:
                            status_emoji = "✅" if feed.enabled else "❌"
                            health_emoji = "⚠️" if feed.failures > 0 else status_emoji
                            response += f"{health_emoji} <b>{feed.name}</b>\n"
                            if not feed.enabled:
                                response += "   Status: Disabled\n"
                            if feed.failures > 0:
                                response += f"   ⚠️ Failures: {feed.failures}\n"
                            response += "\n"

            await message.answer(response)
        except Exception as e:
            logger.error(f"Failed to get statistics: {e}", exc_info=True)
            await message.answer("❌ Failed to get statistics. Please try again.")
