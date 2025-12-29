from typing import Protocol, Awaitable, Callable, Iterable
from pathlib import Path
import asyncio
import typing
import logging

if typing.TYPE_CHECKING:
    from yt_dlp import YoutubeDL
_logger = logging.getLogger(__name__)

type DownloadCallback = Callable[[str], Awaitable[None]]


class DownloaderProtocol(Protocol):
    base_directory: Path
    start_callback: DownloadCallback | None
    success_callback: DownloadCallback | None
    error_callback: DownloadCallback | None

    async def download(self, urls: list[str] | str) -> bool: ...


class BaseDownloader:
    async def download(self, urls: str | list[str]) -> bool:
        url_list = urls if isinstance(urls, list) else [urls]
        return await asyncio.to_thread(self._download_sync, url_list)

    def _download_sync(urls: Iterable[str]) -> bool:
        raise NotImplementedError

    def iter_infos(self, url_list: list[str]):
        raise NotImplementedError

    def _run_callback(self, cb: DownloadCallback | None, url: str) -> None:
        if cb is None:
            return
        try:
            asyncio.run(cb(url))
        except Exception:
            loop = asyncio.get_event_loop()
            loop.create_task(cb(url))


class BaseYDLDownloader(BaseDownloader, DownloaderProtocol):
    ydl: "YoutubeDL"
    base_directory: Path

    def __init__(self, ydl: "YoutubeDL"):
        self.ydl = ydl
        self.ydl.params["outtmpl"]["default"] = str(
            self.base_directory / "%(title)s.%(ext)s"
        )

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

    def download_from_info(self, info: dict):
        self._set_outtmpl(info)
        self.ydl.process_info(info)
        return self.ydl.prepare_filename(info)

    def _download_sync(
        self,
        url_list: list[str],
    ) -> bool:
        failed = False

        for info in self.iter_infos(url_list):
            name = f"{info.get('artist')} - {info.get('fulltitle')}"
            self._run_callback(self.start_callback, name)
            try:
                self.download_from_info(info)
                self._run_callback(self.success_callback, name)
            except Exception:
                _logger.exception("Error downloading %s", name)
                failed = True
                self._run_callback(self.error_callback, name)

        return not failed
