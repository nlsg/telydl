import asyncio
import signal
import os
import logging

from pathlib import Path

import dotenv


import yt_dlp

from telydl.bot import TelyDlBot
from telydl.downloaders import Downloader

from telydl.util import setup_logging

setup_logging()

_logger = logging.getLogger(__name__)
_logger.setLevel(logging.DEBUG)
_logger.debug("starting application...")

dotenv.load_dotenv()


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
        # Always start from best available source (usually Opus)
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
    downloader = Downloader(
        ydl=ydl,
        base_directory=base_directory,
    )
    _logger.debug("initialized downloader")
    bot = TelyDlBot(
        token=os.getenv("TELYDL_BOT_TOKEN"),
        downloader=downloader,
        whitelist=[int(id) for id in os.getenv("TELYDL_WHITELIST").split(",")],
    )
    _logger.debug("initialized TelyDlBot")

    loop = asyncio.get_running_loop()
    downloader.set_loop(loop)

    await bot.start()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)

    await stop_event.wait()
    await bot.stop()
    _logger.debug("application stopped!")


if __name__ == "__main__":
    asyncio.run(tely_main())
