"""FastAPI application with health check endpoints"""

import time
import gc
import asyncio
from typing import Dict, Any, Optional
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.config import settings
from app.utils.logger import get_logger
from app.database import database
from app.utils.cache import cache_service
from app.bot import bot_service
from app.scheduler import scheduler

logger = get_logger(__name__)

# Configure garbage collection for async workloads (optimize thresholds)
# Reduce collection frequency for better performance with async I/O
# Thresholds: (generation0, generation1, generation2)
# Higher values = less frequent GC = better for async I/O workloads
gc.set_threshold(700, 10, 10)  # Default is (700, 10, 10), optimized for async

# Global application instance
app = FastAPI(
    title="ScoutBot",
    description="It rocks Telegram",
    version="0.03",
)

# Track application start time for uptime calculation
_app_start_time: Optional[float] = None


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    global _app_start_time
    _app_start_time = time.time()
    logger.debug("Starting ScoutBot v0.03 application")

    # Initialize database
    database.initialize()

    # Initialize default bot settings
    from app.services.bot_settings_service import bot_settings_service
    await bot_settings_service.initialize_default_settings()
    logger.debug("✅ Default bot settings initialized")

    # Load settings from database (override .env)
    db_settings = await bot_settings_service.get_all_settings()
    from app.config import settings
    for key, value in db_settings.items():
        if hasattr(settings, key):
            # Handle None values for Optional types
            if value is None and key == "allowed_user_id":
                setattr(settings, key, None)
            else:
                setattr(settings, key, value)
    if db_settings:
        logger.debug(f"✅ Loaded {len(db_settings)} settings from database")

    # Log Pentaract configuration (without sensitive data)
    from app.utils.logger import log_pentaract_config
    log_pentaract_config(logger, settings)

    # Initialize bot state
    from app.services.bot_state_service import bot_state_service
    await bot_state_service.get_state()  # Ensure state exists
    logger.debug("✅ Bot state initialized")

    # Initialize Pentaract storage service if enabled
    if settings.pentaract_enabled:
        from app.services.pentaract_storage_service import pentaract_storage
        try:
            success = await pentaract_storage.initialize()
            if success:
                logger.info("✅ Pentaract storage service initialized")
            else:
                logger.warning("⚠️ Pentaract storage service initialization failed")
        except Exception as e:
            logger.error(f"Failed to initialize Pentaract storage service: {e}")
    
    # Initialize cleanup service if Pentaract is enabled
    if settings.pentaract_enabled and settings.pentaract_auto_cleanup:
        from app.services.cleanup_service import cleanup_service
        try:
            await cleanup_service.start()
            logger.info("✅ Cleanup service started")
        except Exception as e:
            logger.error(f"Failed to start cleanup service: {e}")
    
    # Initialize upload queue service if Pentaract is enabled
    if settings.pentaract_enabled:
        from app.services.upload_queue_service import upload_queue_service
        try:
            await upload_queue_service.start()
            logger.info("✅ Upload queue service started")
        except Exception as e:
            logger.error(f"Failed to start upload queue service: {e}")
    
    # Initialize resource monitoring service
    if settings.resource_monitoring_enabled:
        from app.services.resource_monitor_service import resource_monitor
        try:
            await resource_monitor.start()
            logger.info("✅ Resource monitoring service started")
        except Exception as e:
            logger.error(f"Failed to start resource monitoring service: {e}")

    # Initialize Redis cache
    await cache_service.initialize()

    # Initialize scheduler
    scheduler.initialize()
    scheduler.start()

    # Add feed checker job (runs every 10 minutes - optimized for resource usage)
    from app.jobs.feed_checker import check_feeds_job

    scheduler.add_interval_job(
        check_feeds_job,
        minutes=10,
        job_id="check_feeds",
    )
    logger.debug("✅ Feed checker job scheduled")

    # Add blocking monitor job (runs every 2 hours to check success rates - optimized)
    from app.jobs.blocking_monitor import check_blocking_stats_job, cleanup_blocking_stats_job

    scheduler.add_interval_job(
        check_blocking_stats_job,
        minutes=120,
        job_id="check_blocking_stats",
    )
    logger.debug("✅ Blocking monitor job scheduled")

    # Add blocking stats cleanup job (runs daily at 3 AM UTC)
    scheduler.add_cron_job(
        cleanup_blocking_stats_job,
        hour=3,
        minute=0,
        job_id="cleanup_blocking_stats",
    )
    logger.debug("✅ Blocking stats cleanup job scheduled")

    # Add temporary file cleanup job (runs every 2 hours - optimized)
    from app.jobs.tempfile_cleanup import cleanup_tempfiles_job

    scheduler.add_interval_job(
        cleanup_tempfiles_job,
        minutes=120,
        job_id="cleanup_tempfiles",
    )
    logger.debug("✅ Temporary file cleanup job scheduled")

    # Initialize bot
    await bot_service.initialize()
    
    # Start bot in polling or webhook mode based on configuration
    import asyncio
    
    use_webhook = settings.use_webhook
    
    if use_webhook:
        # Webhook mode
        webhook_url = settings.webhook_url
        webhook_secret = settings.webhook_secret
        
        if webhook_url:
            logger.debug(f"🔧 Setting up webhook mode: {webhook_url}")
            success = await bot_service.setup_webhook(webhook_url, webhook_secret)
            if not success:
                logger.warning("⚠️ Webhook setup failed, falling back to polling")
                try:
                    asyncio.create_task(bot_service.start_polling())
                except Exception as e:
                    logger.error(f"Failed to start bot polling: {e}")
        else:
            logger.warning("⚠️ USE_WEBHOOK=true but WEBHOOK_URL not set, using polling")
            try:
                asyncio.create_task(bot_service.start_polling())
            except Exception as e:
                logger.error(f"Failed to start bot polling: {e}")
    else:
        # Polling mode (default)
        try:
            asyncio.create_task(bot_service.start_polling())
        except Exception as e:
            logger.error(f"Failed to start bot polling: {e}")

    # Start keep-alive service
    from app.resilience.keep_alive import keep_alive_service

    keep_alive_service.start()
    logger.debug("✅ Keep-alive service started")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.debug("Shutting down ScoutBot application")

    # Flush statistics buffer before shutdown
    try:
        from app.services.statistics_service import statistics_service
        await statistics_service.buffer.flush(wait_for_existing=True)
        logger.debug("✅ Statistics buffer flushed on shutdown")
    except Exception as e:
        logger.error(f"Error flushing statistics buffer: {e}")

    # Stop Pentaract services
    if settings.pentaract_enabled:
        try:
            from app.services.cleanup_service import cleanup_service
            from app.services.upload_queue_service import upload_queue_service
            from app.services.pentaract_storage_service import pentaract_storage
            
            # Stop upload queue
            await upload_queue_service.stop()
            logger.debug("✅ Upload queue service stopped")
            
            # Stop cleanup service
            await cleanup_service.stop()
            logger.debug("✅ Cleanup service stopped")
            
            # Final cleanup of temporary files
            if settings.pentaract_auto_cleanup:
                cleaned = await cleanup_service.cleanup_temp_files()
                if cleaned > 0:
                    logger.info(f"✅ Cleaned up {cleaned} temporary files on shutdown")
            
            # Close Pentaract storage service
            await pentaract_storage.close()
            logger.debug("✅ Pentaract storage service closed")
        except Exception as e:
            logger.error(f"Error during Pentaract services shutdown: {e}")
        
        # Stop resource monitoring service
        if settings.resource_monitoring_enabled:
            try:
                from app.services.resource_monitor_service import resource_monitor
                await resource_monitor.stop()
                logger.debug("✅ Resource monitoring service stopped")
            except Exception as e:
                logger.error(f"Error stopping resource monitoring service: {e}")

    # Stop keep-alive service
    from app.resilience.keep_alive import keep_alive_service

    keep_alive_service.stop()

    # Stop bot
    await bot_service.close()

    # Stop scheduler
    scheduler.stop()

    # Close cache
    await cache_service.close()

    # Close database
    database.close()


