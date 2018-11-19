"""
To facilitate complex actions based on commands create a
hierarchy of actions that can be recombined in any order.
All actions have async execute methods.
"""
from __future__ import absolute_import, print_function
import asyncio
import datetime
import functools
import glob
import logging
import math
import os
import random
import re
import sys

import aiohttp
import discord
import yaml
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper
import youtube_dl

import dice.exc
import dice.tbl
import dice.util


MAX_DIE_STR = 20
OP_DICT = {
    '__add__': '+',
    '__sub__': '-',
    '+': '__add__',
    '-': '__sub__',
}
TIMERS = {}
TIMER_OFFSETS = ["60:00", "15:00", "5:00", "1:00"]
TIMER_MSG_TEMPLATE = "{}: Timer '{}'"
TIMERS_MSG = """
Timer #{} with description: **{}**
    __Started at__: {} UTC
    __Ends at__: {} UTC
    __Time remaining__: {}
"""
MUSIC_PATH = "extras/music"
PONI_URL = "https://derpibooru.org/search.json?q="
SONG_DB_FILE = os.path.abspath(os.path.join("data", "songs.yml"))
SONG_TAGS_FILE = os.path.abspath(os.path.join("data", "song_tags.yml"))
SONG_FMT = """      __Song {}__: {name}
      __URL__: <{url}>
      __Tags__: {tags}

"""
SONG_FOOTER = """Type __done__ or __stop__ to cancel.
Type __next__ to display the next page of entries.
Type __play 1__ to play entry 1.
"""
SONG_PAGE_LIMIT = 10


async def bot_shutdown(bot, sleep_time=30):  # pragma: no cover
    """
    Shutdown the bot. Not ideal, I should reconsider later.
    """
    await asyncio.sleep(sleep_time)
    await bot.logout()
    await asyncio.sleep(3)
    sys.exit(0)


class Action(object):
    """
    Top level action, contains shared logic.
    """
    def __init__(self, **kwargs):
        self.args = kwargs['args']
        self.bot = kwargs['bot']
        self.msg = kwargs['msg']
        self.log = logging.getLogger('dice.actions')

    async def execute(self):
        """
        Take steps to accomplish requested action, including possibly
        invoking and scheduling other actions.
        """
        raise NotImplementedError


class Help(Action):
    """
    Provide an overview of help.
    """
    async def execute(self):
        prefix = self.bot.prefix
        over = [
            'Here is an overview of my commands.',
            '',
            'For more information do: `{}Command -h`'.format(prefix),
            '       Example: `{}drop -h`'.format(prefix),
            '',
        ]
        lines = [
            ['Command', 'Effect'],
            ['{prefix}math', 'Do some math operations'],
            ['{prefix}m', 'Alias for `!math`'],
            ['{prefix}poni', 'Pony?!?!'],
            ['{prefix}roll', 'Roll a dice like: 2d6 + 5'],
            ['{prefix}r', 'Alias for `!roll`'],
            ['{prefix}songs', 'Create manage song lookup.'],
            ['{prefix}status', 'Show status of bot including uptime'],
            ['{prefix}timer', 'Set a timer for HH:MM:SS in future'],
            ['{prefix}timers', 'See the status of all YOUR active timers'],
            ['{prefix}help', 'This help message'],
        ]
        lines = [[line[0].format(prefix=prefix), line[1]] for line in lines]

        response = '\n'.join(over) + dice.tbl.wrap_markdown(dice.tbl.format_table(lines, header=True))
        await self.bot.send_ttl_message(self.msg.channel, response)
        try:
            await self.bot.delete_message(self.msg)
        except discord.Forbidden as exc:
            self.log.error("Failed to delete msg on: {}/{}\n{}".format(
                           self.msg.channel.server, self.msg.channel, exc))


class Status(Action):
    """
    Display the status of this bot.
    """
    async def execute(self):
        lines = [
            ['Created By', 'GearsandCogs'],
            ['Uptime', self.bot.uptime],
            ['Version', '{}'.format(dice.__version__)],
        ]

        await self.bot.send_message(self.msg.channel,
                                    dice.tbl.wrap_markdown(dice.tbl.format_table(lines)))


