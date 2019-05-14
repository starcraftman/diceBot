"""
New Music player for the bot.
"""
import asyncio
import copy
import datetime
import json
import logging
import os
import pathlib
import random
import shlex
import subprocess
import time

import discord
from numpy import random as rand

import dice.exc
import dice.util
from dicedb.schema import Song  # noqa F401 pylint: disable=unused-import


CMD_TIMEOUT = 15
CACHE_LIMIT = dice.util.get_config('music', 'cache_limit', default=100) * 1024 ** 2
PLAYER_TIMEOUT = dice.util.get_config('music', 'player_timeout', default=120)  # seconds
VOICE_JOIN_TIMEOUT = dice.util.get_config('music', 'voice_join_timeout', default=5)  # seconds
TIMEOUT_MSG = """ Bot joining voice took more than {} seconds.

Try again later or get Gears. """.format(VOICE_JOIN_TIMEOUT)
# Filename goes after o flag, urls at end
YTDL_CMD = "youtube-dl -x --audio-format opus --audio-quality 0 -o"  # + out_template + url
YTDL_PLAYLIST = "youtube-dl -j --flat-playlist"  # + url

# Stupid youtube: https://github.com/Rapptz/discord.py/issues/315
# Archived if go back to streaming youtube
#  BEFORE_OPTS = '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'


def run_cmd_with_retries(args, retries=3):
    """
    Execute args command, ensure out_path exists before running.

    Raises:
        CalledProcessError - When the command fails after retries times.
    """
    if retries < 1 or retries > 20:
        retries = 3

    while retries:
        try:
            return subprocess.check_output(args, timeout=CMD_TIMEOUT).decode()
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            # Occaisonally receive a 403 probably due to rate limits, retry after delay
            logging.getLogger('dice.music').error(str(exc))
            if not retries:
                raise
        retries -= 1
        time.sleep(random.randint(2, 6))


def get_yt_video(url, name, out_path):
    """
    Download a youtube video to the the out_path folder with name.
    """
    try:
        os.makedirs(os.path.dirname(out_path))
    except OSError:
        pass

    fname = os.path.join(out_path, name + ".%(ext)s")
    run_cmd_with_retries(shlex.split(YTDL_CMD) + [fname, url])

    return fname


async def get_yt_info(url):
    """
    Fetches information on a youtube playlist url.
    Returns all pairs of [(video_url, title), ...]
    """
    try:
        args = shlex.split(YTDL_PLAYLIST) + [url]
        proc = subprocess.Popen(args, stdout=subprocess.PIPE)
        await asyncio.get_event_loop().run_in_executor(None, proc.wait, CMD_TIMEOUT)
        capture, _ = proc.communicate()
    except subprocess.TimeoutExpired:
        raise dice.exc.UserException("Playlist fetch impossible at this time.")

    playlist_info = []
    json_str = '[' + ','.join(capture.strip().decode().strip().split('\n')) + ']'
    for info in json.loads(json_str):
        playlist_info += [('https://youtu.be/' + info['id'], info['title'].replace('/', ''))]

    return playlist_info


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
    if not os.path.exists(video.fname):
        raise dice.exc.InternalException("The video is not available to stream.")

    now = time.time()
    os.utime(video.fname, (now, now))

    return discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(video.fname), video.volume)


async def gplayer_monitor(players, gap=3):
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
            has_timed_out = (cur_date - activity[pid]).seconds > PLAYER_TIMEOUT
            if not real_users or has_timed_out:
                await player.disconnect()

        await asyncio.sleep(gap)


async def prefetch_vids(vids):
    """
    Helper, prefetch any vids in the list.
    """
    streams = [asyncio.get_event_loop().run_in_executor(None, get_yt_video, vid.url, vid.name, vid.folder)
               for vid in vids]

    return await asyncio.gather(*streams)


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
        self.shuffle = None  # When enable, put copy of vids list here and select from.
        self.repeat_all = False  # Repeat vids list when last song finished
        self.finished = False  # Set only when player should be stopped

        self.err_channel = err_channel  # Set to originating channel invoked
        self.target_channel = target_channel
        self.__client = client
        self.__now_playing = None  # Unfortunately necessitated by shuffle, see cur_vid

    def __getattr__(self, attr):
        """
        Transparently pass calls to client, we are extending it
        to play a series of videos and cache volume/repeat prefs of songs."""
        if not self.__client:
            raise AttributeError("Client is not set.")

        return getattr(self.__client, attr)

    def __str__(self):
        try:
            current = str(self.cur_vid).split('\n')[0]
        except (AttributeError, IndexError):
            current = ''

        pad = "\n    "
        str_vids = pad + pad.join([str(x) for x in self.vids])

        return """__**Player Status**__ :

__Now Playing__:
    {now_play}
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
            return self.__now_playing if self.__now_playing else self.vids[self.vid_index]
        except (IndexError, TypeError):
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

    def replace_vids(self, new_vids):
        for vid in new_vids:
            if not isinstance(vid, Song):
                raise ValueError("Must add Songs to the GuildPlayer.")

        self.vids = new_vids
        self.vid_index = 0

    def play(self, next_vid=None):
        """
        Play or restart the current video.
        Optional play next_vid instead of cur_vid.
        """
        if not self.vids:
            raise dice.exc.InvalidCommandArgs("No videos set to play. Add some!")

        if not self.is_connected():
            raise dice.exc.RemoteError("Bot no longer connected to voice.")
        if self.is_playing():
            self.stop()

        vid = self.cur_vid
        if next_vid:
            vid = next_vid
        self.finished = False
        self.__client.play(make_stream(vid), after=self.after_call)

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

    def toggle_shuffle(self):
        """ Toggle shuffling the playlist. """
        if self.shuffle:
            self.shuffle = None
            self.__now_playing = None
        else:
            self.shuffle = copy.copy(self.vids)

    def restart_shuffle(self):
        """ Simply repopulate the shuffled list. """
        self.shuffle = copy.copy(self.vids)

    def next(self):
        """
        Go to the next song.
        """
        self.__select_next_song(lambda self: (self.vid_index + 1) < len(self.vids),
                                lambda self: (self.vid_index + 1) % len(self.vids))

    def prev(self):
        """
        Go to the previous song.
        """
        self.__select_next_song(lambda self: (self.vid_index - 1) >= 0,
                                lambda self: (self.vid_index - 1) % len(self.vids))

    def __select_next_song(self, check_func, inc_func):
        """
        Select the next song to play, depends on check_func and inc_func.
        """
        if self.shuffle:
            selected = rand.choice(self.shuffle)
            self.shuffle.remove(selected)
            if not self.shuffle:
                self.restart_shuffle()
            self.__now_playing = selected
            self.play(selected)
        elif self.repeat_all or check_func(self):
            self.vid_index = inc_func(self)
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