@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """Health check endpoint with minimal logging"""
    try:
        import psutil

        process = psutil.Process()
        memory_info = process.memory_info()
        memory_percent = process.memory_percent()
    except ImportError:
        try:
            import sys

            if sys.platform != "win32":
                import resource

                memory_info = resource.getrusage(resource.RUSAGE_SELF)
            else:
                # Windows doesn't have resource module
                memory_info = type("obj", (object,), {"rss": 0, "vms": 0})()
            memory_percent = 0.0
        except Exception:
            memory_info = type("obj", (object,), {"rss": 0, "vms": 0})()
            memory_percent = 0.0

    current_time = time.time()
    uptime = (current_time - _app_start_time) if _app_start_time else 0

    checks: Dict[str, Any] = {
        "status": "ok",
        "timestamp": current_time,
        "uptime": uptime,
        "memory": {
            "rss": getattr(memory_info, "rss", 0),
            "vms": getattr(memory_info, "vms", 0),
            "usage_percent": memory_percent,
            "usage_mb": round(getattr(memory_info, "rss", 0) / 1024 / 1024, 2),
        },
        "mode": "full-bot",
    }

    # Check database
    if database:
        try:
            checks["database"] = await database.health_check()
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            checks["database"] = False
    else:
        checks["database"] = False

    # Check Redis
    if not settings.disable_redis:
        try:
            checks["redis"] = await cache_service.ping()
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            checks["redis"] = False
    else:
        checks["redis"] = settings.disable_redis

    # Check bot
    if bot_service:
        try:
            checks["bot"] = await bot_service.is_polling_active()
        except Exception as e:
            logger.error(f"Bot health check failed: {e}")
            checks["bot"] = False
    else:
        checks["bot"] = False

    # Check scheduler
    if scheduler:
        try:
            checks["scheduler"] = scheduler.running
        except Exception as e:
            logger.error(f"Scheduler health check failed: {e}")
            checks["scheduler"] = False
    else:
        checks["scheduler"] = False

    # Overall health
    critical_services = ["database", "bot"]
    is_healthy = all(checks.get(service, False) for service in critical_services)

    if not is_healthy:
        checks["status"] = "error"
        logger.warning("Health check failed", extra={"checks": checks})
        return JSONResponse(status_code=503, content=checks)

    # Success - log at DEBUG level only
    logger.debug("Health check passed")
    return checks


