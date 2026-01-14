"""User-Agent pool for anti-blocking"""

import random
from typing import Dict
from collections import defaultdict


class UserAgentPool:
    """Manages pool of realistic User-Agent strings with learning"""

    def __init__(self):
        self.user_agents = [
            # Chrome (Desktop)
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            # Firefox (Desktop)
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0",
            # Safari (Desktop)
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
            # Edge (Desktop)
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
            # Chrome (Mobile)
            "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.144 Mobile Safari/537.36",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/120.0.6099.119 Mobile/15E148 Safari/604.1",
            # Firefox (Mobile)
            "Mozilla/5.0 (Android 13; Mobile; rv:121.0) Gecko/121.0 Firefox/121.0",
            # Safari (Mobile)
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1",
        ]

        # Track success/failure per domain per UA
        self.domain_preferences: Dict[str, Dict[str, Dict[str, int]]] = defaultdict(
            lambda: defaultdict(lambda: {"success": 0, "failure": 0})
        )

    def get_random(self) -> str:
        """Get random User-Agent"""
        return random.choice(self.user_agents)

    def get_for_domain(self, domain: str) -> str:
        """Get best User-Agent for specific domain based on history"""
        if domain not in self.domain_preferences:
            return self.get_random()

        # Calculate success rates
        ua_scores = []
        for ua in self.user_agents:
            stats = self.domain_preferences[domain][ua]
            total = stats["success"] + stats["failure"]
            if total == 0:
                # No history, give neutral score
                score = 0.5
            else:
                score = stats["success"] / total

            ua_scores.append((ua, score))

        # Weighted random selection
        if not ua_scores:
            return self.get_random()

        # Sort by score and pick from top performers with some randomness
        ua_scores.sort(key=lambda x: x[1], reverse=True)

        # 70% chance to pick from top 3, 30% random
        if random.random() < 0.7 and len(ua_scores) >= 3:
            return random.choice([ua for ua, _ in ua_scores[:3]])
        else:
            return self.get_random()

    def record_success(self, domain: str, user_agent: str):
        """Record successful request for learning"""
        self.domain_preferences[domain][user_agent]["success"] += 1

    def record_failure(self, domain: str, user_agent: str):
        """Record failed request for learning"""
        self.domain_preferences[domain][user_agent]["failure"] += 1


# Global instance
user_agent_pool = UserAgentPool()
