"""Downloaders module"""

from app.downloaders.base import BaseDownloader
from app.downloaders.youtube import YoutubeDownload
from app.downloaders.direct import DirectDownload
from app.downloaders.instagram import InstagramDownload
from app.downloaders.pixeldrain import PixeldrainDownload
from app.downloaders.krakenfiles import KrakenFilesDownload
from app.downloaders.spotify import SpotifyDownload

__all__ = [
    "BaseDownloader",
    "YoutubeDownload",
    "DirectDownload",
    "InstagramDownload",
    "PixeldrainDownload",
    "KrakenFilesDownload",
    "SpotifyDownload",
]