class Math(Action):
    """
    Perform one or more math operations.
    """
    async def execute(self):
        resp = ['__Math Calculations__', '']
        for line in ' '.join(self.args.spec).split(','):
            line = line.strip()
            if re.match(r'[^0-9 \(\)+-/*]', line):
                resp += ["'{}' looks suspicious. Allowed characters: 0-9 ()+-/*".format(line)]
                continue

            # FIXME: Dangerous, but re blocking anything not simple maths.
            resp += [line + " = " + str(eval(line))]

        await self.bot.send_message(self.msg.channel, '\n'.join(resp))


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
        self.loop = False
        self.state = MPlayerState.STOPPED

        self.__error_channel = None
        # Parts of the discord library wrapped
        self.__voice = None
        self.__player = None

    def __repr__(self):
        return "MPlayer(bot={}, channel={}, error_channel={}, voice={}, player={},"\
            " vids={}, vid_index={}, loop={}, state={})".format(
                self.bot, self.channel, self.__error_channel, self.__voice, self.__player,
                self.vids, self.vid_index, self.loop, self.state
            )

    def initialize_settings(self, msg, args):
        """
        Update current set videos and join requesting user in voice.
        """
        self.channel = msg.author.voice.voice_channel
        self.__error_channel = msg.channel
        if not self.channel:
            self.channel = discord.utils.get(msg.server.channels,
                                             type=discord.ChannelType.voice)

        self.loop = args.loop
        self.vids = validate_videos(args.vids)

    async def update_voice_channel(self):
        """
        Join the right channel before beginning transmission.
        """
        if self.__voice:
            if self.channel != self.__voice.channel:
                await self.__voice.move_to(self.channel)
        else:
            self.__voice = await self.bot.join_voice_channel(self.channel)

    def set_volume(self, new_volume):
        if new_volume < 1 or new_volume > 100:
            raise dice.exc.InvalidCommandArgs("Volume must be between [1, 100]")
        if not self.__player:
            raise dice.exc.InvalidCommandArgs("Volume can only be modified once player started.")
        self.__player.volume = new_volume / 100

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
        if "youtu" in vid:
            self.__player = await self.__voice.create_ytdl_player(vid)
        else:
            self.__player = self.__voice.create_ffmpeg_player(vid)
        self.__player.start()
        self.state = MPlayerState.PLAYING

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

    def prev(self):
        """
        Go to the previous song.
        """
        if self.__player and len(self.vids) > 1:
            if self.loop and self.vid_index > 0:
                self.vid_index = (self.vid_index - 1) % len(self.vids)
                asyncio.ensure_future(self.start())
            else:
                self.vid_index = 0
                self.stop()
                raise dice.exc.InvalidCommandArgs("Loop is not set, queue finished. Stopping.")

    def next(self):
        """
        Go to the next song.
        """
        if self.__player and len(self.vids) > 1:
            if self.loop or self.vid_index + 1 < len(self.vids):
                self.vid_index = (self.vid_index + 1) % len(self.vids)
                asyncio.ensure_future(self.start())
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
                    self.next()

                if (datetime.datetime.utcnow() - last_activity).seconds > 300:
                    await self.quit()
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
            except AttributeError:
                pass

            await asyncio.sleep(sleep_time)


