import asyncio
import signal
import os
import logging

from pathlib import Path

import dotenv


import yt_dlp

from telydl.bot import TelyDlBot
from telydl.downloaders import YoutubeDownloader, Downloader

from telydl.util import setup_logging

setup_logging()

_logger = logging.getLogger(__name__)
_logger.setLevel(logging.DEBUG)
_logger.debug("starting application...")

dotenv.load_dotenv()


class InfoValidationError(Exception):
    pass


def info_hook(info: dict):
    title = info.get("fulltitle")
    try:
        duration = int(info.get("duration")) / 60
    except ValueError:
        _logger.error(f"cannot retreive duration from trackinfo: {info}")
        raise InfoValidationError(f"cannot retrieve duration: {title=}, {duration=}")
    if not (2 < duration < 10):
        raise InfoValidationError(f"duration invalid: {title=}, {duration=}")
    return info


async def tely_main():
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

    base_directory = Path(os.getenv("TELYDL_BASE_DIRECTORY", "downloads")).resolve()

    _logger.debug(f"{base_directory=} / {base_directory.exists()}")

    ydl = yt_dlp.YoutubeDL(ydl_opts)
    yt_downloader = YoutubeDownloader(
        ydl=ydl,
        base_directory=base_directory,
        info_hook=info_hook,
    )
    downloader = Downloader(
        base_directory=base_directory, youtube_downloader=yt_downloader
    )
    _logger.debug("initialized downloader")
    bot = TelyDlBot(
        token=os.getenv("TELYDL_BOT_TOKEN"),
        downloader=downloader,
        whitelist=[int(id) for id in os.getenv("TELYDL_WHITELIST").split(",")],
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
    asyncio.run(tely_main())
