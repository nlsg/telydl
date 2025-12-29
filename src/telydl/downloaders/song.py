from dataclasses import dataclass


@dataclass
class Song:
    filename: str
    name: str
    artist: str
    duration: int | None
