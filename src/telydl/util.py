import re
import subprocess
import logging
from logging.handlers import RotatingFileHandler

URL_REGEX = re.compile(
    r"https?://[^\s<>\"]+",
    re.IGNORECASE,
)


def run_shell(*args: str) -> str:
    result = subprocess.run(
        args,
        capture_output=True,
        text=True,
    )

    return result.stderr.strip() if result.returncode != 0 else result.stdout.strip()


def setup_logging():
    _logger = logging.getLogger()
    _logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    _logger.addHandler(console_handler)

    file_handler = RotatingFileHandler(
        "bot.log",
        maxBytes=5 * 1024 * 1024,
    )
    file_handler.setFormatter(formatter)
    _logger.addHandler(file_handler)

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("telydl").setLevel(logging.DEBUG)