# TODO: Handle possible paging of tags/songs here.
class Play(Action):
    """
    Transparent mapper from actions onto the mplayer.
    """
    async def select_song(self, song_db, tag_db, songs):
        #  songs = sorted(songs, key=lambda x, y: x['name'] < y['name'])
        song_msg = format_song_list('Choose from the following songs...\n\n',
                                    songs, SONG_FOOTER, cnt=1)
        song_msg += 'Type __back__ to return to tags.'

        while True:
            try:
                messages = [await self.bot.send_message(self.msg.channel, song_msg)]
                user_select = await self.bot.wait_for_message(timeout=30, author=self.msg.author,
                                                              channel=self.msg.channel)

                if user_select:
                    messages += [user_select]
                    user_select.content = user_select.content.lower().strip()

                if not user_select \
                        or user_select.content == 'done' \
                        or user_select.content == 'stop':
                    break

                elif user_select.content == 'back':
                    asyncio.ensure_future(self.select_tag(song_db, tag_db))
                    return

                else:
                    choice = int(user_select.content.replace('play ', '')) - 1
                    if choice < 0 or choice >= len(tag_db):
                        raise dice.exc.InvalidCommandArgs('Please select choice in [1, {}]'.format(len(tag_db)))

                    self.args.loop = True
                    self.args.vids = [songs[choice]['url']]
                    self.bot.mplayer.initialize_settings(self.msg, self.args)
                    await self.bot.mplayer.start()
                    await self.bot.send_message(self.msg.channel, 'Song "{}" sent to player.'.format(songs[choice]['name']))
                    return
            except ValueError:
                await self.bot.send_message(self.msg.channel, 'Did not undertand play selection.')
            finally:
                user_select = None
                asyncio.ensure_future(self.bot.delete_messages(messages))

        await self.bot.send_message(self.msg.channel, 'Play db terminated.')

    async def select_tag(self, song_db, tag_db):
        """
        Use the Songs db to lookup dynamically based on tags.
        """
        tag_msg = 'Select one of the following tags by number to explore:\n\n'
        tag_list = sorted(list(tag_db.keys()))
        for ind, tag in enumerate(tag_list, start=1):
            tag_msg += '        **{}**) {} ({} songs)\n'.format(ind, tag, len(tag_db[tag]))
        tag_msg += SONG_FOOTER

        while True:
            try:
                print(tag_msg)
                messages = [await self.bot.send_message(self.msg.channel, tag_msg)]
                user_select = await self.bot.wait_for_message(timeout=30, author=self.msg.author,
                                                              channel=self.msg.channel)

                if user_select:
                    messages += [user_select]
                    user_select.content = user_select.content.lower().strip()

                if not user_select \
                        or user_select.content == 'done' \
                        or user_select.content == 'stop':
                    break

                #  elif user_select.content == 'next':
                    #  entries = entries[SONG_PAGE_LIMIT:]
                    #  num_entries = len(entries[:SONG_PAGE_LIMIT])
                    #  page += 1
                    #  cnt += SONG_PAGE_LIMIT
                    #  reply = format_song_list('**__Songs DB__** Page {}\n\n'.format(page),
                                                #  entries[:SONG_PAGE_LIMIT], SONG_FOOTER, cnt=cnt)

                else:
                    choice = int(user_select.content) - 1
                    if choice < 0 or choice >= len(tag_db):
                        await self.bot.send_message(self.msg.channel,
                        'Please select choice in [1, {}]'.format(len(tag_db)))
                        continue

                    songs = [song_db[x] for x in tag_db[tag_list[choice]]]
                    asyncio.ensure_future(self.select_song(song_db, tag_db, songs))
                    return
            except ValueError:
                await self.bot.send_message(self.msg.channel, 'Did not undertand play selection.')
            finally:
                user_select = None
                asyncio.ensure_future(self.bot.delete_messages(messages))

        await self.bot.send_message(self.msg.channel, 'Play db terminated.')

    async def execute(self):
        mplayer = self.bot.mplayer
        new_vids = validate_videos(self.args.vids)

        if self.args.stop:
            mplayer.stop()
        elif self.args.pause:
            mplayer.pause()
        elif self.args.next:
            mplayer.next()
        elif self.args.prev:
            mplayer.prev()
        elif self.args.volume:
            mplayer.set_volume(self.args.volume)
        elif self.args.append:
            mplayer.vids += new_vids
        elif self.args.loop:
            mplayer.loop = not mplayer.loop
        elif self.args.db:
            songs = Songs(args=self.args, msg=self.msg, bot=self.bot)
            songs.load()
            await self.select_tag(songs.song_db, songs.tag_db)
        else:
            if new_vids:
                # New videos played so replace playlist
                mplayer.initialize_settings(self.msg, self.args)
            await mplayer.start()


def format_song_list(header, entries, footer, *, cnt=1):
    """
    Generate the management list of entries.
    """
    msg = header
    for ent in entries:
        msg += SONG_FMT.format(cnt, **ent)
        cnt += 1
    msg += footer

    return msg


