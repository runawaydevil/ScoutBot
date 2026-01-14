"""HTTP header builder for anti-blocking"""

import random


class HeaderBuilder:
    """Builds realistic HTTP headers for requests"""

    ACCEPT_LANGUAGES = [
        "en-US,en;q=0.9",
        "en-GB,en;q=0.9",
        "pt-BR,pt;q=0.9,en;q=0.8",
        "es-ES,es;q=0.9,en;q=0.8",
    ]

    def build_headers(self, url: str, user_agent: str) -> dict:
        """Build complete header set for request"""
        headers = {
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": random.choice(self.ACCEPT_LANGUAGES),
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
        }

        # Add Referer for Reddit
        if "reddit.com" in url:
            headers["Referer"] = "https://www.reddit.com/"

        return headers


# Global instance
header_builder = HeaderBuilder()
