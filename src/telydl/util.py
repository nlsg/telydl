import re
import time
import subprocess
import logging
from logging.handlers import RotatingFileHandler

URL_REGEX = re.compile(
    r"https?://[^\s<>\"]+",
    re.IGNORECASE,
)


def run_shell(*args: str) -> str:
    _logger = logging.getLogger("shell")
    try:
        t = time.perf_counter()
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
        )
    except Exception as e:
        return str(e)

    _logger.info(f"running shellcommand: {args}")
    output = result.stderr.strip() if result.returncode != 0 else result.stdout.strip()
    return output + f"\ntook: {time.perf_counter() - t:.3}s"


def setup_logging(log_file: str):
    _logger = logging.getLogger()
    _logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    _logger.addHandler(console_handler)

    if log_file:
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=5 * 1024 * 1024,
        )
        file_handler.setFormatter(formatter)
        _logger.addHandler(file_handler)

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("telydl").setLevel(logging.DEBUG)
