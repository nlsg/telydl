import logging

from telydl.downloaders.youtube.abstract import BaseYDLDownloader
import re

import requests
from bs4 import BeautifulSoup

import typing

if typing.TYPE_CHECKING:
    pass

_logger = logging.getLogger(__name__)
_logger.setLevel(logging.DEBUG)


class TokenlessSpotifyDownloader(BaseYDLDownloader):
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

        if re.search(r'(\{"name":".*?,"uri":".*?","artists":\[.*?\]\})', r.text):
            tracks = []
            for item in re.findall(r'(\{"name":".*?","artists":\[.*?\]\})', r.text):
                track_title = re.search(r'"name":"(.*?)"', item).group(1)
                artist = re.search(r'"artists":\[{"name":"(.*?)"', item).group(1)
                tracks.append({"title": track_title, "artist": artist})
            return tracks

        raise RuntimeError("Unable to fetch Spotify metadata")

    def iter_infos(self, url_list: list[str]):
        for url in url_list:
            try:
                tracks = self._fetch_track_metadata(url)
            except RuntimeError as e:
                _logger.error(e)
                continue

            for track in tracks:
                query = f"{track['artist']} - {track['title']}"
                _logger.debug(f"Searching YouTube for: {query}")
                try:
                    yield self.ydl.extract_info(
                        f"ytsearch1:{query}", download=False
                    ).get("entries")[0]
                except IndexError:
                    _logger.error(f"cannot find download for track: {track}")
