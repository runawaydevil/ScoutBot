"""Bot state service for managing bot operational state"""

from datetime import datetime
from typing import Optional
from sqlmodel import select

from app.database import database
from app.models.bot_state import BotState
from app.utils.logger import get_logger

logger = get_logger(__name__)


class BotStateService:
    """Service for managing bot state"""

    async def get_state(self) -> BotState:
        """Get or create bot state"""
        try:
            with database.get_session() as session:
                statement = select(BotState).where(BotState.id == "global")
                state = session.exec(statement).first()

                if not state:
                    # Create default state (running)
                    state = BotState(
                        id="global",
                        is_stopped=False,
                    )
                    session.add(state)
                    session.commit()
                    session.refresh(state)
                    logger.info("Created default bot state (running)")

                return state
        except Exception as e:
            logger.error(f"Failed to get bot state: {e}")
            # Return default state if database fails
            return BotState(id="global", is_stopped=False)

    async def is_stopped(self) -> bool:
        """Check if bot is stopped"""
        state = await self.get_state()
        return state.is_stopped

    async def stop(self, user_id: Optional[str] = None, reason: Optional[str] = None):
        """Stop bot operations"""
        try:
            with database.get_session() as session:
                # Get state within the same session
                statement = select(BotState).where(BotState.id == "global")
                state = session.exec(statement).first()
                
                if not state:
                    # Create default state if it doesn't exist
                    state = BotState(
                        id="global",
                        is_stopped=False,
                    )
                    session.add(state)
                
                state.is_stopped = True
                state.stopped_at = datetime.utcnow()
                state.stopped_by = user_id
                state.reason = reason
                state.updated_at = datetime.utcnow()
                session.add(state)
                session.commit()
                logger.info(f"Bot stopped by user {user_id}: {reason}")
        except Exception as e:
            logger.error(f"Failed to stop bot: {e}")
            raise

    async def start(self):
        """Start bot operations"""
        try:
            with database.get_session() as session:
                # Get state within the same session
                statement = select(BotState).where(BotState.id == "global")
                state = session.exec(statement).first()
                
                if not state:
                    # Create default state if it doesn't exist
                    state = BotState(
                        id="global",
                        is_stopped=False,
                    )
                    session.add(state)
                
                state.is_stopped = False
                state.stopped_at = None
                state.stopped_by = None
                state.reason = None
                state.updated_at = datetime.utcnow()
                session.add(state)
                session.commit()
                logger.info("Bot started - all operations resumed")
        except Exception as e:
            logger.error(f"Failed to start bot: {e}")
            raise


# Global bot state service instance
bot_state_service = BotStateService()