@app.get("/metrics")
async def metrics() -> Dict[str, Any]:
    """Metrics endpoint for Prometheus"""
    try:
        import psutil

        process = psutil.Process()
        memory_info = process.memory_info()
        cpu_percent = process.cpu_percent(interval=0.1)
    except ImportError:
        memory_info = type("obj", (object,), {"rss": 0, "vms": 0})()
        cpu_percent = 0.0

    current_time = time.time()
    uptime_seconds = (current_time - _app_start_time) if _app_start_time else 0

    metrics_data = {
        "memory_rss_bytes": memory_info.rss,
        "memory_vms_bytes": getattr(memory_info, "vms", 0),
        "cpu_percent": cpu_percent,
        "uptime_seconds": uptime_seconds,
    }

    # Add service-specific metrics
    if database:
        try:
            metrics_data.update(await database.get_metrics())
        except Exception as e:
            logger.error(f"Failed to get database metrics: {e}")

    if bot_service:
        try:
            metrics_data.update(await bot_service.get_metrics())
        except Exception as e:
            logger.error(f"Failed to get bot metrics: {e}")

    return metrics_data


@app.get("/stats")
async def stats() -> Dict[str, Any]:
    """Statistics endpoint"""
    stats_data = {
        "timestamp": time.time(),
        "version": "0.5.0",
        "environment": settings.environment,
    }

    # Add service-specific stats
    if database:
        try:
            stats_data.update(await database.get_stats())
        except Exception as e:
            logger.error(f"Failed to get database stats: {e}")

    if bot_service:
        try:
            stats_data.update(await bot_service.get_stats())
        except Exception as e:
            logger.error(f"Failed to get bot stats: {e}")

    return stats_data


@app.post("/webhook/{bot_token:path}")
async def webhook_handler(bot_token: str, update: Dict[str, Any]):
    """Webhook endpoint for Telegram updates"""
    try:
        # Verify bot token matches
        if bot_token != settings.bot_token:
            logger.warning(f"Webhook called with invalid token")
            return JSONResponse(status_code=403, content={"error": "Invalid token"})
        
        # Verify webhook secret if configured
        webhook_secret = getattr(settings, 'webhook_secret', None)
        if webhook_secret:
            # In a real implementation, verify secret from headers
            pass
        
        # Process update through dispatcher
        if bot_service.dp and bot_service.bot:
            await bot_service.dp.feed_update(bot_service.bot, update)
            return {"ok": True}
        else:
            logger.error("Bot or dispatcher not initialized")
            return JSONResponse(status_code=503, content={"error": "Bot not initialized"})
            
    except Exception as e:
        logger.error(f"Webhook handler error: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/")
async def root():
    """Root endpoint"""
    endpoints = {
        "health": "/health",
        "metrics": "/metrics",
        "stats": "/stats",
    }
    
    # Add webhook endpoint if enabled
    if getattr(settings, 'use_webhook', False):
        endpoints["webhook"] = f"/webhook/{settings.bot_token}"
    
    return {
        "name": "ScoutBot",
        "version": "0.03",
        "status": "running",
        "endpoints": endpoints,
    }
