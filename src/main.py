import asyncio
import sys
import os
import aiofiles
import discord
import youtube_dl
import json
import random



youtube_dl.utils.bug_reports_message = lambda: ''


ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0' # bind to ipv4 since ipv6 addresses cause issues sometimes
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

ffmpeg_options = {
    'options': '-vn'
}



class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)

        self.data = data

        self.title = data.get("titel")
        self.url = data.get("url")

    @classmethod
    async def from_url(cls, url, loop):
        def extract_info():
            try:
                return ytdl.extract_info(url, download=False)
            except Exception as e:
                print("Could not load URL info")
                print(e)
                return None

        try:
            data = await asyncio.wait_for(loop.run_in_executor(None, extract_info), timeout=3.0)
        except asyncio.TimeoutError:
            print("Loading URL info timed out")
            return None

        if data == None:
            print("Could not load URL info for unknown reason")
            return None
        if "url" not in data:
            print("URL is not a playable audio source")
            return None

        filename = data["url"]
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)




client = discord.Client()

@client.event
async def on_ready():
    print("Logged in as {}#{}-{}".format(client.user.name, client.user.discriminator, client.user.id))

playlists = None

def load_playlists():
    global playlists

    try:
        with open('data/playlists.json', 'r') as f:
            data = f.read()
        playlists = json.loads(data)
    except FileNotFoundError:
        # Ignore FileNotFoundError and initialize data as empty. Files will be created on write.
        playlists = {}
load_playlists()

async def write_playlists():
    async with aiofiles.open('data/playlists.json', mode='w+') as f:
        await f.write(json.dumps(playlists))



class VoiceConnection:
    def __init__(self, voice_client):
        self.voice_client = voice_client

        self.playlist = None
        self.queue = []
        self.next_song_event = asyncio.Event()

        self.player = None
        self.player_url = None

        self.playing = False
        self.connected = True

    async def play_next(self):
        if len(self.queue) > 0:
            url = self.queue.pop(0)
        else:
            url = random.choice(playlists[self.playlist])

        player = await YTDLSource.from_url(url, client.loop)
        self.player = player
        self.player_url = url

        def done(error):
            # The flag is cleared again after it is detected by #enqueue()
            self.next_song_event.set()

        if player == None:
            print("Unable to play from {}".format(self.player_url))
            done(None)
        else:
            self.voice_client.play(player, after=done)

    async def play_loop(self):
        self.playing = True
        while self.connected and (len(self.queue) > 0 or self.playlist != None):
            await self.play_next()
            await self.next_song_event.wait()
            self.next_song_event.clear()
        self.playing = False

    async def enqueue(self, url):
        if url in playlists:
            self.playlist = url
        else:
            self.queue.append(url)

        if not self.playing:
            asyncio.ensure_future(self.play_loop())


    async def skip(self):
        self.voice_client.stop()
    async def stop(self):
        self.playlist = None
        self.queue = []
        await self.skip()


    async def disconnect(self):
        self.connected = False
        self.next_song_event.set()

voice_connections = {}

