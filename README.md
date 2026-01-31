# TelyDL - HiRes Telegram Music Downloader Bot

TelyDL is a Telegram bot that allows whitelisted users to download music from Tidal and Spotify ( through [monochrome](https://github.com/SamidyFR/monochrome) and YouTube ( as fallback: MP3 ) directly to the server running it.

The bot handles audio extraction, metadata management, and provides a convenient interface for managing downloaded files.

## Usage

Send one or multiple links to the bot and it will download it to your server.

1. Validate the URL
2. Download the audio with embedded metadata
4. Save the file in the appropriate directory
5. Notify you when complete


## Features

- **Multi-platform support**: supported links: Tidal / Spotify / Youtube
- **Simple Whitelist Auth**: authentication is required for every action, unauthorized access is denied and reported to the admin user.
- **Multiple download sources**: HiRes Download through monochrome API / LowRes through `yt-dlp`
- **no API token required**: uses monochrome as source
- **Metadata handling**: Automatic metadata embedding
- **Disk space management**: Monitors disk space and prevents downloads when storage is low
- **URL validation**: Filters URLs based on duration and other criteria ( omits tracks longer than 10min, not configurable yet )
- **Libraray syncing**: sync the libraray to another server with rsync
- **Flat download directory**: download all files into one directory


## potential features

- **soundcloud support**
- **video downloads from multimedia**: download mp4s from all sources accepted by `yt-dlp` ( thats a lot )
- **torrent integration**: provide magnet links ( browse )
- **configurable download structure**: `base/$ARTIST/$ALBUM/`, `base/$ARTIST`, etc.
- **metadata configuration**: `base/$ARTIST/$ALBUM/`, `base/$ARTIST`, etc.

have one? suggest as Issue or submit PR

## Installation

### dependencies

- Python 3.8+
- `uv` or other package manager
- `yt-dlp` for YouTube downloads
- `ffmpeg` optional for audio extraction when the falback yt-dlp handler is used
- `mutagen` for metadata tagging
- Telegram bot token ( easily acquirable through telegram )

### Setup

1. Clone the repository:

```bash
git clone https://github.com/nlsg/telydl.git
cd telydl
```

2. acquire token from botfather

`TELYDL_BOT_TOKEN`: Telegram bot token

3. Run the bot:

```bash
uv run main.py
```

4. install the bot as systemd service ( optional )

[](./scripts/service/install.sh) - user
[](./scripts/service/install_system.sh) - as root service


## Configuration


### minimal config

```env
TELYDL_BOT_TOKEN=your_telegram_bot_token
TELYDL_WHITELIST=12345,67890  # Comma-separated list of authorized user IDs
# To find out the ID, simple make a request and review the logs for unquthorized access
```

### Environment Variables

- `TELYDL_BOT_TOKEN`: Telegram bot token
- `TELYDL_BASE_DIRECTORY`: Directory where downloads will be stored
- `TELYDL_WHITELIST`: Comma-separated list of authorized user IDs
- `TELYDL_ADMIN`: where unauthorized access is reported ( falls back to first whitelisted user if unset )
- `TELYDL_RSYNC`: Rsync command for backup/sync operations
- `TELYDL_MIN_DURATION`: minimum track length ( default 2min )
- `TELYDL_MAX_DURATION`: maximum track_length ( default 10min )
- `TELYDL_MIN_FREE_DISK_SPACE`: downloads are omited, if less disk space is available ( default 10Gb )
- `TELYDL_CHECK_DISK_FREQUENCY`: check disk space every x download ( default 10 )
 

### Bot Commands

- NO COMMAND - parse for urls and download
- `/help` - Show help information
- `/list` - List all downloaded files, might break once the lib is to large ( #TODO )
- `/get <pattern>` - Download a specific file to your telegram client
- `/remove <pattern>` - Remove a file from storage
- `/get_log` - Get application logs
- `/rsync` - Run sync command


## Development

### Running Tests

```bash
python -m pytest tests/
```

## Contributing

Im happy to see your pull request and will likely approve it :)

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the GPLv3 License.

## Credits

Big Thanks to the [monochrome project](https://github.com/SamidyFR/monochrome), the project would not be able to provide high res downloads without it

Suggestions for mirrored APIs are always welcome - just issue or make a PR

Also thanks to `youtube-dl` / `yt-dlp`, very awesome tool I love and use for years.

## Related Projects / Links / Inspirations

- [Tidal UI](https://github.com/uimaxbai/tidal-ui)
- [HiFi API](https://github.com/uimaxbai/hifi-api)
- [TIDAL](https://github.com/hmelder/TIDAL)
- [Reddit thread](https://www.reddit.com/r/musichoarder/comments/1pa0ik2/what_is_qqdl/)
- [https://monochrome.samidy.com/docs](https://monochrome.samidy.com/docs)
- [https://music.binimum.org/](https://music.binimum.org/)
- [https://monochrome-api.samidy.com/docs](https://monochrome-api.samidy.com/docs)