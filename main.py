import asyncio
import signal
import os
import logging
import shutil

from pathlib import Path

import dotenv


import yt_dlp

from telydl.bot import TelyDlBot
from telydl.downloaders import YoutubeDownloader, Downloader, TidalDownloader

from telydl.downloaders.procotols import InfoValidationError
from telydl.schemas import Track, RawTrack
from telydl.util import setup_logging

setup_logging()

_logger = logging.getLogger(__name__)
_logger.setLevel(logging.DEBUG)
_logger.debug("starting application...")

dotenv.load_dotenv()


count = 0

MIN_DURATION = int(os.getenv("TELYDL_MIN_DURATION", "2"))
MAX_DURATION = int(os.getenv("TELYDL_MAX_DURATION", "10"))

MIN_FREE_DISK_SPACE = int(os.getenv("TELYDL_MIN_FREE_DISK_SPACE", "10"))
CHECK_DISK_FREQUENCY = int(os.getenv("TELYDL_CHECK_DISK_FREQUENCY", "10"))

BASE_DIRECTORY = Path(os.getenv("TELYDL_BASE_DIRECTORY", "downloads")).resolve()

WHITE_LIST = os.getenv("TELYDL_WHITELIST", "")
ADMIN = os.getenv("TELYDL_ADMIN")

if not (BOT_TOKEN := os.getenv("TELYDL_BOT_TOKEN")):
    _logger.error("cannot find bot token in environment: TELYDL_BOT_TOKEN")
    exit(1)


def info_hook(info: Track | RawTrack):
    global count
    try:
        duration = int(info.get("duration")) / 60
    except ValueError:
        raise InfoValidationError("cannot retrieve duration")
    if not (MIN_DURATION < duration < MAX_DURATION):
        raise InfoValidationError("duration invalid")
    count += 1
    if count % CHECK_DISK_FREQUENCY:
        if (free_gb := shutil.disk_usage("/").free / 1000**3) < MIN_FREE_DISK_SPACE:
            raise RuntimeError(f"out off space, free: {free_gb} Gb")
    return info


async def main():
    # ---- codec-specific configuration ----
    mode = "mp3"
    if mode == "mp3":
        postprocessor = {
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            # LAME V0 → highest sane MP3 quality, favors size over loss
            "preferredquality": "0",
        }
    elif mode == "aac":
        postprocessor = {
            "key": "FFmpegExtractAudio",
            "preferredcodec": "aac",
            # High-quality AAC VBR, encoder decides bitrate
            "preferredquality": "0",
        }
    else:
        raise ValueError(f"Unsupported mode: {mode}")

    ydl_opts = {
        "format": "bestaudio/best",
        # Behavior
        "quiet": True,
        "noplaylist": True,
        "ignoreerrors": False,
        "nooverwrites": False,
        # One lossy conversion max, no upsampling caps
        "postprocessors": [postprocessor],
    }

    stop_event = asyncio.Event()

    _logger.debug(f"{BASE_DIRECTORY=} / {BASE_DIRECTORY.exists()}")

    ydl = yt_dlp.YoutubeDL(ydl_opts)
    yt_downloader = YoutubeDownloader(
        ydl=ydl,
        base_directory=BASE_DIRECTORY,
        info_hook=info_hook,
    )
    tidal_downloader = TidalDownloader(
        base_directory=BASE_DIRECTORY, info_hook=info_hook
    )
    downloader = Downloader(
        base_directory=BASE_DIRECTORY,
        youtube_downloader=yt_downloader,
        tidal_downloader=tidal_downloader,
    )
    _logger.debug("initialized downloader")
    bot = TelyDlBot(
        token=BOT_TOKEN,
        downloader=downloader,
        admin=ADMIN,
        whitelist=[int(id) for id in WHITE_LIST.split(",")],
    )
    _logger.debug("initialized TelyDlBot")

    loop = asyncio.get_running_loop()
    yt_downloader.set_loop(loop)

    await bot.start()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)

    await stop_event.wait()
    await bot.stop()
    _logger.debug("application stopped!")


if __name__ == "__main__":
    asyncio.run(main())
