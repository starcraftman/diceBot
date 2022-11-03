#  """
#  Implement a complete music player to play local media and youtube videos.

    #  Employ youtube_dl to fetch/transcode youtube videos to a cache.
    #  A general purpose player supporting basic features like
        #  play/pause/next/previous/shuffle
    #  Use a general Song object to modle/persist played volume & repeat settings per song.
    #  Simple tagging system for music.

#  See related Song/SongTag in dicedb.schema
#  """
#  import asyncio
#  import datetime
#  import json
#  import logging
#  import random
#  import re
#  import shlex
#  import subprocess
#  import time

#  import aiohttp
#  import bs4
#  from numpy import random as rand

#  import dice.exc
#  import dice.util
#  from dicedb.schema import Song  # noqa F401 pylint: disable=unused-import


#  CMD_TIMEOUT = 150
#  PLAYER_TIMEOUT = dice.util.get_config('music', 'player_timeout', default=120)  # seconds
#  VOICE_JOIN_TIMEOUT = dice.util.get_config('music', 'voice_join_timeout', default=5)  # seconds
#  TIMEOUT_MSG = """ Bot joining voice took more than {} seconds.

#  Try again later or contact bot owner. """.format(VOICE_JOIN_TIMEOUT)
#  YTDL_PLAYLIST = "youtube-dl -j --flat-playlist"  # + url
#  YT_SEARCH_REG = re.compile(r'((\d+) hours?)?[, ]*((\d+) minutes?)?[, ]*((\d+) seconds?)?[, ]*(([0-9,]+) views)?',
                           #  re.ASCII | re.IGNORECASE)
#  YT_SEARCH = "https://www.youtube.com/results?search_query="


#  def run_cmd_with_retries(args, retries=3):
    #  """
    #  Execute a command (args) on the local system.
    #  If the command fails, retry after a short delay retries times.

    #  Args:
        #  args: The command to execute as a list of strings.
        #  retries: Retry any failed command this many times.

    #  Raises:
        #  CalledProcessError - Failed retries times, the last time command returned not zero.
        #  TimeoutExpired - Failed retries times, the last time command timed out.

    #  Returns:
        #  The decoded unicode string of the captured STDOUT of the command run.
    #  """
    #  if retries < 1 or retries > 20:
        #  retries = 3

    #  while retries:
        #  try:
            #  return subprocess.check_output(args, timeout=CMD_TIMEOUT).decode()
        #  except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            #  # Occaisonally receive a 403 probably due to rate limits, retry after delay
            #  logging.getLogger('dice.music').error(str(exc))
            #  if not retries:
                #  raise
        #  retries -= 1
        #  time.sleep(random.randint(2, 6))


#  async def get_yt_info(url):
    #  """
    #  Fetches information on a youtube playlist url.
    #  Returns a list that contains pairs of (video_url, title) for
    #  every video in the palylist.

    #  Raises:
        #  See run_cmd_with_retries

    #  Returns:
        #  [(video_url_1, title_1), (video_url_2, title_2), ...]
    #  """
    #  args = shlex.split(YTDL_PLAYLIST) + [url]
    #  capture = await asyncio.get_event_loop().run_in_executor(None, run_cmd_with_retries, args)

    #  playlist_info = []
    #  json_str = '[' + ','.join(capture.strip().strip().split('\n')) + ']'
    #  for info in json.loads(json_str):
        #  playlist_info += [('https://youtu.be/' + info['id'], info['title'].replace('/', ''))]

    #  return playlist_info


#  async def gplayer_monitor(players, activity, gap=3):
    #  """
    #  An asynchronous task to monitor to ...
        #  - Disconnect the player when no users in channel or stopped for timeout.
        #  - Prune the cache of old videos to reclaim space when limit reached.

    #  Args:
        #  players: A reference to the structure containing all GuildPlayers.
        #  activity: A dictionary containing tracking info on last activity of players.
        #  gap: Time to wait between checking the gplayer for idle connections.
    #  """
    #  await asyncio.sleep(gap)
    #  asyncio.ensure_future(gplayer_monitor(players, activity, gap))

    #  log = logging.getLogger('dice.music')
    #  cur_date = datetime.datetime.utcnow()
    #  log.debug('GPlayer Monitor: %s %s  %s', cur_date, str(players), str(activity))
    #  for pid, player in players.items():
        #  try:
            #  if not player.voice_channel or not player.is_connected():
                #  raise AttributeError
        #  except (AttributeError, IndexError):
            #  continue

        #  if player.is_playing() or player.is_paused():
            #  activity[pid] = cur_date

        #  has_timed_out = (cur_date - activity[pid]).seconds > PLAYER_TIMEOUT
        #  real_users = [x for x in player.voice_channel.members if not x.bot]
        #  if not real_users or has_timed_out:
            #  log.debug('GPlayer Monitor: disconnect %s', player)
            #  await player.disconnect()


