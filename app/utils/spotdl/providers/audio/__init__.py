"""
Audio providers for spotdl.
"""

from app.utils.spotdl.providers.audio.bandcamp import BandCamp
from app.utils.spotdl.providers.audio.base import (
    ISRC_REGEX,
    AudioProvider,
    AudioProviderError,
    YTDLLogger,
)
from app.utils.spotdl.providers.audio.piped import Piped
from app.utils.spotdl.providers.audio.soundcloud import SoundCloud
from app.utils.spotdl.providers.audio.youtube import YouTube
from app.utils.spotdl.providers.audio.ytmusic import YouTubeMusic

__all__ = [
    "YouTube",
    "YouTubeMusic",
    "SoundCloud",
    "BandCamp",
    "Piped",
    "AudioProvider",
    "AudioProviderError",
    "YTDLLogger",
    "ISRC_REGEX",
]
