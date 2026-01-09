import io
from typing import Any, Dict, Optional, TYPE_CHECKING
from aiohttp import ClientSession, ClientTimeout

from mutagen.flac import FLAC, Picture
from mutagen.mp4 import MP4, MP4Cover

if TYPE_CHECKING:
    from telydl.downloaders.tidal.api import LosslessAPI


async def get_cover_blob(api: "LosslessAPI", cover_id: str) -> Optional[bytes]:
    """
    Fetch album artwork blob.

    Args:
        api: API instance for cover URL
        cover_id: Cover identifier

    Returns:
        Cover image bytes or None
    """
    if not cover_id:
        return None

    url = api.getCoverUrl(cover_id, "1280")

    try:
        timeout = ClientTimeout(total=10)
        async with ClientSession(timeout=timeout) as session:
            async with session.get(url) as response:
                if response.ok:
                    return await response.read()
    except Exception as e:
        print(f"Failed to fetch cover: {e}")

    return None


def assume_extension_from_quality(quality: str) -> str:
    """
    Get file extension based on quality.

    Args:
        quality: Audio quality

    Returns:
        File extension ('flac' or 'm4a')
    """
    if quality in ("LOW", "HIGH"):
        return "m4a"
    return "flac"


async def add_metadata_to_audio(
    audio_data: bytes,
    track: Dict[str, Any],
    quality: str,
    api: Optional["LosslessAPI"] = None,
) -> bytes:
    """
    Adds metadata tags to audio data (FLAC or M4A)

    Args:
        audio_data: Raw audio bytes
        track: Track metadata
        api: API instance for fetching album art
        quality: Audio quality

    Returns:
        Audio data with embedded metadata
    """
    extension = assume_extension_from_quality(quality)

    if extension == "flac":
        return await add_flac_metadata(audio_data, track, api)
    elif extension == "m4a":
        return await add_m4a_metadata(audio_data, track, api)

    # Unsupported format, return original
    return audio_data


async def add_flac_metadata(
    flac_data: bytes, track: Dict[str, Any], api: Optional["LosslessAPI"]
) -> bytes:
    """
    Adds Vorbis comment metadata to FLAC data
    """
    buffer = io.BytesIO(flac_data)
    buffer.seek(0)
    audio = FLAC(buffer)

    # Clear existing tags
    audio.clear()

    # Add standard tags
    if track.get("title"):
        audio["TITLE"] = track["title"]
    if track.get("artist", {}).get("name"):
        audio["ARTIST"] = track["artist"]["name"]
    if track.get("album", {}).get("title"):
        audio["ALBUM"] = track["album"]["title"]
    if track.get("album", {}).get("artist", {}).get("name"):
        audio["ALBUMARTIST"] = track["album"]["artist"]["name"]
    if track.get("trackNumber"):
        audio["TRACKNUMBER"] = str(track["trackNumber"])
    if track.get("album", {}).get("numberOfTracks"):
        audio["TRACKTOTAL"] = str(track["album"]["numberOfTracks"])

    release_date_str = track.get("album", {}).get("releaseDate") or (
        track.get("streamStartDate", "").split("T")[0]
        if track.get("streamStartDate")
        else ""
    )
    if release_date_str:
        try:
            year = str(int(release_date_str.split("-")[0]))
            audio["DATE"] = year
        except (ValueError, IndexError):
            pass

    if track.get("copyright"):
        audio["COPYRIGHT"] = track["copyright"]
    if track.get("isrc"):
        audio["ISRC"] = track["isrc"]

    # Add album artwork
    if track.get("album", {}).get("cover") and api:
        try:
            cover_data = await get_cover_blob(api, track["album"]["cover"])
            if cover_data:
                picture = Picture()
                picture.type = 3  # Front cover
                picture.mime = "image/jpeg"  # Default, could detect
                picture.desc = ""
                picture.data = cover_data
                audio.add_picture(picture)
        except Exception as e:
            print(f"Failed to embed album art: {e}")

    buffer.seek(0)
    audio.save(buffer)
    buffer.seek(0)
    return buffer.read()


async def add_m4a_metadata(
    data: bytes, track: Dict[str, Any], api: Optional["LosslessAPI"]
) -> bytes:
    """
    Adds metadata to M4A data using MP4 atoms
    """
    buffer = io.BytesIO(data)
    buffer.seek(0)
    audio = MP4(buffer)

    # Clear existing tags
    audio.clear()
    # Add standard tags
    tags = {}
    if track.get("title"):
        tags["\xa9nam"] = track["title"]
    if track.get("artist", {}).get("name"):
        tags["\xa9ART"] = track["artist"]["name"]
    if track.get("album", {}).get("title"):
        tags["\xa9alb"] = track["album"]["title"]
    if track.get("album", {}).get("artist", {}).get("name"):
        tags["aART"] = track["album"]["artist"]["name"]

    if track.get("trackNumber"):
        tags["trkn"] = [
            (track["trackNumber"], track.get("album", {}).get("numberOfTracks") or 0)
        ]

    release_date_str = track.get("album", {}).get("releaseDate") or (
        track.get("streamStartDate", "").split("T")[0]
        if track.get("streamStartDate")
        else ""
    )
    if release_date_str:
        try:
            year = str(int(release_date_str.split("-")[0]))
            tags["\xa9day"] = year
        except (ValueError, IndexError):
            pass

    audio.tags.update(tags)

    # Add album artwork
    if track.get("album", {}).get("cover") and api:
        try:
            cover_data = await get_cover_blob(api, track["album"]["cover"])
            if cover_data:
                # Detect format
                if cover_data.startswith(b"\xff\xd8"):
                    format_type = MP4Cover.FORMAT_JPEG
                elif cover_data.startswith(b"\x89PNG"):
                    format_type = MP4Cover.FORMAT_PNG
                else:
                    format_type = MP4Cover.FORMAT_JPEG
                audio.tags["covr"] = [MP4Cover(cover_data, format_type)]
        except Exception as e:
            print(f"Failed to embed album art in M4A: {e}")

    buffer.seek(0)
    audio.save(buffer)
    buffer.seek(0)
    return buffer.read()
