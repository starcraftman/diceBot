"""
Music player for the bot.
"""
import asyncio
import datetime
import discord
import youtube_dl

import dice.exc


class MPlayerState:
    """ MPlayer state enum. """
    STOPPED = 0
    PLAYING = 1
    PAUSED = 2


# TODO: Tests? This is just a wrapper so should be covered by discord.py
class MPlayer(object):
    """
    Music player interface.
    """
    def __init__(self, bot):
        self.bot = bot
        self.channel = None
        self.vids = []
        self.vid_index = 0
        self.volume = 50
        self.loop = True
        self.state = MPlayerState.STOPPED

        self.__error_channel = None
        # Parts of the discord library wrapped
        self.__voice = None
        self.__player = None

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
        return "MPlayer(bot={}, channel={}, error_channel={}, voice={}, player={},"\
            " vids={}, vid_index={}, loop={}, volume={}, state={})".format(
                self.bot, self.channel, self.__error_channel, self.__voice, self.__player,
                self.vids, self.vid_index, self.loop, self.volume, self.state
            )

    @property
    def status(self):
        """ Textual version of state. """
        status = 'Stopped'
        if self.state == MPlayerState.PAUSED:
            status = 'Paused'
        elif self.state == MPlayerState.PLAYING:
            status = 'Playing'

        return status

    def initialize_settings(self, msg, vids):
        """
        Update current set videos and join requesting user in voice.
        """
        self.channel = msg.author.voice.voice_channel
        self.__error_channel = msg.channel
        if not self.channel:
            self.channel = discord.utils.get(msg.server.channels,
                                             type=discord.ChannelType.voice)

        self.vids = vids

    def set_volume(self, new_volume=None):
        """
        Set the volume for the bot.
        """
        if not new_volume:
            new_volume = self.volume

        try:
            new_volume = int(new_volume)
            if new_volume < 0 or new_volume > 100:
                raise ValueError
        except ValueError:
            raise dice.exc.InvalidCommandArgs("Volume must be between [1, 100]")

        self.volume = new_volume
        if self.__player:
            self.__player.volume = new_volume / 100

    async def update_voice_channel(self):
        """
        Join the right channel before beginning transmission.
        """
        if self.__voice:
            if self.channel != self.__voice.channel:
                await self.__voice.move_to(self.channel)
        else:
            self.__voice = await self.bot.join_voice_channel(self.channel)

    async def start(self):
        """
        Start the song currently selected.

        Raises:
            InvalidCommandArgs - No videos to play.
        """
        if not self.vids:
            raise dice.exc.InvalidCommandArgs("No videos to play!")

        self.stop()
        await self.update_voice_channel()

        vid = self.vids[self.vid_index]
        try:
            if "youtu" in vid:
                self.__player = await self.__voice.create_ytdl_player(vid)
            else:
                self.__player = self.__voice.create_ffmpeg_player(vid)
            self.__player.start()
            self.set_volume()
            self.state = MPlayerState.PLAYING
        except youtube_dl.utils.DownloadError as exc:
            if self.__error_channel:
                msg = "Player stopped. Error donwloading video: copyright?\n" + dice.tbl.wrap_markdown(str(exc))
                self.stop()
                await self.bot.send_message(self.__error_channel, msg)
        except youtube_dl.utils.YoutubeDLError as exc:
            if self.__error_channel:
                msg = "Player stopped. General YoutubeDL error.\n" + dice.tbl.wrap_markdown(str(exc))
                self.stop()
                await self.bot.send_message(self.__error_channel, msg)

    def pause(self):
        """
        Toggle player pause function.
        """
        if self.state == MPlayerState.PLAYING:
            self.__player.pause()
            self.state = MPlayerState.PAUSED
        elif self.state == MPlayerState.PAUSED:
            self.__player.resume()
            self.state = MPlayerState.PLAYING

    def stop(self):
        """
        Stop playing the stream.
        """
        try:
            self.state = MPlayerState.STOPPED
            self.__player.stop()
        except AttributeError:
            pass

    async def quit(self):
        """
        Ensure player stopped and quit the voice channel.
        """
        try:
            self.stop()
            await self.__voice.disconnect()
            self.__player = None
            self.__voice = None
        except AttributeError:
            pass

    async def prev(self):
        """
        Go to the previous song.
        """
        if self.__player and self.vids:
            if self.loop and self.vid_index > 0:
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
        if self.__player and self.vids:
            if self.loop or self.vid_index + 1 < len(self.vids):
                self.vid_index = (self.vid_index + 1) % len(self.vids)
                await self.start()
            else:
                self.vid_index = 0
                self.stop()
                raise dice.exc.InvalidCommandArgs("Loop is not set, queue finished. Stopping.")

    async def monitor(self, sleep_time=3):
        """
        Simple monitor task that lives as long as the bot runs.
        """
        last_activity = datetime.datetime.utcnow()

        while True:
            try:
                if self.__player and self.state == MPlayerState.PLAYING:
                    last_activity = datetime.datetime.utcnow()

                if self.state == MPlayerState.PLAYING and self.__player.is_done():
                    await self.next()

                if (datetime.datetime.utcnow() - last_activity).seconds > 300:
                    await self.quit()
            except AttributeError:
                pass

            await asyncio.sleep(sleep_time)
