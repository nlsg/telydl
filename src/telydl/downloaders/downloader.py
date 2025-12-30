from pathlib import Path
import logging
import asyncio
import typing
import itertools

if typing.TYPE_CHECKING:
    from yt_dlp import YoutubeDL

from .youtube import YtDlpDownloader
from .spotify import TokelessSpotifyDownloader
from .abstract import DownloadCallback

_logger = logging.getLogger(__name__)


class Downloader:
    def __init__(
        self,
        ydl: "YoutubeDL",
        base_directory: Path,
    ):
        self.spotify = TokelessSpotifyDownloader(
            ydl=ydl, base_directory=base_directory / "spotify"
        )
        self.youtube = YtDlpDownloader(
            ydl=ydl, base_directory=base_directory / "youtube"
        )

    def set_loop(self, loop):
        self.spotify.set_loop(loop)
        self.youtube.set_loop(loop)

    async def download(
        self, urls: list[str] | str, status_callback: DownloadCallback | None = None
    ) -> list[Path | None]:
        urls = (
            [
                urls,
            ]
            if isinstance(urls, str)
            else urls
        )
        tasks = []
        if spotify_urls := [u for u in urls if "open.spotify" in u]:
            tasks.append(
                self.spotify.download(spotify_urls, status_callback=status_callback)
            )

        if youtube_urls := [u for u in urls if "open.spotify" not in u]:
            tasks.append(
                self.youtube.download(youtube_urls, status_callback=status_callback)
            )

        result = await asyncio.gather(*tasks)
        return list(itertools.chain(*result))
