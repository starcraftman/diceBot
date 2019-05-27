"""
Implement a complete music player to play local media and youtube videos.

    Employ youtube_dl to fetch/transcode youtube videos to a cache.
    A general purpose player supporting basic features like
        play/pause/next/previous/shuffle
    Use a general Song object to modle/persist played volume & repeat settings per song.
    Simple tagging system for music.

See related Song/SongTag in dicedb.schema
"""
import asyncio
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
CACHE_LIMIT = dice.util.get_config('music', 'cache_limit', default=250) * 1024 ** 2
PLAYER_TIMEOUT = dice.util.get_config('music', 'player_timeout', default=120)  # seconds
VOICE_JOIN_TIMEOUT = dice.util.get_config('music', 'voice_join_timeout', default=5)  # seconds
TIMEOUT_MSG = """ Bot joining voice took more than {} seconds.

Try again later or contact bot owner. """.format(VOICE_JOIN_TIMEOUT)
# Filename goes after o flag, urls at end
YTDL_CMD = "youtube-dl -x --audio-format opus --audio-quality 0 -o"  # + out_template + url
YTDL_PLAYLIST = "youtube-dl -j --flat-playlist"  # + url

# Stupid youtube: https://github.com/Rapptz/discord.py/issues/315
# Archived if go back to streaming youtube
#  BEFORE_OPTS = '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'


def run_cmd_with_retries(args, retries=3):
    """
    Execute a command (args) on the local system.
    If the command fails, retry after a short delay retries times.

    Args:
        args: The command to execute as a list of strings.
        retries: Retry any failed command this many times.

    Raises:
        CalledProcessError - Failed retries times, the last time command returned not zero.
        TimeoutExpired - Failed retries times, the last time command timed out.

    Returns:
        The decoded unicode string of the captured STDOUT of the command run.
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
    Download a video off youtube, extract the audio
    and save the video as an opus encoded media file.

    Args:
        url: The url of a youtube video.
        name: The name the video should be saved to.
        out_path: The folder to download the video to.

    Raises:
        See run_cmd_with_retries

    Returns:
        The path to the downloaded video.
    """
    try:
        os.makedirs(os.path.dirname(out_path))
    except OSError:
        pass

    fname = os.path.join(out_path, name + ".%(ext)s")
    run_cmd_with_retries(shlex.split(YTDL_CMD) + [fname, url])

    return os.path.join(out_path, name + ".opus")


async def get_yt_info(url):
    """
    Fetches information on a youtube playlist url.
    Returns a list that contains pairs of (video_url, title) for
    every video in the palylist.

    Raises:
        See run_cmd_with_retries

    Returns:
        [(video_url_1, title_1), (video_url_2, title_2), ...]
    """
    args = shlex.split(YTDL_PLAYLIST) + [url]
    capture = await asyncio.get_event_loop().run_in_executor(None, run_cmd_with_retries, args)

    playlist_info = []
    json_str = '[' + ','.join(capture.strip().strip().split('\n')) + ']'
    for info in json.loads(json_str):
        playlist_info += [('https://youtu.be/' + info['id'], info['title'].replace('/', ''))]

    return playlist_info


