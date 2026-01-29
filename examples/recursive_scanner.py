import asyncio
import logging
import shutil
import os
from pathlib import Path

import dotenv


from telegram import Bot

from telydl.downloaders.tidal.downloader import TidalDownloader
from telydl.downloaders.procotols import InfoValidationError, DuplicationError
from telydl.schemas import Track, RawTrack

from telydl.util import setup_logging
from telydl.database import DBService, init_db


setup_logging("recursivescanner.log")
logging.getLogger("httpcore").setLevel(logging.INFO)
logging.getLogger("telegram").setLevel(logging.INFO)

count = 0


async def info_hook(info: Track | RawTrack):
    global count
    try:
        duration = int(info.get("duration")) / 60
    except ValueError:
        raise InfoValidationError("cannot retrieve duration")
    if not (2 < duration < 10):
        raise InfoValidationError("duration invalid")
    count += 1
    if not (count % 10):
        if (free_gb := shutil.disk_usage("/").free / 1000**3) < 10:
            await send_notification(f"ERROR: out off space, free: {free_gb}GB")
            raise RuntimeError(f"out of space, free: {free_gb}GB")
        if not (count % 50):
            await send_notification(f"still running: {count=} / {free_gb=}GB")
    return info


dotenv.load_dotenv()
dl = TidalDownloader(
    Path("/home/nils/Music/tracks"), info_hook=info_hook, DBService=DBService
)
api = dl.api

me = os.getenv("TELYDL_WHITELIST").split(",")[0]


async def send_notification(message: str):
    try:
        bot = Bot(os.getenv("TELYDL_BOT_TOKEN"))
        await bot.send_message(chat_id=me, text=message)
    except Exception:
        pass


async def notify_error(e, track):
    _logger.info(f"failed to download {dl.fmt(track)}: {e}")
    if not isinstance(e, (InfoValidationError, DuplicationError)):
        await send_notification(f"serious error: {e}")


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
    for raw_track in album.get("tracks"):
        try:
            track = Track.from_tidal(raw_track)
            if track.id in visited:
                raise RuntimeError("track already downloaded")
            path = await dl.download_track(track=track)
        except Exception as e:
            await notify_error(e, track)
            continue
        _logger.info(f"  T: {dl.fmt(track)} | {path}")

    await send_notification(f"album complete: {dl.fmt(album)}")
    for a, _ in zip(
        await api.getSimilarAlbums(album.get("album").get("id")), range(limit)
    ):
        await download_albums_recursive(
            album=await api.getAlbum(a.get("id")),
            depth=depth,
            limit=limit,
            visited=visited,
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
    await send_notification(f"artist complete: {dl.fmt(artist)}")

    for a, _ in zip(await api.getSimilarArtists(artist.get("id")), range(limit)):
        await download_artists_recursive(
            artist=await api.getArtist(a.get("id")),
            depth=depth,
            limit=limit,
            __recursion_counter=__recursion_counter + 1,
        )


async def main():
    try:
        await init_db()
    except Exception as e:
        await send_notification(f"init db exception: {e=}")
        _logger.error(f"init db exception: {e=}")
    for artist_name in "landhouse", "ninze", "apaj":
        try:
            artists = await dl.api.searchArtists(artist_name)
            first_id = artists.get("items")[0].get("id")
            artist = await dl.api.getArtist(first_id)
            await send_notification(f"main/starting with artist: {dl.fmt(artist)}")
            await download_artists_recursive(artist)
            await send_notification(f"main/finished with artist: {dl.fmt(artist)}")
        except Exception as e:
            await send_notification(f"main/exception: {dl.fmt(artist)}\n{e=}")
            _logger.error(f"main/exception: {dl.fmt(artist)}\n{e=}")
            continue


if __name__ == "__main__":
    asyncio.run(main())
