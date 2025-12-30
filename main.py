import asyncio
import signal
import os
import logging
from logging.handlers import RotatingFileHandler

from pathlib import Path

import dotenv


import yt_dlp

from telydl.bot import TelyDlBot
from telydl.downloaders import Downloader

logging.getLogger("httpx").setLevel(logging.WARNING)

_logger = logging.getLogger()
_logger.setLevel(logging.INFO)

formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
_logger.addHandler(console_handler)

file_handler = RotatingFileHandler(
    "bot.log",
    maxBytes=5 * 1024 * 1024,
)
file_handler.setFormatter(formatter)
_logger.addHandler(file_handler)

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

    ydl = yt_dlp.YoutubeDL(ydl_opts)
    downloader = Downloader(
        ydl=ydl, base_directory=Path(os.getenv("TELYDL_BASE_DIR", "downloads"))
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
