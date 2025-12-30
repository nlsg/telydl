from typing import Protocol, Awaitable, Callable, Iterable, Literal
from pathlib import Path
import asyncio
import typing
import logging
from abc import ABC, abstractclassmethod

if typing.TYPE_CHECKING:
    from yt_dlp import YoutubeDL
_logger = logging.getLogger(__name__)

type DownloadStatus = Literal["error", "success", "info"]
type DownloadCallback = Callable[[DownloadStatus, str], Awaitable[None]]
type InfoHook = Callable[[dict], dict | None] | None


class DownloaderProtocol(Protocol):
    base_directory: Path

    async def download(
        self, urls: list[str] | str, status_callback: DownloadCallback | None = None
    ) -> list[Path | None]: ...


class BaseDownloader(ABC):
    def __init__(self):
        self.loop: asyncio.AbstractEventLoop = None

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        self.loop = loop

    async def download(
        self, urls: str | list[str], status_callback: DownloadCallback | None = None
    ) -> bool:
        url_list = urls if isinstance(urls, list) else [urls]
        return await asyncio.to_thread(self._download_sync, url_list, status_callback)

    def _download_sync(
        urls: Iterable[str], status_callback: DownloadCallback | None = None
    ) -> bool:
        raise NotImplementedError

    @staticmethod
    @abstractclassmethod
    def iter_infos(self, url_list: list[str]):
        raise NotImplementedError

    def _run_callback(
        self, cb: DownloadCallback | None, status: DownloadStatus, message: str
    ) -> None:
        if cb is None or self.loop is None:
            return
        _logger.debug(f"running callback: {status=}, {message=}")
        self.loop.call_soon_threadsafe(lambda: asyncio.create_task(cb(status, message)))


class BaseYDLDownloader(BaseDownloader):
    def __init__(
        self,
        ydl: "YoutubeDL",
        base_directory: Path,
        info_hook: InfoHook = None,
    ):
        super().__init__()
        self.ydl = ydl
        self.base_directory = base_directory
        self.ydl.params["outtmpl"]["default"] = str(
            self.base_directory / "%(title)s.%(ext)s"
        )
        self.base_directory = Path(base_directory)
        self.base_directory.mkdir(parents=True, exist_ok=True)
        self.info_hook = info_hook

    def _set_outtmpl(self, info: dict):
        channel = info.get("channel") or info.get("uploader") or ""
        if channel.lower().endswith("- topic"):
            self.ydl.params["outtmpl"]["default"] = str(
                self.base_directory
                / (channel.replace("Topic", "").strip("- ") + " - %(title)s.%(ext)s")
            )
        else:
            self.ydl.params["outtmpl"]["default"] = str(
                self.base_directory / "%(title)s.%(ext)s"
            )

    def download_from_info(self, info: dict) -> Path:
        self._set_outtmpl(info)
        self.ydl.process_info(info)
        return Path(self.ydl.prepare_filename(info))

    def _download_sync(
        self, url_list: list[str], status_callback: DownloadCallback | None = None
    ) -> list[Path | None]:
        results = []
        for info in self.iter_infos(url_list):
            url = info.get("original_url")
            name = (
                f"{info.get('artist') or info.get('channel')} - {info.get('fulltitle')}"
            )
            self._run_callback(status_callback, "info", f"starting: {name}")
            try:
                if self.info_hook:
                    info = self.info_hook(info) or info
                results.append(path := self.download_from_info(info))
                self._run_callback(
                    status_callback, "success", f"{name}\n{path=}\n{url=}"
                )
            except Exception as e:
                self._run_callback(status_callback, "error", f"{name}: {e}")
                _logger.exception(e)
                results.append(None)

        return results
