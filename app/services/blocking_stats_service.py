"""Blocking statistics service for tracking and persisting anti-blocking metrics"""

from datetime import datetime, timedelta
from typing import Optional, Dict, List
from sqlmodel import Session, select
import uuid

from app.models.feed import BlockingStats
from app.utils.logger import get_logger

logger = get_logger(__name__)


class BlockingStatsService:
    """Service for managing blocking statistics and learned behaviors"""

    def __init__(self, session: Session):
        self.session = session

    def get_or_create_stats(self, domain: str) -> BlockingStats:
        """Get existing stats or create new entry for domain"""
        statement = select(BlockingStats).where(BlockingStats.domain == domain)
        stats = self.session.exec(statement).first()

        if not stats:
            stats = BlockingStats(
                id=str(uuid.uuid4()),
                domain=domain,
                total_requests=0,
                successful_requests=0,
                blocked_requests=0,
                rate_limited_requests=0,
                current_delay=5.0,
                circuit_breaker_state="closed",
            )
            self.session.add(stats)
            self.session.commit()
            self.session.refresh(stats)
            logger.info(f"Created new blocking stats for domain: {domain}")

        return stats

    def record_request_success(
        self, domain: str, user_agent: Optional[str] = None, delay: Optional[float] = None
    ) -> BlockingStats:
        """Record a successful request"""
        stats = self.get_or_create_stats(domain)

        stats.total_requests += 1
        stats.successful_requests += 1
        stats.last_success = datetime.utcnow()
        stats.updated_at = datetime.utcnow()

        # Update preferred User-Agent if provided
        if user_agent:
            stats.preferred_user_agent = user_agent

        # Update current delay if provided
        if delay is not None:
            stats.current_delay = delay

        self.session.add(stats)
        self.session.commit()
        self.session.refresh(stats)

        logger.debug(
            f"Recorded success for {domain}: {stats.successful_requests}/{stats.total_requests}"
        )
        return stats

    def record_request_failure(
        self,
        domain: str,
        status_code: int,
        delay: Optional[float] = None,
        circuit_breaker_state: Optional[str] = None,
    ) -> BlockingStats:
        """Record a failed request with status code"""
        stats = self.get_or_create_stats(domain)

        stats.total_requests += 1
        stats.last_failure = datetime.utcnow()
        stats.updated_at = datetime.utcnow()

        # Track specific failure types
        if status_code == 403:
            stats.blocked_requests += 1
            logger.warning(f"Blocked request (403) for domain: {domain}")
        elif status_code == 429:
            stats.rate_limited_requests += 1
            logger.warning(f"Rate limited request (429) for domain: {domain}")

        # Update delay if provided
        if delay is not None:
            stats.current_delay = delay

        # Update circuit breaker state if provided
        if circuit_breaker_state:
            stats.circuit_breaker_state = circuit_breaker_state

        self.session.add(stats)
        self.session.commit()
        self.session.refresh(stats)

        logger.debug(
            f"Recorded failure for {domain}: status={status_code}, "
            f"blocked={stats.blocked_requests}, rate_limited={stats.rate_limited_requests}"
        )
        return stats

    def update_circuit_breaker_state(self, domain: str, state: str) -> BlockingStats:
        """Update circuit breaker state for domain"""
        stats = self.get_or_create_stats(domain)
        stats.circuit_breaker_state = state
        stats.updated_at = datetime.utcnow()

        self.session.add(stats)
        self.session.commit()
        self.session.refresh(stats)

        logger.info(f"Updated circuit breaker state for {domain}: {state}")
        return stats

    def update_delay(self, domain: str, delay: float) -> BlockingStats:
        """Update current delay for domain"""
        stats = self.get_or_create_stats(domain)
        stats.current_delay = delay
        stats.updated_at = datetime.utcnow()

        self.session.add(stats)
        self.session.commit()
        self.session.refresh(stats)

        logger.debug(f"Updated delay for {domain}: {delay}s")
        return stats

    def update_preferred_user_agent(self, domain: str, user_agent: str) -> BlockingStats:
        """Update preferred User-Agent for domain"""
        stats = self.get_or_create_stats(domain)
        stats.preferred_user_agent = user_agent
        stats.updated_at = datetime.utcnow()

        self.session.add(stats)
        self.session.commit()
        self.session.refresh(stats)

        logger.debug(f"Updated preferred User-Agent for {domain}")
        return stats

    def get_stats(self, domain: str) -> Optional[BlockingStats]:
        """Get statistics for a specific domain"""
        statement = select(BlockingStats).where(BlockingStats.domain == domain)
        return self.session.exec(statement).first()

    def get_all_stats(self) -> List[BlockingStats]:
        """Get statistics for all domains"""
        statement = select(BlockingStats)
        return list(self.session.exec(statement).all())

    def get_success_rate(self, domain: str) -> float:
        """Calculate success rate for domain"""
        stats = self.get_stats(domain)
        if not stats or stats.total_requests == 0:
            return 0.0

        return (stats.successful_requests / stats.total_requests) * 100

    def get_domains_with_low_success_rate(self, threshold: float = 50.0) -> List[BlockingStats]:
        """Get domains with success rate below threshold"""
        all_stats = self.get_all_stats()
        low_success_domains = []

        for stats in all_stats:
            if stats.total_requests > 0:
                success_rate = (stats.successful_requests / stats.total_requests) * 100
                if success_rate < threshold:
                    low_success_domains.append(stats)

        return low_success_domains

    def get_domains_by_circuit_breaker_state(self, state: str) -> List[BlockingStats]:
        """Get domains with specific circuit breaker state"""
        statement = select(BlockingStats).where(BlockingStats.circuit_breaker_state == state)
        return list(self.session.exec(statement).all())

    def reset_old_stats(self, days: int = 7) -> int:
        """Reset statistics older than specified days to adapt to changes"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        statement = select(BlockingStats).where(BlockingStats.updated_at < cutoff_date)
        old_stats = self.session.exec(statement).all()

        reset_count = 0
        for stats in old_stats:
            # Reset counters but keep domain and learned preferences
            stats.total_requests = 0
            stats.successful_requests = 0
            stats.blocked_requests = 0
            stats.rate_limited_requests = 0
            stats.current_delay = 5.0
            stats.circuit_breaker_state = "closed"
            stats.updated_at = datetime.utcnow()

            self.session.add(stats)
            reset_count += 1

        if reset_count > 0:
            self.session.commit()
            logger.info(f"Reset {reset_count} old blocking statistics (older than {days} days)")

        return reset_count

    def get_summary(self) -> Dict:
        """Get summary of all blocking statistics"""
        all_stats = self.get_all_stats()

        total_domains = len(all_stats)
        total_requests = sum(s.total_requests for s in all_stats)
        total_successful = sum(s.successful_requests for s in all_stats)
        total_blocked = sum(s.blocked_requests for s in all_stats)
        total_rate_limited = sum(s.rate_limited_requests for s in all_stats)

        circuit_breaker_open = len([s for s in all_stats if s.circuit_breaker_state == "open"])
        circuit_breaker_half_open = len(
            [s for s in all_stats if s.circuit_breaker_state == "half_open"]
        )

        overall_success_rate = (
            (total_successful / total_requests * 100) if total_requests > 0 else 0.0
        )

        return {
            "total_domains": total_domains,
            "total_requests": total_requests,
            "successful_requests": total_successful,
            "blocked_requests": total_blocked,
            "rate_limited_requests": total_rate_limited,
            "overall_success_rate": round(overall_success_rate, 2),
            "circuit_breaker_open": circuit_breaker_open,
            "circuit_breaker_half_open": circuit_breaker_half_open,
        }

    def get_domain_report(self, domain: str) -> Optional[Dict]:
        """Get detailed report for a specific domain"""
        stats = self.get_stats(domain)
        if not stats:
            return None

        success_rate = self.get_success_rate(domain)

        return {
            "domain": stats.domain,
            "total_requests": stats.total_requests,
            "successful_requests": stats.successful_requests,
            "blocked_requests": stats.blocked_requests,
            "rate_limited_requests": stats.rate_limited_requests,
            "success_rate": round(success_rate, 2),
            "current_delay": stats.current_delay,
            "circuit_breaker_state": stats.circuit_breaker_state,
            "preferred_user_agent": stats.preferred_user_agent,
            "last_success": stats.last_success.isoformat() if stats.last_success else None,
            "last_failure": stats.last_failure.isoformat() if stats.last_failure else None,
            "created_at": stats.created_at.isoformat() if stats.created_at else None,
            "updated_at": stats.updated_at.isoformat() if stats.updated_at else None,
        }
