"""Database setup and configuration using SQLModel"""

from typing import Dict, Any, Optional
from sqlmodel import SQLModel, create_engine, Session, select
from sqlalchemy.engine import Engine
import os

from app.config import settings
from app.utils.logger import get_logger
from app.models.feed import (
    Chat,
    Feed,
    JobStatus,
)
from app.models.user_settings import UserSettings
from app.models.statistics import MessageStatistic, DownloadStatistic, ConversionStatistic
from app.models.bot_state import BotState
from app.models.bot_settings import BotSettings
from app.models.pentaract_upload import PentaractUpload
from app.models.pentaract_file import PentaractFile

logger = get_logger(__name__)


class DatabaseService:
    """Database service for managing SQLModel database"""

    def __init__(self):
        self.engine: Optional[Engine] = None
        self._session: Optional[Session] = None

    def initialize(self):
        """Initialize database connection"""
        try:
            # Convert SQLite URL format
            database_url = settings.database_url
            logger.debug(f"Raw database URL from settings: {database_url}")

            # Handle different URL formats
            if database_url.startswith("file:"):
                # Prisma format: file:/app/data/production.db or file:./data/development.db
                path = database_url.replace("file:", "")

                # Only fix paths on Windows (keep Docker/Unix paths as-is)
                if os.name == "nt" and path.startswith("/"):  # Windows
                    # Unix absolute path on Windows, convert to relative
                    if "/app/" in path:
                        # Docker path on Windows, convert to relative
                        path = "./" + path.split("/app/")[-1]
                    else:
                        # Generic absolute path, use just the filename in data directory
                        path = "./data/" + os.path.basename(path)
                    # Normalize path separators for Windows
                    path = path.replace("/", os.sep)

                # Create directory if it doesn't exist
                db_dir = os.path.dirname(path)
                if db_dir and not os.path.exists(db_dir):
                    os.makedirs(db_dir, exist_ok=True)
                    logger.debug(f"Created database directory: {db_dir}")

                # Convert to SQLAlchemy format (always use forward slashes for SQLite URLs)
                normalized_path = path.replace("\\", "/")
                database_url = f"sqlite:///{normalized_path}"

            elif database_url.startswith("sqlite:///./"):
                # Relative path: sqlite:///./data/development.db
                path = database_url.replace("sqlite:///./", "")
                # Normalize path separators for Windows
                if os.name == "nt":
                    path = path.replace("/", os.sep)
                db_dir = os.path.dirname(path)
                if db_dir and not os.path.exists(db_dir):
                    os.makedirs(db_dir, exist_ok=True)
                    logger.debug(f"Created database directory: {db_dir}")
                # Normalize for SQLite URL
                normalized_path = path.replace("\\", "/")
                database_url = f"sqlite:///{normalized_path}"
            elif database_url.startswith("sqlite:///"):
                # Absolute or relative: sqlite:///data/development.db
                path = database_url.replace("sqlite:///", "")

                # Handle absolute paths that don't exist on Windows
                if path.startswith("/app/") or (path.startswith("/") and os.name == "nt"):
                    # Convert Unix/Docker absolute paths to relative on Windows
                    if "/app/" in path:
                        path = "./" + path.split("/app/")[-1]
                    else:
                        path = "./data/" + os.path.basename(path)

                # Normalize path separators for Windows
                if os.name == "nt":
                    path = path.replace("/", os.sep)

                # Create directory if it doesn't exist
                db_dir = os.path.dirname(path)
                if db_dir and not os.path.exists(db_dir):
                    os.makedirs(db_dir, exist_ok=True)
                    logger.debug(f"Created database directory: {db_dir}")

                # Normalize for SQLite URL
                normalized_path = path.replace("\\", "/")
                database_url = f"sqlite:///{normalized_path}"

            logger.debug(f"Connecting to database: {database_url.split('/')[-1]}")

            # Create engine with SQLite-specific settings and connection pooling
            if database_url.startswith("sqlite:///"):
                connect_args = {"check_same_thread": False}
                # SQLite doesn't support pool_size, but we can optimize with other settings
                self.engine = create_engine(
                    database_url,
                    connect_args=connect_args,
                    echo=False,
                    pool_pre_ping=True,  # Verify connections before using
                    pool_recycle=3600,  # Recycle connections after 1 hour
                )
                
                # Configure SQLite PRAGMA settings for optimal performance
                with self.engine.connect() as conn:
                    # Enable WAL mode for better concurrency
                    conn.exec_driver_sql("PRAGMA journal_mode=WAL")
                    # Set synchronous to NORMAL (faster than FULL, safe with WAL)
                    conn.exec_driver_sql("PRAGMA synchronous=NORMAL")
                    # Set cache size to 64MB (negative value = KB, so -64000 = 64MB)
                    conn.exec_driver_sql("PRAGMA cache_size=-64000")
                    # Use memory for temporary tables
                    conn.exec_driver_sql("PRAGMA temp_store=MEMORY")
                    # Enable memory-mapped I/O (256MB)
                    conn.exec_driver_sql("PRAGMA mmap_size=268435456")
                    # Optimize for performance
                    conn.exec_driver_sql("PRAGMA optimize")
                    conn.commit()
            else:
                # For other databases (PostgreSQL, MySQL, etc.), use connection pooling
                self.engine = create_engine(
                    database_url,
                    echo=False,
                    pool_pre_ping=True,
                    pool_size=5,
                    max_overflow=10,
                    pool_recycle=3600,
                )

            # Create tables
            SQLModel.metadata.create_all(self.engine)

            # Apply PRAGMA settings after table creation
            with self.engine.connect() as conn:
                conn.exec_driver_sql("PRAGMA journal_mode=WAL")
                conn.exec_driver_sql("PRAGMA synchronous=NORMAL")
                conn.exec_driver_sql("PRAGMA cache_size=-64000")
                conn.exec_driver_sql("PRAGMA temp_store=MEMORY")
                conn.exec_driver_sql("PRAGMA mmap_size=268435456")
                conn.commit()

            logger.debug("Database initialized successfully with WAL mode and optimizations")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

    def get_session(self) -> Session:
        """Get database session"""
        if not self.engine:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        return Session(self.engine)

    async def health_check(self) -> bool:
        """Check database health"""
        try:
            with self.get_session() as session:
                # Simple query to check connection
                session.exec(select(1)).first()
                return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False

    async def get_metrics(self) -> Dict[str, Any]:
        """Get database metrics"""
        try:
            with self.get_session() as session:
                feed_count = session.exec(select(Feed)).all()
                chat_count = session.exec(select(Chat)).all()

                return {
                    "database_feed_count": len(feed_count),
                    "database_chat_count": len(chat_count),
                }
        except Exception as e:
            logger.error(f"Failed to get database metrics: {e}")
            return {}

    async def get_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        try:
            with self.get_session() as session:
                feeds = session.exec(select(Feed)).all()
                chats = session.exec(select(Chat)).all()
                enabled_feeds = [f for f in feeds if f.enabled]
                disabled_feeds = [f for f in feeds if not f.enabled]

                return {
                    "database": {
                        "total_feeds": len(feeds),
                        "enabled_feeds": len(enabled_feeds),
                        "disabled_feeds": len(disabled_feeds),
                        "total_chats": len(chats),
                    }
                }
        except Exception as e:
            logger.error(f"Failed to get database stats: {e}")
            return {"database": {}}

    async def vacuum_and_analyze(self):
        """Run VACUUM and ANALYZE to optimize database"""
        if not self.engine:
            return
        
        try:
            from sqlalchemy import text
            with self.engine.connect() as conn:
                # VACUUM reclaims unused space
                conn.execute(text("VACUUM"))
                # ANALYZE updates query optimizer statistics
                conn.execute(text("ANALYZE"))
                conn.commit()
                logger.debug("Database VACUUM and ANALYZE completed")
        except Exception as e:
            logger.error(f"Failed to run VACUUM/ANALYZE: {e}")

    def close(self):
        """Close database connection"""
        if self.engine:
            self.engine.dispose()
            logger.debug("Database connection closed")


# Global database instance
database = DatabaseService()
