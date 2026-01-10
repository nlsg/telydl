import asyncio
import logging
import shutil
from pathlib import Path


from telydl.downloaders.tidal.downloader import TidalDownloader

from telydl.util import setup_logging


class InfoValidationError(Exception):
    pass


count = 0

setup_logging("recursivescanner.log")


def info_hook(info: dict):
    global count
    title = info.get("fulltitle")
    try:
        duration = int(info.get("duration")) / 60
    except ValueError:
        _logger.error(f"cannot retreive duration from trackinfo: {info}")
        raise InfoValidationError(f"cannot retrieve duration: {title=}, {duration=}")
    if not (2 < duration < 10):
        raise InfoValidationError(f"duration invalid: {title=}, {duration=}")
    count += 1
    if count % 10:
        if (free_gb := shutil.disk_usage("/").free / 1000**3) < 10:
            raise RuntimeError("out off space")
    return info


dl = TidalDownloader(Path("/home/nils/Music/tracks"), info_hook=info_hook)
api = dl.api


_logger = logging.getLogger(__name__)
logging.getLogger().setLevel(logging.DEBUG)


async def download_albums_recursive(
    album: dict,
    depth=5,
    limit=5,
    visited=set(),
    __recursion_counter=0,
):
    if __recursion_counter >= depth:
        return

    _logger.info(f" R:{dl.fmt(album.get('album'))}")
    for track in album.get("tracks"):
        try:
            path = await dl.download_track(track=track)
        except Exception as e:
            _logger.info(f"failed to doenload {dl.fmt(track)}: {e}")
            continue
        _logger.info(f"  T: {dl.fmt(track)} | {path}")

    for a, _ in zip(
        await api.getSimilarAlbums(album.get("album").get("id")), range(limit)
    ):
        await download_albums_recursive(
            album=await api.getAlbum(a.get("id")),
            depth=depth,
            limit=limit,
            __recursion_counter=__recursion_counter + 1,
        )


async def download_artists_recursive(
    artist: dict,
    depth=5,
    limit=5,
    visited=set(),
    __recursion_counter=0,
):
    if __recursion_counter >= depth:
        return

    _logger.info(f"A:{dl.fmt(artist)}")
    for album in artist.get("albums"):
        await download_albums_recursive(
            album=await api.getAlbum(album.get("id")),
            depth=depth,
            limit=limit,
            visited=visited,
        )

    for a, _ in zip(await api.getSimilarArtists(artist.get("id")), range(limit)):
        await download_artists_recursive(
            artist=await api.getArtist(a.get("id")),
            depth=depth,
            limit=limit,
            __recursion_counter=__recursion_counter + 1,
        )


async def main():
    artists = await dl.api.searchArtists("landhouse")
    first_id = artists.get("items")[0].get("id")
    artist = await dl.api.getArtist(first_id)
    await download_artists_recursive(artist)


if __name__ == "__main__":
    asyncio.run(main())
