import logging
from pathlib import Path

from telydl.downloaders.abstract import DownloadCallback, BaseYDLDownloader
import yt_dlp

_logger = logging.getLogger(__name__)
_logger.setLevel(logging.DEBUG)


class YtDlpDownloader(BaseYDLDownloader):
    base_directory: Path
    start_callback: DownloadCallback | None
    success_callback: DownloadCallback | None
    error_callback: DownloadCallback | None

    def __init__(
        self,
        ydl: yt_dlp.YoutubeDL,
        base_directory: str = "downloads",
        start_callback: DownloadCallback = None,
        success_callback: DownloadCallback = None,
        error_callback: DownloadCallback = None,
    ):
        self.base_directory = Path(base_directory)
        self.start_callback = start_callback
        self.success_callback = success_callback
        self.error_callback = error_callback
        self.base_directory.mkdir(parents=True, exist_ok=True)
        super().__init__(ydl=ydl)

    def _post_process(self, data):
        if (
            data.get("postprocessor") == "MoveFiles"
            and data.get("status") == "finished"
        ):
            info = data.get("info_dict")
            filepath = Path(info.get("filepath"))
            _logger.info(f"Downloaded and moved file: {filepath}")

    def iter_infos(self, url_list: list[str]):
        for url in url_list:
            info = self.ydl.extract_info(url, download=False)
            if "entries" in info:
                _logger.debug(
                    f"got url of type: {info.get('_type')} entries: {len(info.get('entries'))}"
                )
                for entry in info["entries"]:
                    if entry is None:
                        continue
                    yield entry
            else:
                yield info
