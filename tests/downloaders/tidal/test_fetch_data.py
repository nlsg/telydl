import pytest
import pytest_asyncio  # noqa: F401.

from conftest import ALBUMS, TRACKS, downloader, TidalDownloader  # noqa: F401.


__used__ = [
    pytest_asyncio,
    downloader,
]


@pytest.mark.asyncio
async def test_fetch_tracks_from_any_url(downloader: TidalDownloader):
    for track in TRACKS:
        tracks_per_provider = [
            await downloader.fetch_tracks_from_any_url(link) for link in track.values()
        ]
        got_the_same = all(
            i[0].get("id") == tracks_per_provider[0][0].get("id")
            for i in tracks_per_provider[:-1]
        )
        assert got_the_same


@pytest.mark.asyncio
async def test_search_track(downloader: TidalDownloader):
    tracks = await downloader.fetch_tracks_from_any_url(TRACKS[0].get("tidal"))
    track = await downloader.fetch_track("landhouse", "robots")

    assert tracks[0].get("id") == track.get("id")

    tracks = await downloader.fetch_tracks_from_any_url(TRACKS[1].get("spotify"))
    assert (await downloader.fetch_track("landhouse", "robots", "Sanõj")).get(
        "id"
    ) == tracks[0].get("id")


@pytest.mark.asyncio
async def test_fetch_album_from_any_url(downloader: TidalDownloader):
    for album in ALBUMS:
        albums_per_provider = [
            await downloader.fetch_tracks_from_any_url(link) for link in album.values()
        ]
        ids = [sum(track.get("id") for track in album) for album in albums_per_provider]
        got_the_same = all(id == ids[0] for id in ids)
        assert got_the_same
