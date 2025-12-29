from pathlib import Path
import logging
import asyncio
import typing

if typing.TYPE_CHECKING:
    from yt_dlp import YoutubeDL

from .youtube import YtDlpDownloader
from .spotify import TokelessSpotifyDownloader
from .abstract import DownloadCallback, DownloaderProtocol

_logger = logging.getLogger(__name__)


class Downloader:
    def __init__(
        self,
        ydl: "YoutubeDL",
        base_directory: Path,
    ):
        self.spotify = TokelessSpotifyDownloader(ydl=ydl, base_directory=base_directory)
        self.youtube = YtDlpDownloader(ydl=ydl, base_directory=base_directory)

    async def download(self, urls: list[str] | str) -> bool:
        urls = (
            [
                urls,
            ]
            if isinstance(urls, str)
            else urls
        )
        tasks = []
        if spotify_urls := [u for u in urls if "open.spotify" in u]:
            tasks.append(self.spotify.download(spotify_urls))

        if youtube_urls := [u for u in urls if "open.spotify" not in u]:
            tasks.append(self.youtube.download(youtube_urls))

        return all(await asyncio.gather(*tasks))


__all__ = [YtDlpDownloader, Downloader]
