from pathlib import Path
import inspect
import re
import logging
import asyncio


import yt_dlp

from telydl.util import ensure_list
from telydl.schemas import Track, RawTrack
from telydl.database import DBService

from ..procotols import (
    DownloadCallback,
    InfoHook,
    DuplicationError,
    InfoValidationError,
)
from ..youtube.spotify import TokenlessSpotifyDownloader
from .api import LosslessAPI
from .metadata import assume_extension_from_quality, add_metadata_to_audio


_logger = logging.getLogger(__name__)


def fetch_artist_and_title_from_youtube(url: str) -> tuple[str, str]:
    ydl_opts = {
        "quiet": True,
        "extract_flat": True,
        "skip_download": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
    if (video_title := info.get("fulltitle", info.get("title", ""))).count(" - ") == 1:
        artist, title = video_title.split(" - ")
    else:  # Topic
        artist = (
            info.get("artist")
            or info.get("creator")
            or info.get("uploader")
            or info.get("channel")
        )
        title = info.get("title") or info.get("fulltitle")
    return artist, title


class TidalDownloader:
    def __init__(
        self,
        base_directory: Path = Path("."),
        info_hook: InfoHook | None = None,
        DBService: type[DBService] = DBService,
    ):
        self.base_directory = base_directory
        self.base_directory.mkdir(exist_ok=True)
        self.info_hook = info_hook
        self.api = LosslessAPI()
        self.DBService = DBService

    @ensure_list
    async def fetch_tracks_from_any_url(self, url: str) -> list[Track]:
        ## tidal ##
        if m := re.match(r"https://tidal.com/track/([^/]*)", url):
            raw_track = await self.api.getTrackInfo(m.group(1))
            return Track.from_tidal(raw_track)
        elif m := re.match(r"https://tidal.com/album/([^/]*)", url):
            album = await self.api.getAlbum(m.group(1))
            return [Track.from_tidal(track) for track in album.get("tracks")]

        ## spotify ##
        elif m := re.match(r"https://(open)?.spotify.com/track/([^/]*)", url):
            # unsure if open is always provided..
            data = TokenlessSpotifyDownloader.fetch_track_metadata(url)[0]
            artist = data.get("artist").split("·")[0].strip()
            title = data.get("title")
            return await self.fetch_track(artist, title)
        elif m := re.match(r"https://(open)?.spotify.com/album/([^/]*)", url):
            # unsure if open is always provided..
            data = TokenlessSpotifyDownloader.fetch_track_metadata(url)[0]
            query = data.get("title")
            artist = data.get("artist") or data.get("title")
            if m := re.match(r"(.*) - (?:Album|EP) by ([^|]*) (?: \| Spotify)?", query):
                album, artist = m.groups()
                query = f"{artist} {album}"
            res = await self.api.searchAlbums(query)
            items = [
                i
                for i in res.get("items")
                if (
                    i.get("artist", {}).get("name").lower() in artist.lower()
                    or artist.lower() in i.get("artist", {}).get("name").lower()
                )
            ]
            id = items[0].get("id")
            album = await self.api.getAlbum(id)
            return [Track.from_tidal(track) for track in album.get("tracks")]

        ## youtube ##
        elif m := re.match(r"https://www.youtube.com/watch\?v=([^&]*)", url):
            artist, title = fetch_artist_and_title_from_youtube(url)
            return await self.fetch_track(artist, title)
        _logger.warning(f"cannot retrieve info from url: {url}")

    async def fetch_track(
        self, artist: str, title: str, remixer: str | None = None
    ) -> Track | None:
        if m := re.match(r"(.*)(?:[\(]| - )(.*) [Rr]emix", title):
            # allows for: track (some remix) or track - some remix
            # will break if an artists name contains " - " - unlikely
            title, remixer = m.groups()
        # search tends to fail with multiple artists..
        for sep in "&,":
            artist = artist.split(sep)[0]
        query = f"{artist} - {title}".strip().lower()
        res = await self.api.searchTracks(query)
        items = [
            item
            for item in res.get("items")
            if item.get("artist", {}).get("name", "").lower() in artist.lower()
            and (
                (item.get("version") is remixer)
                or (item.get("version") or "").lower().replace("remix", "").strip()
                == (remixer or "").lower().strip()
            )
            and item.get("title").lower() in title.lower()
        ]
        return Track.from_tidal(items[0]) if items else None

    @staticmethod
    def fmt(track: Track | RawTrack) -> str:
        if isinstance(track, Track):
            return str(track)
        album = artist = track
        if track.get("type") == "ARTIST":
            return f"{artist.get('name')} [{artist.get('id')}] popularity={artist.get('popularity')}"
        if track.get("type") == "ALBUM":
            return f"{album.get('title')} [{artist.get('id')}] copyright={album.get('copyright')} tracks={album.get('numberofTracks')}"
        return f"{track.get('artist', {}).get('name')} - {track.get('title')} [{track.get('id')}] ({track.get('duration', 0) / 60:.2f}min)"

    async def download_track(
        self, track: Track, filename: str | None = None, user: int | str | None = None
    ) -> Path:
        if self.info_hook:
            if inspect.iscoroutinefunction(self.info_hook):
                track = (await self.info_hook(track)) or track
            else:
                track = self.info_hook(track) or track

        quality = track._raw.get("audioQuality")
        data = await self.api.downloadTrack(
            id=track.id,
            quality=quality,
        )
        async with self.DBService() as db:
            if await db.get_track(track.id):
                raise DuplicationError(f"track alredy exists: {track}")

        filename = self.base_directory / (
            filename or f"{track.filename}.{assume_extension_from_quality(quality)}"
        )

        try:
            data = await add_metadata_to_audio(
                audio_data=data, track=track, api=self.api, quality=quality
            )
        except Exception as e:
            _logger.info(f"failed to add metadata track={self.fmt(track)}: {e}")

        with open(filename, "wb") as f:
            f.write(data)

        async with self.DBService() as db:
            await db.add_track(track, user)
        return filename

    async def download(
        self,
        urls: list[str] | str,
        status_callback: DownloadCallback | None = None,
        user: int | str | None = None,
    ) -> list[Path | None]:
        if isinstance(urls, str):
            urls = [
                urls,
            ]
        status_callback = status_callback or (lambda _, __: asyncio.sleep(0))
        res = []
        for url in urls:
            path = None
            for track in await self.fetch_tracks_from_any_url(url):
                try:
                    path = await self.download_track(track, user=user)
                    await status_callback(
                        "success", f"download complete: \n{path=}\ntrack={track}"
                    )  # nono {track=}
                except Exception as e:
                    await status_callback(
                        "error", f"download failed \n{e=}\ntrack={track}"
                    )
                    _logger.error(f"download failed {e=} / track={track}")
                    if isinstance(e, (InfoValidationError, DuplicationError)):
                        path = True  # do not trigger secondary download by youtube-dl
                    continue
            # TODO some resulting paths might be skipped, though its more important, that size of urls and results are equal
            res.append(path)

        return res