# TODO: Deduplicate code in 'management interface', make reusable.
# TODO: Need tests here
class Songs(Action):
    """
    Songs command, manages an internal database of songs to play.
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.song_db = {}
        self.tag_db = {}

        self.load()
        self.save()

    def load(self):
        """
        Load the song dbs from files.
        """
        try:
            with open(SONG_DB_FILE) as fin:
                self.song_db = yaml.load(fin, Loader=Loader)
        except FileNotFoundError:
            self.song_db = {}
        try:
            with open(SONG_TAGS_FILE) as fin:
                self.tag_db = yaml.load(fin, Loader=Loader)
        except FileNotFoundError:
            self.tag_db = {}

    def save(self):
        """
        Save the song dbs to files.
        """
        with open(SONG_DB_FILE, 'w') as fout:
            yaml.dump(self.song_db, fout, Dumper=Dumper, encoding='UTF-8', indent=2,
                      explicit_start=True, default_flow_style=False)
        with open(SONG_TAGS_FILE, 'w') as fout:
            yaml.dump(self.tag_db, fout, Dumper=Dumper, encoding='UTF-8', indent=2,
                      explicit_start=True, default_flow_style=False)

    def add(self, key, url, tags):
        """
        Add a song entry to the database and tags files.
        """
        if key in self.song_db:
            self.remove(key)

        self.song_db[key] = {
            'name': key,
            'url': url,
            'tags': tags,
        }
        for tag in tags:
            try:
                self.tag_db[tag] = sorted(list(set(self.tag_db[tag] + [key])))
            except KeyError:
                self.tag_db[tag] = [key]

        self.save()

    def remove(self, key):
        """
        Remove an entry based on its key in the songs file.
        """
        for tag in self.song_db[key]['tags']:
            try:
                self.tag_db[tag].remove(key)
            except (KeyError, ValueError):
                pass

            if not self.tag_db[tag]:
                del self.tag_db[tag]

        try:
            del self.song_db[key]
        except KeyError:
            pass

        self.save()

    async def list(self):
        """
        List all entries in the song db. Implements a paging like interface.
        """
        cnt, page = 1, 1
        entries = sorted(list(self.song_db.values()), key=lambda x: x['name'])
        num_entries = len(entries[:SONG_PAGE_LIMIT])
        reply = format_song_list('**__Songs DB__** Page {}\n\n'.format(page),
                                 entries[:SONG_PAGE_LIMIT], SONG_FOOTER, cnt=cnt)

        while entries:
            try:
                messages = [await self.bot.send_message(self.msg.channel, reply)]
                user_select = await self.bot.wait_for_message(timeout=30, author=self.msg.author,
                                                              channel=self.msg.channel)

                if user_select:
                    messages += [user_select]
                    user_select.content = user_select.content.lower().strip()

                if not user_select \
                        or user_select.content == 'done' \
                        or user_select.content == 'stop':
                    break

                elif 'play' in user_select.content:
                    choice = int(user_select.content.replace('play', '')) - 1
                    if choice < 0 or choice >= SONG_PAGE_LIMIT:
                        raise dice.exc.InvalidCommandArgs('Please select choice in [1, {}]'.format(num_entries))

                    self.args.loop = True
                    self.args.vids = [entries[choice]['url']]
                    self.bot.mplayer.initialize_settings(self.msg, self.args)
                    await self.bot.mplayer.start()
                    break

                elif user_select.content == 'next':
                    entries = entries[SONG_PAGE_LIMIT:]
                    num_entries = len(entries[:SONG_PAGE_LIMIT])
                    page += 1
                    cnt += SONG_PAGE_LIMIT
                    reply = format_song_list('**__Songs DB__** Page {}\n\n'.format(page),
                                             entries[:SONG_PAGE_LIMIT], SONG_FOOTER, cnt=cnt)
            except ValueError:
                await self.bot.send_message(self.msg.channel, 'Did not undertand play selection.')
            finally:
                user_select = None
                asyncio.ensure_future(self.bot.delete_messages(messages))

        await self.bot.send_message(self.msg.channel, 'List terminated.')

    async def manage(self):
        """
        Using paging interface similar to list, allow management of song db.
        """
        cnt = 1
        entries = sorted(list(self.song_db.values()), key=lambda x: x['name'])
        num_entries = len(entries[:SONG_PAGE_LIMIT])

        while entries:
            try:
                reply = format_song_list("Remove one of these songs? [1..{}]:\n".format(num_entries),
                                         entries[:SONG_PAGE_LIMIT], SONG_FOOTER, cnt=cnt)
                messages = [await self.bot.send_message(self.msg.channel, reply)]
                user_select = await self.bot.wait_for_message(timeout=30, author=self.msg.author,
                                                              channel=self.msg.channel)

                if user_select:
                    messages += [user_select]
                    user_select.content = user_select.content.lower().strip()

                if not user_select \
                        or user_select.content == 'done'\
                        or user_select.content == 'stop':
                    break

                elif user_select.content == 'next':
                    cnt += SONG_PAGE_LIMIT
                    entries = entries[SONG_PAGE_LIMIT:]
                    num_entries = len(entries[:SONG_PAGE_LIMIT])
                    continue

                else:
                    choice = int(user_select.content) - 1
                    if choice < 0 or choice >= SONG_PAGE_LIMIT:
                        raise ValueError

                    self.remove(entries[choice]['name'])
                    entries.remove(entries[choice])
            except (KeyError, ValueError):
                raise dice.exc.InvalidCommandArgs("Please check your usage.")
            finally:
                user_select = None
                asyncio.ensure_future(self.bot.delete_messages(messages))

        await self.bot.send_message(self.msg.channel, "Management terminated.")

    async def search_names(self, term):
        """
        Search for a name across key entries in the song db.
        """
        reply = '**__Songs DB__** - Searching Names for __{}__\n\n'.format(term)
        cnt = 1

        l_term = ' '.join(term).lower().strip()
        for key in self.song_db:
            if l_term in key:
                song = self.song_db[key]
                reply += SONG_FMT.format(cnt, **song)
                cnt += 1

        await self.bot.send_message(self.msg.channel, reply)

    async def search_tags(self, term):
        """
        Search loosely accross the tags.
        """
        reply = '**__Songs DB__** - Searching Tags for __{}__\n\n'.format(term)
        cnt = 1

        l_term = ' '.join(term).lower().strip()
        for key in self.tag_db:
            if l_term in key:
                reply += '__**{}**__\n'.format(key)
                for name_key in self.tag_db[key]:
                    ent = self.song_db[name_key]
                    reply += SONG_FMT.format(cnt, **ent)
                    cnt += 1
                reply += "\n"

        await self.bot.send_message(self.msg.channel, reply)

    async def execute(self):
        if self.args.add:
            msg = self.msg.content.replace(self.bot.prefix + 'songs --add', '')
            msg = msg.replace(self.bot.prefix + 'songs -a', '')
            parts = re.split(r'\s*,\s*', msg)
            parts = [part.strip() for part in parts]
            key, url, tags = parts[0].lower().strip(), parts[1], [x.lower().strip() for x in parts[2:]]
            self.add(key, url, tags)
        if self.args.list:
            await self.list()
        elif self.args.manage:
            await self.manage()
        elif self.args.search:
            await self.search_names(self.args.search)
        elif self.args.tag:
            await self.search_tags(self.args.tag)


class Poni(Action):
    """
    Poni command.
    """
    async def execute(self):
        msg = "No images found!"
        tags = re.split(r'\s*,\s*|\s*,|,s*', self.msg.content.replace(self.bot.prefix + 'poni ', ''))
        full_tag = "%2C+".join(tags + ["-nswf", "-suggestive"])
        full_tag = re.sub(r'\s', '+', full_tag)

        async with aiohttp.ClientSession() as session:
            async with session.get(PONI_URL + full_tag) as resp:
                resp_json = await resp.json()
                total_imgs = resp_json['total']

            if total_imgs:
                total_ind = random.randint(1, total_imgs)
                page_ind = math.ceil(total_ind / 15)
                img_ind = total_ind % 15 - 1

                async with session.get(PONI_URL + full_tag + '&page=' + str(page_ind)) as resp:
                    resp_json = await resp.json()
                    img_found = resp_json["search"][img_ind]["representations"]

                msg = 'https:' + img_found["full"]

        await self.bot.send_message(self.msg.channel, msg)


class Roll(Action):
    """
    Perform one or more rolls of dice according to spec.
    """
    async def execute(self):
        resp = ['__Dice Rolls__', '']

        for line in ' '.join(self.args.spec).split(','):
            line = line.strip()
            times = 1

            match = re.match(r'(\d+)\s*\*\s*\(?([0-9 +-d]*)\)?', line)
            if match:
                times, line = int(match.group(1)), match.group(2)

            throw = Throw(tokenize_dice_spec(line))
            for _ in range(times):
                resp += [line + " = {}".format(await throw.next(self.bot.loop))]

        await self.bot.send_message(self.msg.channel, '\n'.join(resp))


class Dice(object):
    """
    Overall interface for a dice.
    """
    def __init__(self, next_op=""):
        self.values = []
        self.next_op = next_op  # Either "__add__" or "__sub__"
        self.acu = ""  # Slot to accumulate text, used in reduction

    @property
    def num(self):
        """
        The sum of the dice roll(s) for the spec.
        """
        return functools.reduce(lambda x, y: x + y, self.values)

    @property
    def spec(self):
        """
        The specification of how to roll the dice.
        """
        return str(self)

    @property
    def trailing_op(self):
        return ' {} '.format(OP_DICT[self.next_op]) if self.next_op else ""

    def __str__(self):
        """
        The individual roles displayed in a string.
        """
        if len(self.values) > MAX_DIE_STR:
            line = "({}, ..., {})".format(self.values[0], self.values[-1])
        else:
            line = "({})".format(" + ".join([str(x) for x in self.values]))
        return line + self.trailing_op

    def __add__(self, other):
        """
        Add one dice to another dice. Always returns a FixedRoll (i.e. fixed Dice).
        """
        if not isinstance(other, Dice):
            raise ValueError("Can only add Dice")

        new_roll = FixedRoll(self.num + other.num, other.next_op)
        new_roll.acu = self.acu + str(other)
        return new_roll

    def __sub__(self, other):
        """
        Subtract one dice from another dice. Always returns a FixedRoll (i.e. fixed Dice).
        """
        if not isinstance(other, Dice):
            raise ValueError("Can only add Dice")

        new_roll = FixedRoll(self.num - other.num, other.next_op)
        new_roll.acu = self.acu + str(other)
        return new_roll

    def roll(self):
        """
        Perform the roll as specified.
        """
        raise NotImplementedError


class FixedRoll(Dice):
    """
    A fixed dice roll, always returns a constant number.
    """
    def __init__(self, num, next_op=""):
        super().__init__(next_op)
        self.values = [int(num)]
        self.dice = self.values[0]
        self.rolls = 1

    def roll(self):
        return self.num


class DiceRoll(Dice):
    """
    A standard dice roll. Roll rolls times a dice of any number of sides from [1, inf].
    """
    def __init__(self, spec, next_op=""):
        super().__init__(next_op)
        self.rolls, self.dice = parse_dice_spec(spec)

    @property
    def spec(self):
        return "({}d{})".format(self.rolls, self.dice)

    def roll(self):
        self.values = [random.randint(1, self.dice) for _ in range(self.rolls)]
        return self.num


class DiceRollKeepHigh(DiceRoll):
    """
    Same as a dice roll but only keep n high rolls.
    """
    def __init__(self, spec, next_op=""):
        super().__init__(spec[:spec.rindex('k')], next_op)
        self.keep = 1
        match = re.match(r'.*kh?(\d+)', spec)
        if match:
            self.keep = int(match.group(1))

    def __str__(self):
        if len(self.values) > MAX_DIE_STR:
            return "({}, ..., {})".format(self.values[0], self.values[-1]) + self.trailing_op

        emphasize = sorted(self.values)[:-self.keep]
        line = ''
        for val in self.values:
            if val in emphasize:
                emphasize.remove(val)
                val = "~~{}~~".format(val)
            line += "{} + ".format(val)

        return '(' + line[:-3] + ')' + self.trailing_op

    @property
    def spec(self):
        return "({}d{}kh{})".format(self.rolls, self.dice, self.keep)

    @property
    def num(self):
        vals = sorted(self.values)[-self.keep:]
        return functools.reduce(lambda x, y: x + y, vals)


class DiceRollKeepLow(DiceRoll):
    """
    Same as a dice roll but only keep n low rolls.
    """
    def __init__(self, spec, next_op=""):
        super().__init__(spec[:spec.rindex('kl')], next_op)
        self.keep = 1
        match = re.match(r'.*kl(\d+)', spec)
        if match:
            self.keep = int(match.group(1))

    def __str__(self):
        if len(self.values) > MAX_DIE_STR:
            return "({}, ..., {})".format(self.values[0], self.values[-1]) + self.trailing_op

        line = ''
        emphasize = sorted(self.values)[self.keep:]
        for val in self.values:
            if val in emphasize:
                emphasize.remove(val)
                val = "~~{}~~".format(val)
            line += "{} + ".format(val)

        return '(' + line[:-3] + ')' + self.trailing_op

    @property
    def spec(self):
        return "({}d{}kl{})".format(self.rolls, self.dice, self.keep)

    @property
    def num(self):
        vals = sorted(self.values)[:self.keep]
        return functools.reduce(lambda x, y: x + y, vals)


class Throw(object):
    """
    Throws 1 or more Dice. Acts as a simple container.
    Can be used primarily to reroll a complex dice setup.
    """
    def __init__(self, die=None):
        self.dice = die
        if not self.dice:
            self.dice = []

    def add_dice(self, die):
        """ Add one or more dice to be thrown. """
        self.dice += die

    async def next(self, loop):
        """ Throw the dice and return the individual rolls and total. """
        for die in self.dice:
            if die.rolls > 1000000:
                msg = "{} is excessive.\n\n\
I won't waste my otherworldly resources on it, insufferable mortal.".format(die.spec[1:-1])
                raise dice.exc.InvalidCommandArgs(msg)
            await loop.run_in_executor(None, die.roll)

        self.dice[0].acu = str(self.dice[0])
        tot = functools.reduce(lambda x, y: getattr(x, x.next_op)(y), self.dice)

        response = "{} = {}".format(tot.acu, tot.num)

        return response


class Timer(Action):
    """
    Allow users to set timers to remind them of things.
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        if not re.match(r'[0-9:]+', self.args.time) or self.args.time.count(':') > 2:
            raise dice.exc.InvalidCommandArgs("I can't understand time spec! Use format: **HH:MM:SS**")

        end_offset = parse_time_spec(self.args.time)
        self.start = datetime.datetime.utcnow()
        self.end = self.start + datetime.timedelta(seconds=end_offset)
        self.sent_msg = None
        self.triggers = self.calc_triggers(end_offset)
        self.cancel = False

        TIMERS[self.key] = self

    def __str__(self):
        msg = "Timer(start={}, end={}, cancel={}, sent_msg={}, triggers={})".format(
            self.start, self.end, self.cancel, self.sent_msg, str(self.triggers)
        )
        return msg

    @property
    def key(self):
        """
        Unique key to store timer.
        """
        return self.msg.author.name + str(self.start)

    @property
    def description(self):
        """
        Description associated with the timer.
        """
        try:
            description = self.msg.author.name + " " + self.args.time
        except AttributeError:
            description = "Default description"
        if isinstance(self.args.description, list):
            description = " ".join(self.args.description)

        return description

    def calc_triggers(self, end_offset):
        """
        Set the required trigger times and the associated messages to send.
        """
        msg = TIMER_MSG_TEMPLATE.format(self.msg.author.mention, self.description)

        if self.args.offsets is None:
            self.args.offsets = TIMER_OFFSETS
        offsets = sorted([-parse_time_spec(x) for x in self.args.offsets])
        offsets = [x for x in offsets if end_offset + x > 0]  # validate offsets applicable

        triggers = []
        for offset in offsets:
            trigger = self.end + datetime.timedelta(seconds=offset)
            triggers.append([trigger, msg + " has {} time remaining!".format(self.end - trigger)])

        triggers.append([self.end, msg + " has expired. Do something meatbag!"])

        return triggers

    async def check_timer(self, sleep_time=5):
        """
        Perform a check on the triggers of this timer.

        If a trigger has been reached, send the appropriate message back to channel.
        If no triggers left, stop scheduling a new check_timer invocation.

        Args:
            sleep_gap: The gap between checks on the timer.
        """
        del_cnt = 0
        now = datetime.datetime.utcnow()
        for trigger, msg in self.triggers:
            if now > trigger:
                if self.sent_msg:
                    try:
                        await self.bot.delete_message(self.sent_msg)
                    except discord.Forbidden as exc:
                        self.log.error("Failed to delete msg on: {}/{}\n{}".format(
                                       self.msg.channel.server, self.msg.channel, exc))
                self.sent_msg = await self.bot.send_message(self.msg.channel, msg)
                del_cnt += 1

        while del_cnt:
            del self.triggers[0]
            del_cnt -= 1

        if not self.cancel and self.triggers:
            await asyncio.sleep(sleep_time)
            asyncio.ensure_future(self.check_timer(sleep_time))
        else:
            del TIMERS[self.key]

    async def execute(self):
        self.sent_msg = await self.bot.send_message(self.msg.channel, "Starting timer for: " + self.args.time)
        await self.check_timer(1)


