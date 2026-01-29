import time
import sys
from pathlib import Path
from mutagen.flac import FLAC


from telydl.util import setup_logging, logging


setup_logging(__file__.replace(".py", "") + ".log")
logger = logging.getLogger(__name__)


def iterate_library(root_dir: str | Path):
    count = 0
    start_time = time.perf_counter()
    for path in Path(root_dir).glob("*.flac"):
        if not path.is_file():
            continue
        try:
            audio = FLAC(path)
        except Exception as e:
            logger.error(f"{path} failed to load tags: {e}")
            continue
        changed = False

        if not audio.tags:
            logger.warning(f"no tags found for file: {path}")
            continue

        if (artist := audio["ARTIST"][0]) and "," in artist and ", " not in artist:
            artist: str
            new_artist = artist.replace(",", ", ").replace("  ", " ")
            logger.info(
                f"{path.name}: artist name contains comma without space: {artist} -> {new_artist}"
            )

            audio["ARTIST"] = new_artist
            changed = True
        if title := audio["TITLE"][0]:
            title: str
            if "(None)" in title and "(Original Mix)" not in title:
                new_title = title.replace("(None)", "(Original Mix)")

                logger.info(
                    f"{path.name}: contains None instead of Mix: {title} -> {new_title}"
                )
                audio["TITLE"] = new_title
                changed = True
            elif "(None)" in title and "(Original Mix)" in title:
                new_title = title.replace("(None)", "")
                logger.info(
                    f"{path.name}: contains None and Mix: {title} -> {new_title}"
                )
                audio["TITLE"] = new_title
                changed = True
        if changed:
            audio.save()
            count += 1
    logger.info(
        f"updated {count} files in {time.perf_counter() - start_time:.3f} seconds"
    )


if __name__ == "__main__":
    # print_flac_tags("/srv/media/music/tracks")
    if len(sys.argv) == 2:
        path = sys.argv[1]
        iterate_library(path)
    else:
        print(f"usage: {__file__} <path>")
