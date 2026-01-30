import asyncio
import base64
import json
import logging
from typing import Any, Dict, List, Optional, Callable
from aiohttp import ClientSession, ClientTimeout

from telydl.util import locate_section, retry_on_exception

_logger = logging.getLogger(__name__)


# Assuming equivalents from utils.py
class RateLimitHit(Exception):
    pass


RATE_LIMIT_ERROR_MESSAGE = "Rate limit exceeded"


def deriveTrackQuality(track: Dict[str, Any]) -> Optional[str]:
    # Placeholder implementation
    return track.get("audioQuality")


DASH_MANIFEST_UNAVAILABLE_CODE = "DASH_MANIFEST_UNAVAILABLE"


class Settings:
    async def getInstances(self, type: str) -> list[str]:
        return {
            "api": ["https://monochrome-api.samidy.com"],
            "streaming": [
                "https://tidal.kinoplus.online",
                "https://tidal-api.binimum.org",
                "https://triton.squid.wtf",
                "https://wolf.qqdl.site",
                "https://katze.qqdl.site",
                "https://hund.qqdl.site",
                "https://vogel.qqdl.site",
                "https://maus.qqdl.site",
            ],
        }.get(type)


class LosslessAPI:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings()

    @retry_on_exception(RateLimitHit)
    async def fetchWithRetry(
        self, relativePath: str, options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        options = options or {}
        type_ = options.get("type", "api")
        instances = await self.settings.getInstances(type_)
        if not instances:
            raise ValueError(f"No API instances configured for type: {type_}")

        maxRetries = 3
        lastError: Optional[Exception] = None

        timeout = ClientTimeout(total=30)
        async with ClientSession(timeout=timeout) as session:
            for baseUrl in instances:
                url = (
                    f"{baseUrl.rstrip('/')}/{relativePath.lstrip('/')}"
                    if baseUrl.endswith("/")
                    else f"{baseUrl}{relativePath}"
                )

                for attempt in range(1, maxRetries + 1):
                    try:
                        async with session.get(url) as response:
                            if response.status == 429:
                                raise RateLimitHit(RATE_LIMIT_ERROR_MESSAGE)

                            if response.ok:
                                return await response.json()

                            if response.status == 401:
                                try:
                                    errorData = await response.json()
                                except Exception:
                                    errorData = None

                                if errorData and errorData.get("subStatus") == 11002:
                                    lastError = ValueError(
                                        errorData.get(
                                            "userMessage", "Authentication failed"
                                        )
                                    )
                                    if attempt < maxRetries:
                                        await asyncio.sleep(0.2 * attempt)
                                        continue

                            if response.status >= 500 and attempt < maxRetries:
                                await asyncio.sleep(0.2 * attempt)
                                continue

                            lastError = ValueError(
                                f"Request failed with status {response.status}"
                            )
                            break

                    except Exception as error:
                        lastError = error
                        if attempt < maxRetries:
                            await asyncio.sleep(0.2 * attempt)

        raise lastError or ValueError(f"All API instances failed for: {relativePath}")

    def normalizeSearchResponse(self, data: Dict[str, Any], key: str) -> Dict[str, Any]:
        section = locate_section(data, key)
        items = section.get("items", []) if section else []
        return {
            "items": items,
            "limit": section.get("limit", len(items)) if section else len(items),
            "offset": section.get("offset", 0) if section else 0,
            "totalNumberOfItems": section.get("totalNumberOfItems", len(items))
            if section
            else len(items),
        }

    def prepareTrack(self, track: Dict[str, Any]) -> Dict[str, Any]:
        normalized = track.copy()

        if (
            not track.get("artist")
            and isinstance(track.get("artists"), list)
            and track["artists"]
        ):
            normalized["artist"] = track["artists"][0]

        derivedQuality = deriveTrackQuality(normalized)
        if derivedQuality and normalized.get("audioQuality") != derivedQuality:
            normalized["audioQuality"] = derivedQuality

        return normalized

    def prepareAlbum(self, album: Dict[str, Any]) -> Dict[str, Any]:
        if (
            not album.get("artist")
            and isinstance(album.get("artists"), list)
            and album["artists"]
        ):
            return {**album, "artist": album["artists"][0]}
        return album

    def preparePlaylist(self, playlist: Dict[str, Any]) -> Dict[str, Any]:
        return playlist

    def prepareArtist(self, artist: Dict[str, Any]) -> Dict[str, Any]:
        if (
            not artist.get("type")
            and isinstance(artist.get("artistTypes"), list)
            and artist["artistTypes"]
        ):
            return {**artist, "type": artist["artistTypes"][0]}
        return artist

    def parseTrackLookup(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        entries = data if isinstance(data, list) else [data]
        track = None
        info = None
        originalTrackUrl = None

        for entry in entries:
            if not entry or not isinstance(entry, dict):
                continue

            if not track and "duration" in entry:
                track = entry
                continue

            if not info and "manifest" in entry:
                info = entry
                continue

            if not originalTrackUrl and "OriginalTrackUrl" in entry:
                candidate = entry["OriginalTrackUrl"]
                if isinstance(candidate, str):
                    originalTrackUrl = candidate

        if not track or not info:
            raise ValueError("Malformed track response")

        return {"track": track, "info": info, "originalTrackUrl": originalTrackUrl}

    def extractStreamUrlFromManifest(self, manifest: str) -> Optional[str]:
        try:
            decoded = base64.b64decode(manifest).decode("utf-8")

            try:
                parsed = json.loads(decoded)
                if parsed.get("urls") and parsed["urls"]:
                    return parsed["urls"][0]
            except Exception:
                import re

                match = re.search(r"https?://[\w\-.~:?#[@!$&\'()*+,;=%/]+", decoded)
                return match.group(0) if match else None
        except Exception as error:
            print(f"Failed to decode manifest: {error}")
        return None

    def deduplicateAlbums(self, albums: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        unique = {}

        for album in albums:
            key = f"{album.get('title')}{album.get('numberOfTracks', 0)}"

            if key in unique:
                existing = unique[key]

                if album.get("explicit") and not existing.get("explicit"):
                    unique[key] = album
                    continue
                if not album.get("explicit") and existing.get("explicit"):
                    continue

                existingTags = len(existing.get("mediaMetadata", {}).get("tags", []))
                newTags = len(album.get("mediaMetadata", {}).get("tags", []))

                if newTags > existingTags:
                    unique[key] = album
            else:
                unique[key] = album

        return list(unique.values())

    async def searchTracks(
        self, query: str, options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        if options is None:
            options = {}
        try:
            response = await self.fetchWithRetry(f"/search/?s={query}", options)
            normalized = self.normalizeSearchResponse(response, "tracks")
            return {
                **normalized,
                "items": [self.prepareTrack(t) for t in normalized["items"]],
            }
        except Exception as error:
            print(f"Track search failed: {error}")
            return {"items": [], "limit": 0, "offset": 0, "totalNumberOfItems": 0}

    async def searchArtists(
        self, query: str, options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        if options is None:
            options = {}
        try:
            response = await self.fetchWithRetry(f"/search/?a={query}", options)
            normalized = self.normalizeSearchResponse(response, "artists")
            return {
                **normalized,
                "items": [self.prepareArtist(a) for a in normalized["items"]],
            }
        except Exception as error:
            print(f"Artist search failed: {error}")
            return {"items": [], "limit": 0, "offset": 0, "totalNumberOfItems": 0}

    async def searchAlbums(
        self, query: str, options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        if options is None:
            options = {}
        try:
            response = await self.fetchWithRetry(f"/search/?al={query}", options)
            normalized = self.normalizeSearchResponse(response, "albums")
            preparedItems = [self.prepareAlbum(a) for a in normalized["items"]]
            return {**normalized, "items": self.deduplicateAlbums(preparedItems)}
        except Exception as error:
            print(f"Album search failed: {error}")
            return {"items": [], "limit": 0, "offset": 0, "totalNumberOfItems": 0}

    async def searchPlaylists(
        self, query: str, options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        if options is None:
            options = {}
        try:
            response = await self.fetchWithRetry(f"/search/?p={query}", options)
            normalized = self.normalizeSearchResponse(response, "playlists")
            return {
                **normalized,
                "items": [self.preparePlaylist(p) for p in normalized["items"]],
            }
        except Exception as error:
            print(f"Playlist search failed: {error}")
            return {"items": [], "limit": 0, "offset": 0, "totalNumberOfItems": 0}

    async def getAlbum(self, id: str) -> Dict[str, Any]:
        response = await self.fetchWithRetry(f"/album/?id={id}")
        jsonData = response

        data = jsonData.get("data", jsonData)

        album = None
        tracksSection = None

        if data and isinstance(data, dict) and not isinstance(data, list):
            if "numberOfTracks" in data or "title" in data:
                album = self.prepareAlbum(data)

            if "items" in data:
                tracksSection = data

                if not album and data["items"] and data["items"]:
                    firstItem = data["items"][0]
                    track = firstItem.get("item", firstItem)

                    if track and track.get("album"):
                        album = self.prepareAlbum(track["album"])

        if not album:
            raise ValueError("Album not found")

        if (
            album
            and not album.get("artist")
            and tracksSection
            and tracksSection.get("items")
        ):
            firstTrack = tracksSection["items"][0]
            track = firstTrack.get("item", firstTrack)
            if track and track.get("artist"):
                album["artist"] = track["artist"]

        if (
            album
            and not album.get("releaseDate")
            and tracksSection
            and tracksSection.get("items")
        ):
            firstTrack = tracksSection["items"][0]
            track = firstTrack.get("item", firstTrack)

            if track:
                if track.get("album") and track["album"].get("releaseDate"):
                    album["releaseDate"] = track["album"]["releaseDate"]
                elif track.get("streamStartDate"):
                    album["releaseDate"] = track["streamStartDate"].split("T")[0]

        tracks = (
            [
                self.prepareTrack(i.get("item", i))
                for i in tracksSection.get("items", [])
            ]
            if tracksSection
            else []
        )
        return {"album": album, "tracks": tracks}

    async def getPlaylist(self, id: str) -> Dict[str, Any]:
        response = await self.fetchWithRetry(f"/playlist/?id={id}")
        jsonData = response

        data = jsonData.get("data", jsonData)

        playlist = None
        tracksSection = None

        if data.get("playlist"):
            playlist = data["playlist"]

        if data.get("items"):
            tracksSection = {"items": data["items"]}

        if not playlist or not tracksSection:
            entries = data if isinstance(data, list) else [data]
            for entry in entries:
                if not entry or not isinstance(entry, dict):
                    continue

                if not playlist and (
                    "uuid" in entry
                    or "numberOfTracks" in entry
                    or ("title" in entry and "id" in entry)
                ):
                    playlist = entry

                if not tracksSection and "items" in entry:
                    tracksSection = entry

        if not playlist and isinstance(data, list):
            for entry in data:
                if (
                    entry
                    and isinstance(entry, dict)
                    and ("uuid" in entry or "numberOfTracks" in entry)
                ):
                    playlist = entry
                    break

        if not playlist:
            raise ValueError("Playlist not found")

        tracks = (
            [
                self.prepareTrack(i.get("item", i))
                for i in tracksSection.get("items", [])
            ]
            if tracksSection
            else []
        )

        if playlist.get("numberOfTracks", 0) > len(tracks):
            offset = len(tracks)
            SAFE_MAX_TRACKS = 10000

            while (
                len(tracks) < playlist["numberOfTracks"]
                and len(tracks) < SAFE_MAX_TRACKS
            ):
                try:
                    nextResponse = await self.fetchWithRetry(
                        f"/playlist/?id={id}&offset={offset}"
                    )
                    nextJson = nextResponse
                    nextData = nextJson.get("data", nextJson)

                    nextItems = []

                    if nextData.get("items"):
                        nextItems = nextData["items"]
                    elif isinstance(nextData, list):
                        for entry in nextData:
                            if (
                                entry
                                and isinstance(entry, dict)
                                and "items" in entry
                                and isinstance(entry["items"], list)
                            ):
                                nextItems = entry["items"]
                                break

                    if not nextItems:
                        break

                    preparedItems = [
                        self.prepareTrack(i.get("item", i)) for i in nextItems
                    ]
                    if not preparedItems:
                        break

                    if tracks and preparedItems[0]["id"] == tracks[0]["id"]:
                        break

                    tracks.extend(preparedItems)
                    offset += len(preparedItems)

                except Exception as error:
                    print(f"Error fetching playlist tracks at offset {offset}: {error}")
                    break

        return {"playlist": playlist, "tracks": tracks}

    async def getMix(self, id: str) -> Dict[str, Any]:
        response = await self.fetchWithRetry(f"/mix/?id={id}", {"type": "api"})
        data = response

        mixData = data.get("mix")
        items = data.get("items", [])

        if not mixData:
            raise ValueError("Mix metadata not found")

        tracks = [self.prepareTrack(i.get("item", i)) for i in items]

        mix = {
            "id": mixData["id"],
            "title": mixData["title"],
            "subTitle": mixData.get("subTitle"),
            "description": mixData.get("description"),
            "mixType": mixData.get("mixType"),
            "cover": mixData.get("images", {}).get("LARGE", {}).get("url")
            or mixData.get("images", {}).get("MEDIUM", {}).get("url")
            or mixData.get("images", {}).get("SMALL", {}).get("url"),
        }

        return {"mix": mix, "tracks": tracks}

    async def getArtist(self, artistId: str) -> Dict[str, Any]:
        primaryResponse, contentResponse = await asyncio.gather(
            self.fetchWithRetry(f"/artist/?id={artistId}"),
            self.fetchWithRetry(f"/artist/?f={artistId}&skip_tracks=true"),
        )

        primaryJsonData = primaryResponse
        primaryData = primaryJsonData.get("data", primaryJsonData)
        rawArtist = primaryData.get(
            "artist", primaryData[0] if isinstance(primaryData, list) else primaryData
        )

        if not rawArtist:
            raise ValueError("Primary artist details not found.")

        artist = {
            **self.prepareArtist(rawArtist),
            "picture": rawArtist.get("picture") or primaryData.get("cover"),
            "name": rawArtist.get("name", "Unknown Artist"),
        }

        contentJsonData = contentResponse
        contentData = contentJsonData.get("data", contentJsonData)
        entries = contentData if isinstance(contentData, list) else [contentData]

        albumMap = {}
        trackMap = {}

        def isTrack(v):
            return v and "id" in v and "duration" in v and "album" in v

        def isAlbum(v):
            return v and "id" in v and "numberOfTracks" in v

        def scan(value, visited=None):
            if visited is None:
                visited = set()
            if (
                not value
                or not isinstance(value, (dict, list))
                or str(value) in visited
            ):
                return
            visited.add(str(value))

            if isinstance(value, list):
                for item in value:
                    scan(item, visited)
                return

            item = value.get("item", value)
            if isAlbum(item):
                albumMap[item["id"]] = self.prepareAlbum(item)
            if isTrack(item):
                trackMap[item["id"]] = self.prepareTrack(item)

            for nested in value.values():
                scan(nested, visited)

        for entry in entries:
            scan(entry)

        try:
            searchResults = await self.searchAlbums(artist["name"])
            if searchResults and searchResults["items"]:
                numericArtistId = int(artistId)

                for item in searchResults["items"]:
                    itemArtistId = item.get("artist", {}).get("id")
                    matchesArtist = itemArtistId == numericArtistId or (
                        isinstance(item.get("artists"), list)
                        and any(a["id"] == numericArtistId for a in item["artists"])
                    )

                    if matchesArtist and item["id"] not in albumMap:
                        albumMap[item["id"]] = item
        except Exception as e:
            print(f"Failed to fetch additional albums via search: {e}")

        rawReleases = list(albumMap.values())
        allReleases = self.deduplicateAlbums(rawReleases)
        allReleases.sort(key=lambda a: a.get("releaseDate", ""), reverse=True)

        eps = [a for a in allReleases if a.get("type") in ("EP", "SINGLE")]
        albums = [a for a in allReleases if a not in eps]

        tracks = list(trackMap.values())
        tracks.sort(key=lambda t: t.get("popularity", 0), reverse=True)
        tracks = tracks[:15]

        return {**artist, "albums": albums, "eps": eps, "tracks": tracks}

    async def getSimilarArtists(self, artistId: str) -> List[Dict[str, Any]]:
        try:
            response = await self.fetchWithRetry(
                f"/artist/similar/?id={artistId}", {"type": "api"}
            )
            data = response

            items = (
                data.get("artists")
                or data.get("items")
                or data.get("data")
                or (data if isinstance(data, list) else [])
            )

            return [self.prepareArtist(artist) for artist in items]
        except Exception as e:
            print(f"Failed to fetch similar artists: {e}")
            return []

    async def getSimilarAlbums(self, albumId: str) -> List[Dict[str, Any]]:
        try:
            response = await self.fetchWithRetry(
                f"/album/similar/?id={albumId}", {"type": "api"}
            )
            data = response

            items = (
                data.get("items")
                or data.get("albums")
                or data.get("data")
                or (data if isinstance(data, list) else [])
            )

            return [self.prepareAlbum(album) for album in items]
        except Exception as e:
            print(f"Failed to fetch similar albums: {e}")
            return []

    async def getTrackInfo(self, trackId: str) -> Dict[str, Any]:
        response = await self.fetchWithRetry(f"/info/?id={trackId}", {"type": "api"})
        data = response.get("data", response)
        if album_id := data.get("album", {}).get("id"):
            try:
                album = await self.getAlbum(album_id)
                data["album"] = {**data["album"], **album.get("album", {})}
            except Exception:
                pass  # silent
        return data

    def normalizeTrackResponse(
        self, apiResponse: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        if not apiResponse or not isinstance(apiResponse, dict):
            return [apiResponse]

        raw = apiResponse.get("data", apiResponse)

        trackStub = {"duration": raw.get("duration", 0), "id": raw.get("trackId")}

        return [trackStub, raw]

    async def getTrackStreamInfo(
        self, id: str, quality: str = "LOSSLESS"
    ) -> Dict[str, Any]:
        response = await self.fetchWithRetry(
            f"/track/?id={id}&quality={quality}", {"type": "streaming"}
        )
        jsonResponse = response
        result = self.parseTrackLookup(self.normalizeTrackResponse(jsonResponse))

        return result

    async def getStreamUrl(self, id: str, quality: str = "LOSSLESS") -> str:
        lookup = await self.getTrackStreamInfo(id, quality)

        if lookup.get("originalTrackUrl"):
            return lookup["originalTrackUrl"]
        else:
            streamUrl = self.extractStreamUrlFromManifest(lookup["info"]["manifest"])
            if not streamUrl:
                raise ValueError("Could not resolve stream URL")
            return streamUrl

    async def downloadTrack(
        self,
        id: str,
        quality: str = "LOSSLESS",
        onProgress: Callable | None = None,
    ) -> bytes:
        try:
            lookup = await self.getTrackStreamInfo(id, quality)
            streamUrl = lookup.get(
                "originalTrackUrl"
            ) or self.extractStreamUrlFromManifest(lookup["info"]["manifest"])
            if not streamUrl:
                raise ValueError("Could not resolve stream URL")

            timeout = ClientTimeout(total=300)  # 5 min for download
            async with ClientSession(timeout=timeout) as session:
                async with session.get(streamUrl) as response:
                    if not response.ok:
                        raise ValueError(f"Fetch failed: {response.status}")

                    contentLength = response.headers.get("Content-Length")
                    totalBytes = int(contentLength) if contentLength else 0

                    receivedBytes = 0
                    data = b""

                    if onProgress:
                        async for chunk in response.content.iter_chunked(8192):
                            data += chunk
                            receivedBytes += len(chunk)
                            onProgress(
                                {
                                    "stage": "downloading",
                                    "receivedBytes": receivedBytes,
                                    "totalBytes": totalBytes or None,
                                }
                            )
                        return data
                    else:
                        return await response.read()

        except Exception as error:
            print(f"Download failed: {error}")
            if str(error) == RATE_LIMIT_ERROR_MESSAGE:
                raise
            raise ValueError("Download failed. The stream may require a proxy.")

    def getCoverUrl(self, id: Optional[str], size: str = "320") -> str:
        if not id:
            import random

            return f"https://picsum.photos/seed/{random.random()}/{size}"
        formattedId = id.replace("-", "/")
        return f"https://resources.tidal.com/images/{formattedId}/{size}x{size}.jpg"

    def getArtistPictureUrl(self, id: Optional[str], size: str = "320") -> str:
        if not id:
            import random

            return f"https://picsum.photos/seed/{random.random()}/{size}"
        formattedId = id.replace("-", "/")
        return f"https://resources.tidal.com/images/{formattedId}/{size}x{size}.jpg"