class Timers(Action):
    """
    Show a users own timers.
    """
    def timer_summary(self):
        msg = "The timers for {}:\n".format(self.msg.author.name)
        cnt = 1

        for key in TIMERS:
            if self.msg.author.name not in key or TIMERS[key].cancel:
                continue

            timer = TIMERS[key]
            trunc_start = timer.start.replace(microsecond=0)
            trunc_end = timer.end.replace(microsecond=0)
            diff = timer.end - datetime.datetime.utcnow()
            diff = diff - datetime.timedelta(microseconds=diff.microseconds)

            msg += TIMERS_MSG.format(cnt, timer.description, trunc_start, trunc_end, diff)
            cnt += 1

        if cnt == 1:
            msg += "**None**"

        return msg

    async def manage_timers(self):
        """
        Create a simple interactive menu to manage timers.
        """
        user_select = None
        user_timers = [x for x in TIMERS if self.msg.author.name in x]
        while True:
            try:
                reply = "Please select a timer to delete from below [1..{}]:\n".format(len(user_timers)) + self.timer_summary()
                reply += "\n\nWrite 'done' or 'stop' to finish."
                messages = [await self.bot.send_message(self.msg.channel, reply)]
                user_select = await self.bot.wait_for_message(timeout=30, author=self.msg.author,
                                                              channel=self.msg.channel)

                if user_select:
                    messages += [user_select]
                    user_select.content = user_select.content.lower().strip()

                if not user_select \
                        or user_select.content == 'done' \
                        or user_select.content == 'stop':
                    return

                choice = int(user_select.content) - 1
                if choice < 0 or choice >= len(user_timers):
                    raise ValueError

                for timer in TIMERS.values():
                    if timer.key == user_timers[choice]:
                        timer.cancel = True
                        del user_timers[choice]
                        break
            except (KeyError, ValueError):
                pass
            finally:
                user_select = None
                asyncio.ensure_future(self.bot.delete_messages(messages))

    async def execute(self):
        if self.args.clear:
            remove_user_timers(TIMERS, self.msg.author.name)
            return
        elif self.args.manage:
            await self.manage_timers()
            return

        await self.bot.send_message(self.msg.channel, self.timer_summary())


