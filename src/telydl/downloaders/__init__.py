from .tidal.downloader import TidalDownloader
from .youtube.downloader import YoutubeDownloader

from .downloader import Downloader

__all__ = [Downloader, YoutubeDownloader, TidalDownloader]
