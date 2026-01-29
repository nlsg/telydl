from datetime import datetime, timezone
from typing import Optional, Set, Any, Dict
import logging

from sqlalchemy import String, Integer, DateTime, ForeignKey, select, JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from telydl.schemas import Track

# ------------------------
# DB setup
# ------------------------
DB_URL = "sqlite+aiosqlite:///data.db"
engine = create_async_engine(DB_URL, echo=False)
Session = async_sessionmaker(engine, expire_on_commit=False)
_logger = logging.getLogger(__name__)


# ------------------------
# Base
# ------------------------
class Base(DeclarativeBase):
    pass


# ------------------------
# Mixins
# ------------------------
class IdNameMixin:
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)


# ------------------------
# Models
# ------------------------
class User(IdNameMixin, Base):
    __tablename__ = "users"

    role: Mapped[str] = mapped_column(String, default="user")
    registered_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_action: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class TrackDB(IdNameMixin, Base):
    __tablename__ = "tracks"

    filename: Mapped[str] = mapped_column(String, nullable=False)
    artist: Mapped[str] = mapped_column(String, nullable=False)
    added_by: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )
    raw: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)


# ------------------------
# DB Service
# ------------------------
class DBService:
    def __init__(self, session_factory: Optional[async_sessionmaker] = None):
        self._session: Optional[AsyncSession] = None
        self._session_factory = session_factory or Session

    async def __aenter__(self) -> "DBService":
        self._session = self._session_factory()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self._session:
            try:
                if exc_type:
                    await self._session.rollback()
                else:
                    await self._session.commit()
            finally:
                await self._session.close()
                self._session = None

    # ---------- Users ----------
    async def add_user(self, *, name: str, role: str = "user") -> User:
        user = User(name=name, role=role)
        self._session.add(user)
        await self._session.flush()  # assign ID
        return user

    async def get_user_by_name(self, name: str) -> Optional[User]:
        """Return the first user with this name, or None"""
        assert self._session is not None
        result = await self._session.execute(select(User).where(User.name == name))
        return result.scalars().one_or_none()

    async def get_user(self, user_id: int) -> Optional[User]:
        return await self._session.get(User, user_id)

    # ---------- Tracks ----------
    async def add_track(
        self, track: Track, added_by: int | str | None = None
    ) -> TrackDB:
        if isinstance(added_by, int):
            user = await self.get_user(added_by)
        else:
            user = await self.get_user_by_name(added_by or "System")
        db_track = TrackDB(
            id=track.id,
            name=track.name,
            filename=track.filename,
            artist=",".join(track.artists),
            added_by=user.id,
            raw=track._raw,
        )
        self._session.add(db_track)

        if user:
            user.last_action = datetime.now(timezone.utc)

        return db_track

    async def get_all_track_ids(self) -> Set[int]:
        result = await self._session.execute(select(TrackDB.id))
        return {r[0] for r in result.all()}

    async def get_track(self, track_id: int) -> Optional[User]:
        return await self._session.get(TrackDB, track_id)


# ------------------------
# Init DB
# ------------------------
async def init_db(engine=engine, session=None) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with DBService(session_factory=session) as db:
        if not await db.get_user_by_name("System"):
            await db.add_user(name="System", role="admin")
            _logger.info("initialized System user")