def parse_dice_spec(spec):
    """
    Parse a SINGLE dice spec of form 2d6.
    """
    terms = str(spec).lower().split('d')
    terms.reverse()

    if len(terms) < 1:
        raise dice.exc.InvalidCommandArgs("Cannot determine dice.")

    try:
        sides = int(terms[0])
        if sides < 1:
            raise dice.exc.InvalidCommandArgs("Invalid number for dice (d__6__). Number must be [1, +∞]")
        if terms[1] == '':
            rolls = 1
        else:
            rolls = int(terms[1])
            if rolls < 1:
                raise dice.exc.InvalidCommandArgs("Invalid number for rolls (__r__d6). Number must be [1, +∞] or blank (1).")
    except IndexError:
        rolls = 1
    except ValueError:
        raise dice.exc.InvalidCommandArgs("Invalid number for rolls or dice. Please clarify: " + spec)

    return (rolls, sides)


def parse_time_spec(time_spec):
    """
    Parse a simple time spec of form: [HH:[MM:[SS]]] into seconds.

    Raises:
        InvalidCommandArgs - Time spec could not be parsed.
    """
    secs = 0
    try:
        t_spec = time_spec.split(':')
        t_spec.reverse()
        secs += int(t_spec[0])
        secs += int(t_spec[1]) * 60
        secs += int(t_spec[2]) * 3600
    except (IndexError, ValueError):
        if secs == 0:
            raise dice.exc.InvalidCommandArgs("I can't understand time spec! Use format: **HH:MM:SS**")

    return secs