@client.event
async def on_message(message):
    if not message.content.startswith("!"):
        return

    print("Received potential command: {}", message.content)

    content = message.content[1:]
    content_split = content.split(" ", 1)
    
    command = content_split[0]
    if len(content_split) == 1:
        argument = ""
    else:
        argument = content_split[1]



    if command == "connect":
        if message.author.voice == None or message.author.voice.channel == None: 
            await message.channel.send("You are not connected to a voice channel.")
        else:
            voice_client = await message.author.voice.channel.connect()
            voice_connections[message.guild.id] = VoiceConnection(voice_client)

            await message.channel.send("Connected to voice channel {}.".format(message.author.voice.channel.name))

    elif command == "leave":
        voice_connection = voice_connections.get(message.guild.id)

        if voice_connection == None:
            await message.channel.send("The bot is not connected to a voice channel.")
        else:
            await voice_connection.disconnect()
            del voice_connections[message.guild.id]

            await voice_connection.voice_client.disconnect()
            await message.channel.send("Disconnected from voice channel.")

    elif command == "play":
        if argument == "":
            await message.channel.send("You have to provide an URL to be played.")
        else:
            voice_connection = voice_connections.get(message.guild.id)

            if voice_connection == None:
                await message.channel.send("The bot is not connected to a voice channel.")
            else:
                await voice_connection.enqueue(argument)
                await message.channel.send("Song enqueued.")
    elif command == "playing":
        voice_connection = voice_connections.get(message.guild.id)

        if voice_connection == None:
            await message.channel.send("The bot is not connected to a voice channel.")
        elif not voice_connection.playing:
            await message.channel.send("The bot is not playing anything.")
        else:
            string = ""

            string += "Currently playing {} .\n".format(voice_connection.player_url)

            if len(voice_connection.queue) == 0:
                string += "The queue is empty.\n"
                if voice_connection.playlist != None:
                    string += "Playing from playlist {}".format(voice_connection.playlist)
            else:
                string += "The queue contains {} song(s):\n".format(len(voice_connection.queue))
                string += "\n".join(voice_connection.queue[:10])
                string += "\n"
                if len(voice_connection.queue) > 10:
                    string += "...\n"
                if voice_connection.playlist != None:
                    string += "Playing from playlist {} afterwards".format(voice_connection.playlist)


            await message.channel.send(string)
    elif command == "skip":
        voice_connection = voice_connections.get(message.guild.id)

        if voice_connection == None:
            await message.channel.send("The bot is not connected to a voice channel.")
        elif not voice_connection.playing:
            await message.channel.send("The bot is not playing anything.")
        else:
            await voice_connection.skip()
            await message.channel.send("Skipping current song")
    elif command == "stop":
        voice_connection = voice_connections.get(message.guild.id)

        if voice_connection == None:
            await message.channel.send("The bot is not connected to a voice channel.")
        elif not voice_connection.playing:
            await message.channel.send("The bot is not playing anything.")
        else:
            await voice_connection.stop()
            await message.channel.send("Stopping playback and clearing queue.")
    elif command == "playlist" or command == "playlists":
        if argument == "":
            s = "There are the following playlists:\n"
            s += "\n".join(playlists.keys())

            await message.channel.send(s)
        elif argument not in playlists:
            await message.channel.send("Cannot find playlist {}".format(argument))
        else:
            s = "The playlist {} contains the following songs:\n".format(argument)
            s += "\n".join(playlists[argument])
            await message.channel.send(s)
    elif command == "playlist_add":
        split = argument.split(" ")

        if len(split) != 2:
            await message.channel.send("Usage: !playlist_add PLAYLIST SONG")
        else:
            playlist = split[0]
            song = split[1]

            if playlist not in playlists:
                playlists[playlist] = [song]
                await message.channel.send("Created new playlist {} and added song".format(playlist))
            else:
                if song in playlists[playlist]:
                    await message.channel.send("Playlist {} already contains that song".format(playlist))
                else:
                    playlists[playlist].append(song)
                    await message.channel.send("Song added to playlist {}".format(playlist))
            await write_playlists()
    elif command == "playlist_remove":
        split = argument.split(" ")

        if len(split) != 2:
            await message.channel.send("Usage: !playlist_remove PLAYLIST SONG")
        else:
            playlist = split[0]
            song = split[1]

            if playlist not in playlists:
                await message.channel.send("Cannot find playlist {}".format(playlist))
            else:
                if song in playlists[playlist]:
                    playlists[playlist].remove(song)
                    await message.channel.send("Song removed from playlist {}".format(playlist))
                else:
                    await message.channel.send("Cannot find that song in playlist {}".format(playlist))
            await write_playlists()
    elif command == "playlist_delete":
        if argument == "":
            await message.channel.send("Usage: !playlist_delete PLAYLIST")
        else:
            playlist = argument
            if playlist not in playlists:
                await message.channel.send("Cannot find playlist {}".format(playlist))
            else:
                del playlists[playlist]
                await message.channel.send("Deleted playlist {}".format(playlist))
            await write_playlists()





if "DISCORD_TOKEN" not in os.environ:
    print("No discord token environment variable. Exiting")
    sys.exit()
else:
    # client.run('NTQwNTM2NTEzOTk0MjkzMjU5.DzSV4w.MbEcS3YvA-FXrX-Du6sBq3a9jRE')
    client.run(os.environ["DISCORD_TOKEN"])
