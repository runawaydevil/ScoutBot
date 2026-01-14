"""HTTP session manager with rotation"""

import time
import aiohttp
from typing import Dict, Tuple


class SessionManager:
    """Manages HTTP sessions per domain with rotation"""

    def __init__(self, session_ttl: int = 900):
        self.sessions: Dict[str, Tuple[aiohttp.ClientSession, float]] = (
            {}
        )  # domain -> (session, created_at)
        self.session_ttl = session_ttl  # 15 minutes (optimized for memory)

    async def get_session(self, domain: str) -> aiohttp.ClientSession:
        """Get or create session for domain"""
        # Clean up expired sessions periodically
        current_time = time.time()
        expired_domains = [
            d for d, (s, created_at) in self.sessions.items()
            if current_time - created_at >= self.session_ttl
        ]
        for expired_domain in expired_domains:
            session, _ = self.sessions[expired_domain]
            await session.close()
            del self.sessions[expired_domain]
        
        if domain in self.sessions:
            session, created_at = self.sessions[domain]
            if current_time - created_at < self.session_ttl:
                return session
            else:
                # Session expired, close and create new
                await session.close()

        # Create new session with optimized connection limits (reduced for memory)
        session = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(limit_per_host=2, limit=15),  # Reduced to 2 per host, 15 total
            cookie_jar=aiohttp.CookieJar(),
        )
        self.sessions[domain] = (session, time.time())
        return session

    async def close_all(self):
        """Close all sessions"""
        for session, _ in self.sessions.values():
            await session.close()
        self.sessions.clear()

    async def close_session(self, domain: str):
        """Close specific domain session"""
        if domain in self.sessions:
            session, _ = self.sessions[domain]
            await session.close()
            del self.sessions[domain]


# Global instance with optimized TTL (15 minutes for memory optimization)
session_manager = SessionManager(session_ttl=900)
