from pathlib import Path

import pytest
import pytest_asyncio

from telydl.downloaders.tidal.downloader import TidalDownloader

pytest_asyncio = pytest_asyncio

TRACKS = [
    {  # Landhouse - Robots
        "tidal": "https://tidal.com/track/429125301/u",
        "spotify": "https://open.spotify.com/track/4Z34nXz4uvQGctL5FFl8gB?si=4553f561024440bb",
        "youtube-topic": "https://www.youtube.com/watch?v=Kih04PB6RZA&pp=ygUcbGFuZGhvdXNlICYgcmFkZGFudHplIHJvYm90cw%3D%3D",
        "youtube": "https://www.youtube.com/watch?v=KUetdiD1Bo4&pp=ygUcbGFuZGhvdXNlICYgcmFkZGFudHplIHJvYm90cw%3D%3D",
    },
    {  # Landhouse - Robots (Sanõj Remix)
        # "tidal": "",
        "spotify": "https://open.spotify.com/track/60k5p5p1Bz8T2AMvD6i0mG?si=83afe47ce1a84ad2",
        "youtube-topic": "https://www.youtube.com/watch?v=zHQM7icVdi4",
        "youtube": "https://www.youtube.com/watch?v=XCatGlkpRQU&pp=ygUcbGFuZGhvdXNlICYgcmFkZGFudHplIHJvYm90cw%3D%3D",
    },
]

ALBUMS = [
    {  # Landhouse - Robots in Lilics Spaceships
        "spotify": "https://open.spotify.com/album/2dlUNuLVmFPse9LHzgbk6f?si=e_pl9ce6T2mRKob8H4EbaA",
        "tidal": "https://tidal.com/album/429125300/u",
    },
    {  # Landhouse - Life
        "tidal": "https://tidal.com/album/109474035/u",
        "spotify": "https://open.spotify.com/album/0GE0jP4MK5bu9RjADBD6rQ?si=95cb2d04d4d44aff",
    },
]


@pytest.fixture
def downloader():
    return TidalDownloader(Path("."))


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
