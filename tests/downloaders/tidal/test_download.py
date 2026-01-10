import pytest
from conftest import ALBUMS, TRACKS, TidalDownloader

ALBUMS, TRACKS, TidalDownloader


LOSSLESS_TRACKS = [TRACKS[0].get("tidal")]

HI_RESS_LOSSLESS_TRACKS = [
    "https://tidal.com/track/77610759/u"  # nirvana - come as you are
]


@pytest.mark.asyncio
async def test_download_hi_ress_lossless_track_from_tidal_link(
    downloader: TidalDownloader,
):
    paths = await downloader.download(HI_RESS_LOSSLESS_TRACKS[0])
