"""
New Music player for the bot.
"""
import asyncio
import datetime
import logging
import os
import pathlib
import random
import subprocess
import time

import discord

import dice.exc
import dice.util
from dicedb.schema import Song  # noqa F401 pylint: disable=unused-import


CACHE_LIMIT = dice.util.get_config('music', 'cache_limit', default=100) * 1024 ** 2
PLAYER_TIMEOUT = dice.util.get_config('music', 'player_timeout', default=120)  # seconds
VOICE_JOIN_TIMEOUT = dice.util.get_config('music', 'voice_join_timeout', default=5)  # seconds
TIMEOUT_MSG = """ Bot joining voice took more than {} seconds.

Try again later or get Gears. """.format(VOICE_JOIN_TIMEOUT)
# Filename goes after o flag, urls at end
YTDL_CMD = "youtube-dl -o -x --audio-format opus --audio-quality 0"

# Stupid youtube: https://github.com/Rapptz/discord.py/issues/315
# Archived if go back to streaming youtube
#  BEFORE_OPTS = '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'


def youtube_dl(url, name, out_path=None):
    """
    Download a youtube video in the right audio format.
    """
    if not out_path:
        out_path = dice.util.get_config('paths', 'music')

    try:
        os.makedirs(os.path.dirname(out_path))
    except OSError:
        pass

    fname = os.path.join(out_path, name + ".%(ext)s")
    args = YTDL_CMD.split(' ')
    args = args[:2] + [fname] + args[2:] + [url]

    retries = 3
    while retries:
        try:
            subprocess.check_call(args)
            break
        except subprocess.CalledProcessError as exc:
            logging.getLogger('dice.music').error(str(exc))
            if not retries:
                raise
        retries -= 1
        time.sleep(random.randint(0, 5))

    return fname


def prune_cache(cache_dir, *, prefix=None, limit=CACHE_LIMIT):
    """
    Remove the oldest videos in the cache_dir.
    If prefix given select those that start with prefix.
    Otherwise consider all files in the cache_dir.
    """
    path = pathlib.Path(cache_dir)
    matcher = '{}*'.format(prefix) if prefix else '*'
    songs = sorted(list(path.glob(matcher)), key=lambda x: x.stat().st_mtime)
    total_size = 0
    for song in songs:
        total_size += os.stat(song).st_size

    while total_size > limit:
        total_size -= os.stat(songs[0]).st_size
        os.remove(songs[0])
        songs = songs[1:]


def make_stream(video):
    """
    Fetches a local copy of the video if required.
    Then just returns the stream object required for the voice client.
    """
    if video.is_remote() and not os.path.exists(video.fname):
        youtube_dl(video.url, video.name, video.folder)

    now = time.time()
    os.utime(video.fname, (now, now))

    return discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(video.fname), video.volume)


async def gplayer_monitor(players, gap=2):
    """
    Thi simple task monitors for:
        - prune old youtube videos cached
        - check if bots left without listeners in voice channels
    """
    activity = {}

    while True:
        prune_cache(dice.util.get_config('paths', 'youtube'))

        cur_date = datetime.datetime.utcnow()
        for pid in players:
            try:
                player = players[pid]
                if not player.target_channel or not player.is_connected():
                    raise AttributeError
            except (AttributeError, IndexError):
                continue

            if player.is_playing():
                activity[pid] = cur_date

            real_users = [x for x in player.target_channel.members if not x.bot]
            has_timed_out = (datetime.datetime.utcnow() - activity[pid]).seconds > PLAYER_TIMEOUT
            if not real_users or has_timed_out:
                await player.disconnect()

        await asyncio.sleep(gap)


