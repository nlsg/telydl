from typing import Any, Literal
from dataclasses import dataclass


from telydl.util import sanitize_filename

type RawTrack = dict[str, Any]

type Quality = Literal["HI_RES_LOSSLESS", "LOSSLESS", "HIGH", "LOW"]


@dataclass
class Track:
    name: str
    artists: list[str]
    duration: int
    origin_url: str
    id: str

    _raw: RawTrack

    @property
    def filename(self) -> str:
        return sanitize_filename(f"{', '.join(self.artists)} - {self.name}")

    def __str__(self):
        return f"{self.filename} [{self.id}] ({self.duration / 60:.2f}min)"

    @classmethod
    def from_tidal(cls: type["Track"], raw_track: RawTrack):
        name = raw_track.get("title")
        if "mix)" not in name.lower():
            mix = raw_track.get("version") or "Original Mix"
            name = f"{name} ({mix})"
        try:
            artists = [a.get("name") for a in raw_track.get("artists", [])]
            assert all(artists)
        except (IndexError, ValueError, AssertionError):
            artists = [
                raw_track.get("artist", {}).get("name", "unknown"),
            ]
        return cls(
            name=name,
            artists=artists,
            duration=raw_track.get("duration", 0),
            origin_url=raw_track.get("url"),
            id=raw_track.get("id"),
            _raw=raw_track,
        )

    def get(self, key, default=None):
        return self._raw.get(key, default)
