from pathlib import Path

from .procotols import DownloadCallback

from .tidal.downloader import TidalDownloader
from .youtube.downloader import YoutubeDownloader

import logging

_logger = logging.getLogger(__name__)


class Downloader:
    def __init__(
        self,
        base_directory: Path,
        tidal_downloader: TidalDownloader | None = None,
        youtube_downloader: YoutubeDownloader | None = None,
    ):
        self.tidal_downloader = tidal_downloader or TidalDownloader(
            base_directory=base_directory
        )
        self.youtube_downloader = youtube_downloader or YoutubeDownloader(
            base_directory=base_directory
        )

    async def download(
        self, urls: list[str] | str, status_callback: DownloadCallback | None = None
    ) -> list[Path | None]:
        if isinstance(urls, str):
            urls = [
                urls,
            ]
        results = await self.tidal_downloader.download(
            urls=urls, status_callback=status_callback
        )

        if all(results):
            _logger.info("complete tidal success!")
            return results

        results_ = []
        for result, url in zip(results, urls):
            if result:
                results_.append(result)
                continue
            res = await self.youtube_downloader.download(
                url, status_callback=status_callback
            )
            results_.append(res[0])
        return results_
