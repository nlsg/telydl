import pytest
import pytest_asyncio

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from telydl.database import DBService, Track
from telydl.database import init_db

pytest_asyncio = pytest_asyncio


@pytest_asyncio.fixture
async def in_memory_db():
    # Create a new in-memory engine
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async_session = async_sessionmaker(test_engine, expire_on_commit=False)

    # Create tables
    await init_db(engine=test_engine, session=async_session)

    yield async_session

    await test_engine.dispose()


# @pytest.mark.asyncio
# async def test_init():
#     await init_db()


@pytest.mark.asyncio
async def test_get_default_user(in_memory_db):
    async with DBService(session_factory=in_memory_db) as db:
        await db.get_user_by_name("System")


@pytest.mark.asyncio
async def test_service(in_memory_db):
    async with DBService(session_factory=in_memory_db) as db:
        alice = await db.add_user(name="Alice", role="admin")

        track1 = Track(
            name="Song A",
            artists=["Artist X"],
            duration=210,
            origin_url="https://example.com/a",
            id="track-a",
            _raw={"genre": "pop"},
        )
        track2 = Track(
            name="Song B",
            artists=["Artist Y"],
            duration=180,
            origin_url="https://example.com/b",
            id="track-b",
            _raw={"genre": "rock"},
        )

        await db.add_track(track1, added_by=alice.id)
        await db.add_track(track2, added_by=alice.id)

        refreshed_alice = await db.get_user(alice.id)
        assert refreshed_alice.last_action is not None

        all_ids = await db.get_all_track_ids()
        assert len(all_ids) == 2
