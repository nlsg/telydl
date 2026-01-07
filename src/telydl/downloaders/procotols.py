from typing import Protocol, Awaitable, Callable, Literal
from pathlib import Path

type DownloadStatus = Literal["error", "success", "info"]
type DownloadCallback = Callable[[DownloadStatus, str], Awaitable[None]]


class DownloaderProtocol(Protocol):
    base_directory: Path

    async def download(
        self, urls: list[str] | str, status_callback: DownloadCallback | None = None
    ) -> list[Path | None]: ...