def prune_cache(cache_dir, limit=CACHE_LIMIT, *, prefix=None):
    """
    Scan a folder for all files or if optional prefix provided, only those matching it.
    Total their filesize and keep removing the oldest video until
    total filesize < limit.

    Args:
        cache_dir: Path to local files to examine.
        limit: The maximum size of the cache_dir before pruning older files.
        prefix: Optional kwarg prefix, if provided only match files with this prefix.

    Raises:
        OSError: Error during file removal, likely permissions problem.
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


def make_stream(vid):
    """
    Then just returns the stream object required for the voice client.

    Args:
        vid: The Song to play over the stream.

    Raises:
        FileNotFoundError: Attempted to play a song that did not exist locally.

    Returns:
        An AudioStream ready to be served by the discord voice client.
    """
    if not vid.ready:
        raise FileNotFoundError("Missing Song: " + vid.fname)

    now = time.time()
    os.utime(vid.fname, (now, now))

    return discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(vid.fname), vid.volume)


async def gplayer_monitor(players, activity, gap=3):
    """
    An asynchronous task to monitor to ...
        - Disconnect the player when no users in channel or stopped for timeout.
        - Prune the cache of old videos to reclaim space when limit reached.

    Args:
        players: A reference to the structure containing all GuildPlayers.
        activity: A dictionary containing tracking info on last activity of players.
        gap: Time to wait between checking the gplayer for idle connections.
    """
    await asyncio.sleep(gap)
    asyncio.ensure_future(gplayer_monitor(players, activity, gap))

    log = logging.getLogger('dice.music')
    prune_cache(dice.util.get_config('paths', 'youtube'))

    cur_date = datetime.datetime.utcnow()
    log.debug('GPlayer Monitor: %s %s  %s', cur_date, str(players), str(activity))
    for pid, player in players.items():
        try:
            if not player.target_channel or not player.is_connected():
                raise AttributeError
        except (AttributeError, IndexError):
            continue

        if player.is_playing():
            activity[pid] = cur_date

        real_users = [x for x in player.target_channel.members if not x.bot]
        has_timed_out = (cur_date - activity[pid]).seconds > PLAYER_TIMEOUT
        if not real_users or has_timed_out:
            log.debug('GPlayer Monitor: disconnect %s', player)
            await player.disconnect()


async def prefetch_all(vids, *, sequential=False):
    """
    Aynchronously wait until all songs are downloaded by processes in the background.
    On return, all videos must be available.

    Args:
        vids: A list of Songs to download.
    """
    streams = [asyncio.get_event_loop().run_in_executor(None, get_yt_video, vid.url, vid.name, vid.folder)
               for vid in vids if vid.url and not os.path.exists(vid.fname)]

    return await asyncio.gather(*streams)


async def prefetch_in_order(vids):
    """
    Songs will be downloaded in pairs from front and back of vids list.
    On return, all videos must be available.

    Args:
        vids: A list of Songs to download.
    """
    to_download = [vid for vid in vids if not vid.ready]

    loop = asyncio.get_event_loop()
    while to_download:
        jobs = []
        for index in [0, -1]:
            try:
                vid = to_download.pop(index)
                jobs += [loop.run_in_executor(None, get_yt_video, vid.url, vid.name, vid.folder)]
            except IndexError:
                pass

        await asyncio.gather(*jobs)


# Implemented in self.__client, stop, pause, resume, disconnect(async), move_to(async)
class GuildPlayer():
    """
    A player that wraps a discord.VoiceClient, extending the functionality to
    encompass a standard player with a builtin music queue and standard features.

    Attributes:
        cur_vid: The current Song playing, None if no vids have been set.
        vids: A list of Songs, they store per video settings and provide a path to the file to stream.
        itr: A bidirectional iterator to move through Songs.
        shuffle: When True next video is randomly selected until all videos fairly visited.
        repeat_all: When True, restart the queue at the beginning when finished.
        target_channel: The voice channel to connect to.
        __client: The reference to discord.VoiceClient, needed to manipulate underlying client.
                  Do no use directly, just use as if was self.
    """
    def __init__(self, *, cur_vid=None, vids=None, itr=None, repeat_all=False, shuffle=False,
                 target_channel=None, client=None):
        if not vids:
            vids = []
        self.vids = list(vids)
        self.itr = itr
        self.cur_vid = cur_vid  # The current Song, or None if nothing in list.
        self.repeat_all = repeat_all  # Repeat vids list when last song finished
        self.shuffle = shuffle
        self.target_channel = target_channel

        self.__client = client

        if self.vids and not self.itr and not self.cur_vid:
            self.reset_iterator()

    def __getattr__(self, attr):
        """ Transparently pass calls to the client we are extending. """
        if not self.__client:
            raise AttributeError("Client is not set.")

        return getattr(self.__client, attr)

    def __str__(self):
        """ Summarize the status of the GuildPlayer for a user. """
        try:
            current = str(self.cur_vid).split('\n')[0]
        except (AttributeError, IndexError):
            current = ''

        pad = "\n    "
        try:
            vids = self.itr.items
        except AttributeError:
            vids = self.vids
        str_vids = pad + pad.join([str(x) for x in vids])

        return """__**Player Status**__ :

__Now Playing__:
    {now_play}
