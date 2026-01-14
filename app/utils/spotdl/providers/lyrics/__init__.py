"""
Lyrics providers for spotdl.
"""

from app.utils.spotdl.providers.lyrics.azlyrics import AzLyrics
from app.utils.spotdl.providers.lyrics.base import LyricsProvider
from app.utils.spotdl.providers.lyrics.genius import Genius
from app.utils.spotdl.providers.lyrics.musixmatch import MusixMatch
from app.utils.spotdl.providers.lyrics.synced import Synced

__all__ = ["AzLyrics", "Genius", "MusixMatch", "Synced", "LyricsProvider"]