#  def parse_search_label(line):
    #  """
    #  Parse the label for video duration & view count from a youtube label.

    #  Args:
        #  line: A string containing the label parsed from youtube html.

    #  Returns:
        #  [duration, views]

        #  duration: A string of format HH:MM:SS. Empty if errored during parsing.
        #  views: The integer view count of the video. 0 if no information found.
    #  """
    #  try:
        #  duration, views = '', 0
        #  index = line.index('ago')
        #  if index != -1:
            #  line = line[index + 3:].strip()

        #  matched = YT_SEARCH_REG.match(line)
        #  if matched:
            #  time_parts = []
            #  for num in (2, 4, 6):
                #  time_parts += [matched.group(num) if matched.group(num) else 0]

            #  duration = "{}:{:>2}:{:>2}".format(*time_parts).replace(' ', '0')
            #  views = int(matched.group(8).replace(',', ''))

            #  if duration == "0:00:00":
                #  duration = ""
    #  except (AttributeError, ValueError):
        #  duration, views = '', 0

    #  return duration, views


#  async def yt_search(terms):
    #  """
    #  Search youtube for terms & return results to present to the user.
    #  Returns first 20 results as presented on first page of search.

    #  Returns:
        #  A list of the following form:
        #  [
            #  {'url': url, 'title': title, 'duration': duration, 'views': views},
            #  {'url': url, 'title': title, 'duration': duration, 'views': views},
            #  {'url': url, 'title': title, 'duration': duration, 'views': views},
            #  ...
        #  ]

        #  Breakdown:
            #  url: Either a shortened video link or a link to a full playlist.
            #  title: The title of the video or playlist.
            #  duration: For videos, the HH:MM:SS it asts for. For playlists, ''.
            #  views: For videos, the view count. For playlists, 0.
    #  """
    #  async with aiohttp.ClientSession() as session:
        #  async with session.get(YT_SEARCH + "+".join(terms)) as resp:
            #  soup = bs4.BeautifulSoup(await resp.text(), 'html.parser')

    #  log = logging.getLogger('dice.music')
    #  log.debug("Requested Search: %s", "+".join(terms))
    #  log.debug("Returned:\n\n %s", str(soup.find_all('div', class_='yt-lockup-content')))

    #  results = []
    #  for match in soup.find_all('div', class_='yt-lockup-content'):
        #  try:
            #  url = match.a.get('href')
        #  except AttributeError:
            #  url = ''
        #  if 'watch?v=' not in url:
            #  continue

        #  if '&list=' in url:
            #  url = "https://youtube.com" + url
        #  else:
            #  url = "https://youtu.be/" + url.replace("/watch?v=", "")

        #  duration, views = parse_search_label(match.span.get('aria-label'))

        #  results += [{'url': url, 'title': match.a.get('title'), 'duration': duration, 'views': views}]

    #  return results


#  # Implemented in self.__client, stop, pause, resume, disconnect(async), move_to(async)
#  class GuildPlayer():
    #  """
    #  A player that wraps a discord.VoiceClient, extending the functionality to
    #  encompass a standard player with a builtin music queue and standard features.

    #  Attributes:
        #  cur_vid: The current Song playing, None if no vids have been set.
        #  vids: A list of Songs, they store per video settings and provide a path to the file to stream.
        #  itr: A bidirectional iterator to move through Songs.
        #  shuffle: When True next video is randomly selected until all videos fairly visited.
        #  repeat_all: When True, restart the queue at the beginning when finished.
        #  voice_channel: The voice channel to connect to.
        #  __client: The reference to discord.VoiceClient, needed to manipulate underlying client.
                  #  Do no use directly, just use as if was self.
    #  """
    #  def __init__(self, *, cur_vid=None, vids=None, itr=None, repeat_all=False, shuffle=False,
                 #  voice_channel=None, text_channel=None, client=None):
        #  if not vids:
            #  vids = []
        #  self.vids = list(vids)
        #  self.itr = itr
        #  self.cur_vid = cur_vid  # The current Song, or None if nothing in list.
        #  self.repeat_all = repeat_all  # Repeat vids list when last song finished
        #  self.shuffle = shuffle
        #  self.voice_channel = voice_channel
        #  self.text_channel = text_channel

        #  self.__client = client

        #  if self.vids and not self.itr and not self.cur_vid:
            #  self.reset_iterator()

    #  def __getattr__(self, attr):
        #  """ Transparently pass calls to the client we are extending. """
        #  if not self.__client:
            #  raise AttributeError("Client is not set.")

        #  return getattr(self.__client, attr)

    #  def __str__(self):
        #  """ Summarize the status of the GuildPlayer for a user. """
        #  try:
            #  current = str(self.cur_vid).split('\n')[0]
        #  except (AttributeError, IndexError):
            #  current = ''

        #  pad = "\n    "
        #  try:
            #  vids = self.itr.items
        #  except AttributeError:
            #  vids = self.vids
        #  str_vids = pad + pad.join([str(x) for x in vids])

        #  return """__**Player Status**__ :

