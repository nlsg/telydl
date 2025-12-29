import logging
from pathlib import Path

from telydl.downloaders.abstract import BaseYDLDownloader

_logger = logging.getLogger(__name__)
_logger.setLevel(logging.DEBUG)


class YtDlpDownloader(BaseYDLDownloader):
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
