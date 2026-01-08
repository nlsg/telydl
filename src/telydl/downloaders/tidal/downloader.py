import re
from pathlib import Path


from ..procotols import DownloadCallback

from .api import LosslessAPI


class TidalDownloader:
    def __init__(self, base_directory: Path):
        self.base_directory = base_directory
        self.api = LosslessAPI()

    def get_track_ids(self, url: str) -> list[id]:
        if m := re.match(r"https://tidal.com/track/([^/]*)", url):
            # single track from tidal
            return [
                m.group(1),
            ]

        elif m := re.match(r"https://tidal.com/album/([^/]*)", url):
            album_id = m.group(1)

    async def download(
        self, urls: list[str] | str, status_callback: DownloadCallback | None = None
    ) -> list[Path | None]:
        if isinstance(urls, str):
            urls = [
                urls,
            ]
        for url in urls:
            print(url)

        return [Path(".") for _ in urls]
