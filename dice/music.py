"""
Music player for the bot.
"""
import asyncio
import datetime
import discord
import youtube_dl

import dice.exc

MPLAYER_TIMEOUT = 120  # seconds
# Stupid youtube: https://github.com/Rapptz/discord.py/issues/315
BEFORE_OPTS = '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'


class MPlayerState:
    """ MPlayer state enum. """
    STOPPED = 0
    PLAYING = 1
    PAUSED = 2
    TEXT = {
        STOPPED: 'Stopped',
        PLAYING: 'Playing',
        PAUSED: 'Paused',
    }


class MPlayer(object):
    """
    Music player interface.
    """
    def __init__(self, bot, *, d_voice=None, d_player=None):
        self.vids = []
        self.vid_index = 0
        self.volume = 50
        self.loop = True
        self.state = MPlayerState.STOPPED

        # Wrapped by this class, not for outside use.
        self.bot = bot
        self.target_voice_channel = None
        self.err_channel = None
        self.d_voice = d_voice
        self.d_player = d_player

    def __str__(self):
        str_vids = []
        for vid in self.vids:
            if dice.util.is_valid_url(vid):
                str_vids += ['<' + vid + '>']
            else:
                str_vids += [vid]

        return """__**Player Status**__ :

        Queue: {vids}
        Index: {vid_index}
        Volume: {volume}/100
        Loop: {loop}
        Status: {state}
""".format(vids=str_vids, vid_index=self.vid_index, volume=self.volume,
           loop=self.loop, state=self.status)

    def __repr__(self):
        return "MPlayer(bot={}, target_voice_channel={}, err_channel={}, d_voice={}, d_player={},"\
            " vids={}, vid_index={}, loop={}, volume={}, state={})".format(
                self.bot, self.target_voice_channel, self.err_channel, self.d_voice, self.d_player,
                self.vids, self.vid_index, self.loop, self.volume, self.state
            )

    @property
    def status(self):
        """ Textual version of state. """
        return MPlayerState.TEXT[self.state]

    def initialize_settings(self, msg, vids):
        """
        Update current set videos and recorded channels.
        """
        self.target_voice_channel = msg.author.voice.voice_channel
        self.err_channel = msg.channel
        if not self.target_voice_channel:
            self.target_voice_channel = discord.utils.get(msg.server.channels,
                                                          type=discord.ChannelType.voice)

        self.vids = vids

    async def join_voice_channel(self):
        """
        Join the right channel before beginning transmission.
        """
        if self.d_voice:
            if self.target_voice_channel != self.d_voice.channel:
                await self.d_voice.move_to(self.target_voice_channel)
        else:
            self.d_voice = await self.bot.join_voice_channel(self.target_voice_channel)

    def set_volume(self, new_volume=None):
        """
        Set the volume for the bot.
        """
        if new_volume is None:
            new_volume = self.volume

        try:
            new_volume = int(new_volume)
            if new_volume < 0 or new_volume > 100:
                raise ValueError
        except ValueError:
            raise dice.exc.InvalidCommandArgs("Volume must be between [0, 100]")

        self.volume = new_volume
        if self.d_player:
            self.d_player.volume = new_volume / 100

    async def start(self):
        """
        Start the song currently selected.

        Raises:
            InvalidCommandArgs - No videos to play.
        """
        if not self.vids:
            raise dice.exc.InvalidCommandArgs("No videos to play!")

        self.stop()
        await self.join_voice_channel()

        vid = self.vids[self.vid_index]
        try:
            if "youtu" in vid:
                self.d_player = await self.d_voice.create_ytdl_player(
                    vid, before_options=BEFORE_OPTS)
            else:
                self.d_player = self.d_voice.create_ffmpeg_player(vid)
            self.d_player.start()
            self.set_volume()
            self.state = MPlayerState.PLAYING
        except youtube_dl.utils.DownloadError as exc:
            if self.err_channel:
                msg = "Player stopped. Error donwloading video: copyright?\n" + dice.tbl.wrap_markdown(str(exc))
                self.stop()
                await self.bot.send_message(self.err_channel, msg)
        except youtube_dl.utils.YoutubeDLError as exc:
            if self.err_channel:
                msg = "Player stopped. General YoutubeDL error.\n" + dice.tbl.wrap_markdown(str(exc))
                self.stop()
                await self.bot.send_message(self.err_channel, msg)

    def pause(self):
        """
        Toggle player pause function.
        """
        if self.state == MPlayerState.PLAYING:
            self.d_player.pause()
            self.state = MPlayerState.PAUSED
        elif self.state == MPlayerState.PAUSED:
            self.d_player.resume()
            self.state = MPlayerState.PLAYING

    def stop(self):
        """
        Stop playing the stream.
        """
        try:
            self.state = MPlayerState.STOPPED
            self.d_player.stop()
        except AttributeError:
            pass

    async def quit(self):
        """
        Ensure player stopped and quit the voice channel.
        """
        try:
            self.stop()
            await self.d_voice.disconnect()
            self.d_player = None
            self.d_voice = None
        except AttributeError:
            pass

    async def prev(self):
        """
        Go to the previous song.
        """
        if self.d_player and self.vids:
            if self.loop or self.vid_index - 1 >= 0:
                self.vid_index = (self.vid_index - 1) % len(self.vids)
                await self.start()
            else:
                self.vid_index = 0
                self.stop()
                raise dice.exc.InvalidCommandArgs("Loop is not set, queue finished. Stopping.")

    async def next(self):
        """
        Go to the next song.
        """
        if self.d_player and self.vids:
            if self.loop or self.vid_index + 1 < len(self.vids):
                self.vid_index = (self.vid_index + 1) % len(self.vids)
                await self.start()
            else:
                self.vid_index = 0
                self.stop()
                raise dice.exc.InvalidCommandArgs("Loop is not set, queue finished. Stopping.")

    async def monitor(self, sleep_time=5):
        """
        Simple monitor task that lives as long as the bot runs.
        """
        last_activity = datetime.datetime.utcnow()

        while True:
            if self.d_player:
                if self.state == MPlayerState.PLAYING:
                    last_activity = datetime.datetime.utcnow()

                if self.state == MPlayerState.PLAYING and self.d_player.is_done():
                    await self.next()

                if (datetime.datetime.utcnow() - last_activity).seconds > MPLAYER_TIMEOUT:
                    await self.quit()

            await asyncio.sleep(sleep_time)
