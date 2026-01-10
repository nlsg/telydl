from typing import Protocol, Awaitable, Callable, Literal
from pathlib import Path

type DownloadStatus = Literal["error", "success", "info"]
type DownloadCallback = Callable[[DownloadStatus, str], Awaitable[None]]

type InfoHook = Callable[[dict], dict | None] | None


class DuplicationError(Exception):
    pass


class InfoValidationError(Exception):
    pass


errors = (InfoValidationError, DuplicationError)


class DownloaderProtocol(Protocol):
    base_directory: Path

    async def download(
        self, urls: list[str] | str, status_callback: DownloadCallback | None = None
    ) -> list[Path | None]: ...
