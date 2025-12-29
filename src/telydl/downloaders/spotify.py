import logging
from pathlib import Path

from telydl.downloaders.abstract import DownloadCallback, BaseYDLDownloader
import re

import requests
from bs4 import BeautifulSoup

import typing

if typing.TYPE_CHECKING:
    from yt_dlp import YoutubeDL

_logger = logging.getLogger(__name__)
_logger.setLevel(logging.DEBUG)


class TokelessSpotifyDownloader(BaseYDLDownloader):
    base_directory: Path
    start_callback: DownloadCallback | None
    success_callback: DownloadCallback | None
    error_callback: DownloadCallback | None

    def __init__(
        self,
        ydl: "YoutubeDL",
        base_directory: str = "downloads",
        start_callback: DownloadCallback | None = None,
        success_callback: DownloadCallback | None = None,
        error_callback: DownloadCallback | None = None,
    ):
        self.base_directory = Path(base_directory)
        self.base_directory.mkdir(parents=True, exist_ok=True)

        self.start_callback = start_callback
        self.success_callback = success_callback
        self.error_callback = error_callback
        super().__init__(ydl=ydl)

    def _fetch_track_metadata(self, spotify_url: str) -> dict:
        """
        Fetch metadata for a Spotify track/album/playlist.
        Only uses HTML scraping (no tokens needed).
        Returns a list of dicts with 'title' and 'artist'.
        """
        r = requests.get(spotify_url)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        # Try Open Graph tags first (works for track/album/playlist pages)
        title = soup.find("meta", property="og:title")
        desc = soup.find("meta", property="og:description")

        if title and desc:
            # Single track
            return [{"title": title["content"], "artist": desc["content"]}]

        # Playlist/album scraping fallback
        m = re.search(r'(\{"name":".*?,"uri":".*?","artists":\[.*?\]\})', r.text)
        if m:
            items = re.findall(r'(\{"name":".*?","artists":\[.*?\]\})', r.text)
            tracks = []
            for item in items:
                track_title = re.search(r'"name":"(.*?)"', item).group(1)
                artist = re.search(r'"artists":\[{"name":"(.*?)"', item).group(1)
                tracks.append({"title": track_title, "artist": artist})
            return tracks

        # Fallback
        raise RuntimeError("Unable to fetch Spotify metadata")

    def iter_infos(self, url_list: list[str]):
        for url in url_list:
            tracks = self._fetch_track_metadata(url)

            for track in tracks:
                query = f"{track['artist']} - {track['title']}"
                _logger.debug(f"Searching YouTube for: {query}")
                try:
                    yield self.ydl.extract_info(
                        f"ytsearch1:{query}", download=False
                    ).get("entries")[0]
                except IndexError:
                    _logger.error(f"cannot find download for track: {track}")