def remove_user_timers(timers, msg_author):
    """
    Purge all timers associated with msg_author.
    Youcan only purge your own timers.
    """
    for key_to_remove in [x for x in timers if msg_author in x]:
        timers[key_to_remove].cancel = True


def tokenize_dice_spec(spec):
    """
    Tokenize a single string into multiple Dice.
    String should be of form:

        4d6 + 10d6kh2 - 4
    """
    tokens = []
    spec = re.sub(r'([+-])', r' \1 ', spec.lower())
    for roll in re.split(r'\s+', spec):
        if roll in ['+', '-'] and tokens:
            tokens[-1].next_op = OP_DICT[roll]
            continue

        if 'kh' in roll and 'kl' in roll:
            raise dice.exc.InvalidCommandArgs("__kh__ and __kl__ are mutually exclusive. Pick one muppet!")
        elif 'kl' in roll:
            tokens += [DiceRollKeepLow(roll)]
            continue
        elif re.match(r'.*\dkh?', roll):
            tokens += [DiceRollKeepHigh(roll)]
            continue

        try:
            tokens += [FixedRoll(int(roll))]
        except ValueError:
            tokens += [DiceRoll(roll)]

    return tokens


def validate_videos(list_vids):
    """
    Validate the youtube links or local files.

    Raises:
        InvalidCommandArgs - A video link or name failed validation.
    """
    new_vids = []

    for vid in list_vids:
        if "/" in vid:
            if "youtube.com" in vid or "youtu.be" in vid:
                if vid[0] == "<" and vid[-1] == ">":
                    vid = vid[1:-1]
                new_vids.append(vid)
            else:
                raise dice.exc.InvalidCommandArgs("Only youtube links supported: " + vid)
        else:
            globbed = glob.glob(os.path.join(MUSIC_PATH, vid + "*"))
            if len(globbed) != 1:
                raise dice.exc.InvalidCommandArgs("Cannot find local video: " + vid)
            new_vids.append(globbed[0])

    return new_vids