# Implemented in self.__client, stop, pause, resume, disconnect(async), move_to(async)
class GuildPlayer(object):
    """
    Player represents the management of the video queue for
    a particular guild.
    """
    def __init__(self, *, vids=None, vid_index=0, repeat_all=False,
                 target_channel=None, err_channel=None, client=None):
        if not vids:
            vids = []
        self.vids = vids
        self.vid_index = vid_index
        self.repeat_all = False  # Repeat vids list when last song finished
        self.finished = False  # Set only when player should be stopped

        self.err_channel = err_channel  # Set to originating channel invoked
        self.target_channel = target_channel
        self.__client = client

    def __getattr__(self, attr):
        """
        Transparently pass calls to client, we are extending it
        to play a series of videos and cache volume/repeat prefs of songs."""
        if not self.__client:
            raise AttributeError("Client is not set.")

        return getattr(self.__client, attr)

    def __str__(self):
        try:
            current = self.cur_vid.name
        except (AttributeError, IndexError):
            current = ''

        pad = "\n    "
        str_vids = pad + pad.join([str(x) for x in self.vids])

        return """__**Player Status**__ :

__Now Playing__: {now_play}
__Status__: {status}
__Repeat All__: {repeat}
__Video List__:{vids}
""".format(now_play=current, vids=str_vids,
           status=self.status(), repeat=self.repeat_all)

    def __repr__(self):
        keys = ['vid_index', 'vids', 'repeat_all', 'err_channel', 'target_channel']
        kwargs = ['{}={!r}'.format(key, getattr(self, key)) for key in keys]

        return "GuildPlayer({})".format(', '.join(kwargs))

    @property
    def cur_vid(self):
        """ The current video playing/selected. If finished, will point to first. """
        try:
            return self.vids[self.vid_index]
        except TypeError:
            return None

    def status(self):
        state = 'stopped'

        try:
            if self.is_connected():
                if self.is_playing():
                    state = 'playing'
                elif self.is_paused():
                    state = 'paused'
        except AttributeError:
            pass

        return state

    def set_volume(self, new_volume):
        self.cur_vid.set_volume(new_volume)
        try:
            self.source.volume = self.cur_vid.volume
        except AttributeError:
            pass

    def play(self, replace_vids=None):
        """
        Play the vids in the list.
        If optional replace_vids passed, replace current queue and reset to start.
        """
        if replace_vids:
            self.vids = replace_vids
            self.vid_index = 0
        if not self.vids:
            raise dice.exc.InvalidCommandArgs("No videos set to play.")

        if self.is_playing():
            self.stop()

        self.finished = False
        self.__client.play(make_stream(self.cur_vid), after=self.after_call)

    def after_call(self, error):
        """
        To be executed on error or after stream finishes.
        """
        if error:
            logging.getLogger('dice.music').error(str(error))

        if self.is_playing() or self.finished:
            pass
        elif self.cur_vid.repeat:
            self.play()
        else:
            self.next()

    def toggle_pause(self):
        """ Toggle pausing the player. """
        if self.is_connected():
            if self.is_playing():
                self.pause()
            elif self.is_paused():
                self.resume()

    def next(self):
        """
        Go to the next song.
        """
        if self.repeat_all or (self.vid_index + 1) < len(self.vids):
            self.vid_index = (self.vid_index + 1) % len(self.vids)
            self.play()
        else:
            self.stop()
            self.finished = True

    def prev(self):
        """
        Go to the previous song.
        """
        if self.repeat_all or (self.vid_index - 1) >= 0:
            self.vid_index = (self.vid_index - 1) % len(self.vids)
            self.play()
        else:
            self.stop()
            self.finished = True

    async def disconnect(self):
        """
        Only called when sure bot voice services no longer needed.
        """
        try:
            self.stop()
            await self.__client.disconnect()
            self.__client = None
        except AttributeError:
            pass

    async def join_voice_channel(self):
        """
        Join the right channel before beginning transmission.

        Raises:
            InvalidCommandArgs - The bot could not join voice within a timeout. Discord network issue?
        """
        try:
            if self.__client:
                await asyncio.wait_for(self.__client.move_to(self.target_channel),
                                       VOICE_JOIN_TIMEOUT)
            else:
                self.__client = await asyncio.wait_for(self.target_channel.connect(),
                                                       VOICE_JOIN_TIMEOUT)
        except asyncio.TimeoutError:
            await self.disconnect()
            raise dice.exc.UserException(TIMEOUT_MSG)

    async def prefetch_vids(self, *, first_only=True):
        """
        Helper, prefetch either all videos or just the first.
        When it returns, videos are available.
        """
        streams = [asyncio.get_event_loop().run_in_executor(None, make_stream, vid)
                   for vid in self.vids[:1]]
        if not first_only:
            streams = [asyncio.get_event_loop().run_in_executor(None, make_stream, vid)
                       for vid in self.vids]

        return await asyncio.gather(*streams)