__State__: {state}
__Repeat All__: {repeat}
__Shuffle__: {shuffle}
__Video List__:{vids}
""".format(now_play=current, vids=str_vids, state=self.state.capitalize(),
           repeat='{}abled'.format('En' if self.repeat_all else 'Dis'),
           shuffle='{}abled'.format('En' if self.shuffle else 'Dis'))

    def __repr__(self):
        keys = ['cur_vid', 'vids', 'itr', 'repeat_all', 'shuffle', 'target_channel']
        kwargs = ['{}={!r}'.format(key, getattr(self, key)) for key in keys]

        return "GuildPlayer({})".format(', '.join(kwargs))

    def is_done(self):
        """ True only if reached end of playlist and not set to repeat. """
        return self.itr.is_finished() and not self.repeat_all

    @property
    def state(self):
        """ The state of the player, either 'paused', 'playing' or 'stopped'. """
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
        """ Set the volume for the current song playing and persist choice.  """
        try:
            self.cur_vid.volume = new_volume
            self.source.volume = self.cur_vid.volume
        except AttributeError:
            pass

    def set_vids(self, new_vids):
        """ Replace the current videos and reset iterator. """
        for vid in new_vids:
            if not isinstance(vid, Song):
                raise ValueError("Must add Songs to the GuildPlayer.")

        self.vids = list(new_vids)
        self.reset_iterator()

    def append_vids(self, new_vids):
        """ Append videos into the player and update iterator. """
        for vid in new_vids:
            if not isinstance(vid, Song):
                raise ValueError("Must add Songs to the GuildPlayer.")

        self.vids += new_vids
        if self.shuffle:
            rand.shuffle(new_vids)
        self.itr.items += new_vids

    def play(self, next_vid=None):
        """
        Play the cur_vid, if it is playing it will be restarted.
        Optional play next_vid instead of cur_vid if it is provided.
        """
        if not self.vids:
            raise dice.exc.InvalidCommandArgs("No videos set to play. Add some!")

        if not self.is_connected():
            raise dice.exc.RemoteError("Bot no longer connected to voice.")
        if self.is_playing():
            self.stop()

        vid = next_vid if next_vid else self.cur_vid
        self.__client.play(make_stream(vid), after=self.after_play)

    async def play_when_ready(self, vid=None, timeout=20):
        """
        Wait for the Song to be locally available.
        When it is, call play_func with vid.
        On return, the Song must be available and playing.

        Args:
            vid: A Song to download then play.
            timeout: Maximum time to wait for download.

        Raises:
            TimeoutError: Timed out waiting for the Song to be ready.
        """
        if not vid:
            vid = self.cur_vid

        start = datetime.datetime.now()
        while not vid.ready:
            if (datetime.datetime.now() - start).seconds > timeout:
                raise TimeoutError

            await asyncio.sleep(0.5)

        self.play(vid)

    def after_play(self, error):
        """
        To be executed on error or after stream finishes.
        """
        if error:
            logging.getLogger('dice.music').error(str(error))

        if self.is_playing() or self.is_done():
            return

        if self.itr.is_finished() and self.repeat_all:
            self.reset_iterator(to_last=(self.itr.index == -1))
        elif not self.cur_vid.repeat:
            self.next()
        self.play()

    def toggle_pause(self):
        """ Toggle pausing the player. """
        if self.is_connected():
            if self.is_playing():
                self.pause()
            elif self.is_paused():
                self.resume()

    def toggle_shuffle(self):
        """ Toggle shuffling the playlist. Updates the iterator for consistency. """
        self.shuffle = not self.shuffle
        self.reset_iterator()

    def reset_iterator(self, *, to_last=False):
        """
        Reset the iterator and shuffle if required.

        Args:
            to_last: When False, iterator points to first item.
                     When True, iterator points to last item.
        """
        items = self.vids.copy()
        if self.shuffle:
            rand.shuffle(items)
        self.itr = dice.util.BIterator(items)
        self.cur_vid = next(self.itr)

        if to_last:  # Reset iterator to the last item
            try:
                while True:
                    next(self.itr)
            except StopIteration:
                pass
            self.cur_vid = self.itr.prev()

    def next(self):
        """
        Go to the next song.

        Returns:
            The newly selected Song. None if the iterator is exhausted.
        """
        try:
            self.cur_vid = self.itr.next()
            return self.cur_vid
        except StopIteration:
            if self.repeat_all:
                self.reset_iterator()
                return self.cur_vid

            self.stop()

    def prev(self):
        """
        Go to the previous song.

        Returns:
            The newly selected Song. None if the iterator is exhausted.
        """
        try:
            self.cur_vid = self.itr.prev()
            return self.cur_vid
        except StopIteration:
            if self.repeat_all:
                self.reset_iterator(to_last=True)
                return self.cur_vid

            self.stop()

    async def replace_and_play(self, new_vids):
        """
        Replace the playlist with new_vids.
        Take care to download them if needed and play them.
        Thia is primarily a convenience compounding a useful flow.

        Args:
            new_vids: New Songs to play, will replace the current queue.
        """
        await dice.music.prefetch_all(new_vids[:1])
        await self.join_voice_channel()

        self.set_vids(new_vids)
        self.play()
        await dice.music.prefetch_in_order(new_vids[1:])

    async def disconnect(self):
        """
        Only called when sure bot voice services no longer needed.

        Stops playing, disconnects bot from channel and unsets the voice client.
        """
        try:
            self.stop()
            await self.__client.disconnect()
            self.__client = None
        except AttributeError:
            pass

    async def join_voice_channel(self):
        """
        Join the right channel before beginning transmission. If client is currently
        connected then move to the correct channel.

        Raises:
            UserException - The bot could not join voice within a timeout. Discord network issue?
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
