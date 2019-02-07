# Ditch

Ditch is a small single-purpose bot I originally wrote to attempt to stream audio from Twitch into a
Discord channel. It then expanded to be a simple, generic audio-playing bot with playlists.

## Setup

1. Clone the repository and install docker as well as docker-compose
1. Copy `ditch.env.example` to `ditch.env` and insert your bot token
1. Run `docker-compose up` or `docker-compose up -d`

After completing the setup you can edit the Python files and restart the bot to apply changes.

## Usage

- `!play URL`: Enqueue a link
- `!play PLAYLIST`: Enqueue a playlist
- `!playing`: Print information about currently playing song and queue
- `!playlists`: List playlists
- `!playlist PLAYLIST`: List songs in specific playlist
- `!playlist_add PLAYLIST SONG`: Add song to playlist
- `!playlist_remove PLAYLIST SONG`: Remove song from playlist
- `!playlist_DELETE PLAYLIST`: Delete playlist
