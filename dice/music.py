"""
Music player for the bot.
"""
import asyncio
import datetime
import discord
import youtube_dl

import dice.exc

VOICE_JOIN_TIMEOUT = 5  # seconds
TIMEOUT_MSG = """ Bot joining voice took more than 5 seconds.

Try again later or get Gears. """
MPLAYER_TIMEOUT = 120  # seconds
# Stupid youtube: https://github.com/Rapptz/discord.py/issues/315
BEFORE_OPTS = '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'


#  Ideas for Bot Changes later:
#  - YTManager (Download & cache last n videos from youtube. Prove file name to and perhaps generate AudioStream on demand.
#  -  Store in DB either LocalVideo or YTVideo objects pickled, no more inspection/decision by regex.
#  - Add entry to all songs for loop or not loop, controllable by db. Saves whatever user chooses on play.
#  - Modify mplayer to be per server creation, no longer needs any reference to self.bot.


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
        self.target_voice_channel = None
        self.err_channel = None
        self.d_voice = d_voice

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
        return "MPlayer(target_voice_channel={}, err_channel={}, d_voice={}, d_player={},"\
            " vids={}, vid_index={}, loop={}, volume={}, state={})".format(
                self.target_voice_channel, self.err_channel, self.d_voice, self.d_player,
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

        Raises:
            InvalidCommandArgs - The bot could not join voice within a timeout. Discord network issue?
        """
        try:
            if self.d_voice:
                if self.target_voice_channel != self.d_voice.channel:
                    await asyncio.wait_for(self.d_voice.move_to(self.target_voice_channel),
                                           VOICE_JOIN_TIMEOUT)
            else:
                self.d_voice = await asyncio.wait_for(
                    self.target_voice_channel.connect(), VOICE_JOIN_TIMEOUT)
        except asyncio.TimeoutError:
            await self.quit()
            raise dice.exc.InvalidCommandArgs(TIMEOUT_MSG)

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
                await self.err_channel.send(msg)
        except youtube_dl.utils.YoutubeDLError as exc:
            if self.err_channel:
                msg = "Player stopped. General YoutubeDL error.\n" + dice.tbl.wrap_markdown(str(exc))
                self.stop()
                await self.err_channel.send(msg)

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

                real_users = [x for x in self.target_voice_channel.voice_members if not x.bot]
                if not real_users or \
                        (datetime.datetime.utcnow() - last_activity).seconds > MPLAYER_TIMEOUT:
                    await self.quit()

            await asyncio.sleep(sleep_time)