#  __Now Playing__:
    #  {now_play}
#  __State__: {state}
#  __Repeat All__: {repeat}
#  __Shuffle__: {shuffle}
#  __Video List__:{vids}
#  """.format(now_play=current, vids=str_vids, state=self.state.capitalize(),
           #  repeat='{}abled'.format('En' if self.repeat_all else 'Dis'),
           #  shuffle='{}abled'.format('En' if self.shuffle else 'Dis'))

    #  def __repr__(self):
        #  keys = ['cur_vid', 'vids', 'itr', 'repeat_all', 'shuffle', 'voice_channel', 'text_channel']
        #  kwargs = ['{}={!r}'.format(key, getattr(self, key)) for key in keys]

        #  return "GuildPlayer({})".format(', '.join(kwargs))

    #  def is_connected(self):
        #  """ True IFF the bot is connected. """
        #  try:
            #  return self.__client.is_connected()
        #  except AttributeError:
            #  return False

    #  def is_playing(self):
        #  """ Implies is__connected and the stream is playing. """
        #  try:
            #  return self.__client.is_playing()
        #  except AttributeError:
            #  return False

    #  def is_paused(self):
        #  """ Implies is__connected and the stream is paused. """
        #  try:
            #  return self.__client.is_paused()
        #  except AttributeError:
            #  return False

    #  def is_done(self):
        #  """ True only if reached end of playlist and not set to repeat. """
        #  return not self.itr or (self.itr.is_finished() and not self.repeat_all)

    #  @property
    #  def state(self):
        #  """ The state of the player, either 'paused', 'playing' or 'stopped'. """
        #  state = 'stopped'

        #  try:
            #  if self.is_connected():
                #  if self.is_playing():
                    #  state = 'playing'
                #  elif self.is_paused():
                    #  state = 'paused'
        #  except AttributeError:
            #  pass

        #  return state

    #  def set_volume(self, new_volume):
        #  """ Set the volume for the current song playing and persist choice.  """
        #  try:
            #  self.cur_vid.volume = new_volume
            #  self.source.volume = self.cur_vid.volume
        #  except AttributeError:
            #  pass

    #  def set_vids(self, new_vids):
        #  """ Replace the current videos and reset iterator. """
        #  for vid in new_vids:
            #  if not isinstance(vid, Song):
                #  raise ValueError("Must add Songs to the GuildPlayer.")

        #  self.vids = list(new_vids)
        #  self.cur_vid = None
        #  self.itr = None
        #  if new_vids:
            #  self.reset_iterator()

    #  def append_vids(self, new_vids):
        #  """
        #  Append videos into the player and update iterator.
        #  If needed, new vids will be downloaded in the background.
        #  """
        #  for vid in new_vids:
            #  if not isinstance(vid, Song):
                #  raise ValueError("Must add Songs to the GuildPlayer.")

        #  self.vids += new_vids
        #  if self.shuffle:
            #  rand.shuffle(new_vids)

        #  if self.is_done():
            #  self.reset_iterator()
        #  else:
            #  self.itr.items += new_vids

    #  def play(self, next_vid=None):
        #  """
        #  Play the cur_vid, if it is playing it will be restarted.
        #  Optional play next_vid instead of cur_vid if it is provided.
        #  """
        #  if not self.vids:
            #  raise dice.exc.InvalidCommandArgs("No videos set to play. Add some!")

        #  if not self.is_connected():
            #  raise dice.exc.RemoteError("Bot no longer connected to voice.")

        #  vid = next_vid if next_vid else self.cur_vid
        #  try:
            #  dice.util.BOT.status = vid.name
        #  except AttributeError:
            #  pass

        #  last_source = self.__client.source
        #  if self.is_playing() or self.is_paused():
            #  self.__client.source = vid.stream()
        #  else:
            #  self.__client.play(vid.stream(), after=self.after_play)

        #  try:
            #  last_source.pcmd.terminate()
            #  last_source.pcmd = None
        #  except (AttributeError, OSError):
            #  pass

    #  def after_play(self, error):
        #  """
        #  To be executed on error or after stream finishes.
        #  """
        #  if error:
            #  logging.getLogger('dice.music').error(str(error))

        #  if not self.is_connected() or self.is_playing() or self.is_done():
            #  return

        #  last_source = self.__client.source
        #  if self.itr.is_finished() and self.repeat_all:
            #  self.reset_iterator(to_last=(self.itr.index == -1))
        #  elif not self.cur_vid.repeat:
            #  self.next()
        #  self.play()

        #  try:
            #  last_source.pcmd.terminate()
            #  last_source.pcmd = None
        #  except (AttributeError, OSError):
            #  pass

    #  def toggle_shuffle(self):
        #  """ Toggle shuffling the playlist. Updates the iterator for consistency. """
        #  self.shuffle = not self.shuffle
        #  self.reset_iterator()

    #  def reset_iterator(self, *, to_last=False):
        #  """
        #  Reset the iterator and shuffle if required.

        #  Args:
            #  to_last: When False, iterator points to first item.
                     #  When True, iterator points to last item.
        #  """
        #  items = self.vids.copy()
        #  if self.shuffle:
            #  rand.shuffle(items)
        #  self.itr = dice.util.BIterator(items)
        #  self.cur_vid = next(self.itr)

        #  if to_last:  # Reset iterator to the last item
            #  try:
                #  while True:
                    #  next(self.itr)
            #  except StopIteration:
                #  pass
            #  self.cur_vid = self.itr.prev()

    #  def next(self):
        #  """
        #  Go to the next song.

        #  Returns:
            #  The newly selected Song. None if the iterator is exhausted.
        #  """
        #  try:
            #  self.cur_vid = self.itr.next()
            #  return self.cur_vid
        #  except StopIteration:
            #  try:
                #  dice.util.BOT.status = 'Queue finished'
            #  except AttributeError:
                #  pass
            #  if self.repeat_all:
                #  self.reset_iterator()
                #  return self.cur_vid

            #  self.stop()
            #  raise

    #  def prev(self):
        #  """
        #  Go to the previous song.

        #  Returns:
            #  The newly selected Song. None if the iterator is exhausted.
        #  """
        #  try:
            #  self.cur_vid = self.itr.prev()
            #  return self.cur_vid
        #  except StopIteration:
            #  if self.repeat_all:
                #  self.reset_iterator(to_last=True)
                #  return self.cur_vid

            #  self.stop()
            #  raise

    #  def dedupe(self):
        #  """
        #  Remove all duplicate entries in the vids list.
        #  The iterator is reset and pointing to current playing video.
        #  """
        #  old_len = len(self.vids)
        #  old_cur = self.cur_vid
        #  self.vids = list({vid for vid in self.vids})
        #  self.reset_iterator()
        #  self.cur_vid = old_cur

        #  while self.cur_vid and self.itr.current != self.cur_vid:
            #  next(self.itr)

        #  return old_len - len(self.vids)

    #  async def disconnect(self):
        #  """
        #  Only called when sure bot voice services no longer needed.

        #  Stops playing, disconnects bot from channel and unsets the voice client.
        #  """
        #  try:
            #  last_source = self.__client.source
            #  self.stop()
            #  await self.__client.disconnect()
            #  self.__client = None

            #  last_source.pcmd.terminate()
            #  last_source.pcmd = None
        #  except (AttributeError, OSError):
            #  pass

    #  async def join_voice_channel(self):
        #  """
        #  Join the right channel before beginning transmission. If client is currently
        #  connected then move to the correct channel.

        #  Raises:
            #  UserException - The bot could not join voice within a timeout. Discord network issue?
        #  """
        #  try:
            #  if self.__client:
                #  await asyncio.wait_for(self.__client.move_to(self.voice_channel),
                                       #  VOICE_JOIN_TIMEOUT)
            #  else:
                #  self.__client = await asyncio.wait_for(self.voice_channel.connect(),
                                                       #  VOICE_JOIN_TIMEOUT)
        #  except asyncio.TimeoutError:
            #  await self.disconnect()
            #  raise dice.exc.UserException(TIMEOUT_MSG)
