"""
To facilitate complex actions based on commands create a
hierarchy of actions that can be recombined in any order.
All actions have async execute methods.
"""
from __future__ import absolute_import, print_function
import asyncio
import concurrent.futures
import datetime
import inspect
import logging
import math
import re

import aiohttp
import discord
import numpy.random as rand

import dice.exc
import dice.roll
import dice.tbl
import dice.turn
import dice.util
from dice.music import GuildPlayer

import dicedb
import dicedb.query

CHECK_TIMER_GAP = 5
TIMERS = {}
TIMER_OFFSETS = ["60:00", "15:00", "5:00", "1:00"]
PF_URL = 'https://cse.google.com/cse?cx=006680642033474972217%3A6zo0hx_wle8&q={}'
D5_URL = 'https://cse.google.com/cse?cx=006680642033474972217%3A1xq0zf2wtvq&q={}'
STAR_URL = 'https://cse.google.com/cse?cx=006680642033474972217%3Awyjvzq2cjz8&q={}'
PONI_URL = "https://derpibooru.org/search.json?q="
LIMIT_SONGS = 8
LIMIT_TAGS = 16
PLAYERS = {}


class Action():
    """
    Top level action, contains shared logic.
    """
    def __init__(self, **kwargs):
        self.args = kwargs['args']
        self.bot = kwargs['bot']
        self.msg = kwargs['msg']
        self.log = logging.getLogger('dice.actions')
        self.session = dicedb.Session()

    @property
    def chan_id(self):
        """
        An id representing the originating channel.
        """
        return '{}_{}'.format(self.msg.guild.id, self.msg.channel.id)

    @property
    def guild_id(self):
        """
        An id representing the guild.
        """
        return self.msg.guild.id

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
            ['{prefix}d5', 'Search on the D&D 5e wiki'],
            ['{prefix}effect', 'Add an effect to a user in turn order'],
            ['{prefix}e', 'Alias for `!effect`'],
            ['{prefix}math', 'Do some math operations'],
            ['{prefix}music', 'Play songs from youtube and server.'],
            ['{prefix}m', 'Alias for `!music`'],
            ['{prefix}n', 'Alias for `!turn --next`'],
            ['{prefix}pf', 'Search on the Pathfinder wiki'],
            ['{prefix}poni', 'Pony?!?!'],
            ['{prefix}pun', 'Prepare for pain!'],
            ['{prefix}roll', 'Roll a dice like: 2d6 + 5'],
            ['{prefix}r', 'Alias for `!roll`'],
            ['{prefix}songs', 'Create manage song lookup.'],
            ['{prefix}star', 'Search on the Starfinder wiki.'],
            ['{prefix}status', 'Show status of bot including uptime'],
            ['{prefix}timer', 'Set a timer for HH:MM:SS in future'],
            ['{prefix}timers', 'See the status of all YOUR active timers'],
            ['{prefix}turn', 'Manager turn order for pen and paper combat'],
            ['{prefix}help', 'This help message'],
        ]
        lines = [[line[0].format(prefix=prefix), line[1]] for line in lines]

        response = '\n'.join(over) + dice.tbl.wrap_markdown(dice.tbl.format_table(lines, header=True))
        await self.bot.send_ttl_message(self.msg.channel, response)
        try:
            await self.msg.delete()
        except discord.Forbidden as exc:
            self.log.error("Failed to delete msg on: %s/%s\n%s",
                           self.msg.channel.guild, self.msg.channel, str(exc))


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


class Music(Action):
    """
    Transparent mapper from user input onto the music player.
    """
    @staticmethod
    async def make_videos(arg_vids):
        """
        Preprocess the arguments and return a list of valid videos
        the player can handle.

        Args:
            arg_vids: The args.vids list of arguments from user.

        Returns:
            A list of valid Song objects that can be played.
        """
        parts = [part.strip() for part in re.split(r'\s*,\s*', ' '.join(arg_vids))]

        if dice.util.is_valid_playlist(parts[0]):
            vid_info = await dice.music.get_yt_info(parts[0])
            new_vids = dicedb.query.validate_videos([x[0] for x in vid_info])
            for vid in new_vids:
                _, title = vid_info[0]
                vid_info = vid_info[1:]
                vid.name = title[:30]
        else:
            new_vids = dicedb.query.validate_videos(parts)

        return new_vids

    async def clear(self, mplayer):
        mplayer.stop()
        mplayer.set_vids([])

    async def restart(self, mplayer):
        """ Restart the player at the beginning. """
        mplayer.reset_iterator()
        await mplayer.play_when_ready()
        return "__**Now Playing**__\n\n{}".format(mplayer.cur_vid)

    async def stop(self, mplayer):
        """ Stop the player. """
        await mplayer.disconnect()
        return "Player has been stopped.\n\nRestart it or play other vids to continue."

    async def pause(self, mplayer):
        """ Pause the player. """
        mplayer.toggle_pause()
        return"Player is now: " + mplayer.state

    async def next(self, mplayer):
        """ Play the next video. """
        if mplayer.next():
            await mplayer.play_when_ready()
        return "__**Now Playing**__\n\n{}".format(mplayer.cur_vid)

    async def prev(self, mplayer):
        """ Play the previous video. """
        if mplayer.prev():
            await mplayer.play_when_ready()
        return "__**Now Playing**__\n\n{}".format(mplayer.cur_vid)

    async def repeatqueue(self, mplayer):
        """ Set player to loop to beginning. """
        mplayer.repeat_all = not mplayer.repeat_all
        msg = "Player will stop playing after last song in list."
        if mplayer.repeat_all:
            msg = "Player will return to and play first song after finishing list."

        return msg

    async def repeat(self, mplayer):
        """ Set player to repeat video when it finishes normally. """
        mplayer.cur_vid.repeat = not mplayer.cur_vid.repeat
        msg = "Current video {} will **NO** longer repeat.".format(mplayer.cur_vid.name)
        if mplayer.cur_vid.repeat:
            msg = "Current video {} **will** repeat.\n\nAdvance list with '--next'.".format(mplayer.cur_vid.name)

        return msg

    async def shuffle(self, mplayer):
        """ Set player to repeat video when it finishes normally. """
        mplayer.toggle_shuffle()
        await mplayer.play_when_ready()
        return "Player shuffle is now: **{}abled**".format('En' if mplayer.shuffle else 'Dis')

    async def status(self, mplayer):
        """ Show current bot status. """
        return str(mplayer)

    async def volume(self, mplayer):
        """ Set the volume for current song. """
        mplayer.set_volume(self.args.volume)
        msg = "Player volume: {}/100".format(mplayer.cur_vid.volume_int)
        await self.bot.send_message(self.msg.channel, msg)

    async def append(self, mplayer):
        """ Append to the end of the queue. """
        new_vids = await self.__class__.make_videos(self.args.vids)
        mplayer.append_vids(new_vids)
        await dice.music.prefetch_in_order(new_vids)
        await self.bot.send_message(self.msg.channel, str(mplayer))

    async def play(self, mplayer):
        """ Start playing or replace entire playlist. """
        new_vids = await self.__class__.make_videos(self.args.vids)
        msg = await self.bot.send_message(self.msg.channel, "Please wait, ensuring first song downloaded. Rest will download in background.")
        await dice.music.prefetch_all(new_vids[:1])
        mplayer.set_vids(new_vids)
        mplayer.play()
        try:
            await msg.delete()
        except discord.Forbidden:
            pass

        await self.bot.send_message(self.msg.channel, str(mplayer))
        await dice.music.prefetch_in_order(new_vids[1:])

    async def execute(self):
        mplayer = get_guild_player(self.guild_id, self.msg)
        await mplayer.join_voice_channel()

        if not getattr(self.args, 'sub'):
            self.args.sub = 'status'

        try:
            msg = await getattr(self, self.args.sub)(mplayer)
        except dice.exc.RemoteError as exc:
            msg = str(exc)
        if msg:
            await self.bot.send_long_message(self.msg.channel, msg)

        if mplayer.cur_vid.id and self.args.sub in ['repeat', 'volume']:
            song = dicedb.query.get_song_by_id(self.session, mplayer.cur_vid.id)
            song.update(mplayer.cur_vid)
            self.session.add(song)
            self.session.commit()


class SongRemoval(dice.util.PagingMenu):
    """
    Generate the management interface for removing songs from db.
    """
    def menu(self):
        header = """**Remove Songs**
Page {}/{}
Select a song to remove by number [1..{}]:

""".format(self.page, self.total_pages, len(self.cur_entries))
        return format_song_list(header, self.cur_entries, dice.util.PAGING_FOOTER)

    async def handle_msg(self, user_select):
        choice = int(user_select.content) - 1
        if choice < 0 or choice >= len(self.cur_entries):
            raise ValueError

        dicedb.query.remove_song_with_tags(self.act.session, self.entries[choice].name)
        del self.entries[choice]
        await self.send("**Song Deleted**\n\n    {}".format(self.entries[choice].name))

        return False


class SelectTag(dice.util.PagingMenu):
    """
    Select a tag to play all songs with tag or fursther select a single song from.
    """
    def menu(self):
        menu = """**Select A Tag**
Page {}/{}
Select a tag from blow to play or explore further:

""".format(self.page, self.total_pages, len(self.cur_entries))
        for ind, tag in enumerate(self.cur_entries, start=1):
            tagged_songs = dicedb.query.get_songs_with_tag(self.act.session, tag)
            menu += '        **{}**) {} ({} songs)\n'.format(ind, tag, len(tagged_songs))
        menu = menu.rstrip() + dice.util.PAGING_FOOTER
        menu += """Type __all 1__ to play all songs with tag 1
Type __list__ to go select by song list"""

        return menu

    async def handle_msg(self, user_select):
        if user_select.content == 'list':
            entries = dicedb.query.get_song_choices(self.act.session)
            asyncio.ensure_future(SelectSong(self.act, entries).run())
            return True

        choice = int(user_select.content.replace('all', '')) - 1
        if choice < 0 or choice >= len(self.cur_entries):
            raise ValueError

        songs = dicedb.query.get_songs_with_tag(self.act.session, self.cur_entries[choice])
        if 'all' in user_select.content:
            mplayer = get_guild_player(self.act.guild_id, self.msg)
            self.msgs += [await self.send('Please wait, downloading as needed before playing.')]
            await mplayer.replace_and_play(songs)
            await self.send(str(mplayer))
        else:
            await SelectSong(self.act, songs).run()

        return True


class SelectSong(dice.util.PagingMenu):
    """
    Select a song from a list of tags provided.
    """
    def menu(self):
        header = """**Select A Song**
Page {}/{}
Select a song to play by number [1..{}]:

""".format(self.page, self.total_pages, len(self.cur_entries))
        menu = format_song_list(header, self.cur_entries, dice.util.PAGING_FOOTER)
        menu += 'Type __tags__ to go select by tags'

        return menu

    async def handle_msg(self, user_select):
        if user_select.content == 'tags':
            entries = dicedb.query.get_tag_choices(self.act.session)
            asyncio.ensure_future(SelectTag(self.act, entries, LIMIT_TAGS).run())
            return True

        choice = int(user_select.content) - 1
        if choice < 0 or choice >= len(self.cur_entries):
            raise ValueError
        selected = self.entries[choice]

        self.msgs += [await self.send('Appending new selection to playlist. Select another or exit.')]
        await get_guild_player(self.act.guild_id).append_vids([selected])
        await dice.music.prefetch_all([selected])
        await self.send('**Song Started**\n\n' + str(selected))

        return True


# TODO: Need tests here
class Songs(Action):
    """
    Songs command, manages an internal database of songs to play.
    """
    def add(self, name, url, tags):
        """
        Add a song entry to the database and tags files.
        """
        return dicedb.query.add_song_with_tags(self.session, name, url, tags)

    def remove(self, name):
        """
        Remove an entry based on its key in the songs file.
        """
        dicedb.query.remove_song_with_tags(self.session, name)

    async def list(self):
        """
        List all entries in the song db. Implements a paging like interface.
        """
        entries = dicedb.query.get_song_choices(self.session)
        await SelectSong(self, entries, LIMIT_SONGS).run()

    async def manage(self):
        """
        Using paging interface similar to list, allow management of song db.
        """
        entries = dicedb.query.get_song_choices(self.session)
        await SongRemoval(self, entries, LIMIT_SONGS).run()

    async def select_tag(self):
        """
        Use the Songs db to lookup dynamically based on tags.
        """
        entries = dicedb.query.get_tag_choices(self.session)
        await SelectTag(self, entries, LIMIT_TAGS).run()

    async def search_names(self, term):
        """
        Search for a name across key entries in the song db.
        """
        reply = '**__Songs DB__** - Searching Names for __{}__\n\n'.format(term)
        cnt = 1

        l_term = ' '.join(term).lower().strip()
        for song in dicedb.query.search_songs_by_name(dicedb.Session(), l_term):
            reply += song.format_menu(cnt)
            cnt += 1

        await self.bot.send_long_message(self.msg.channel, reply)

    async def search_tags(self, term):
        """
        Search loosely accross the tags.
        """
        reply = '**__Songs DB__** - Searching Tags for __{}__\n\n'.format(term)
        cnt = 1

        session = dicedb.Session()
        l_term = ' '.join(term).lower().strip()
        for tag in dicedb.query.get_tag_choices(session, l_term):
            reply += '__**{}**__\n'.format(tag)
            for song in dicedb.query.get_songs_with_tag(session, tag):
                reply += song.format_menu(cnt)
                cnt += 1
            reply += "\n"

        await self.bot.send_long_message(self.msg.channel, reply)

    async def execute(self):
        if self.args.add:
            msg = self.msg.content.replace(self.bot.prefix + 'songs --add', '')
            msg = msg.replace(self.bot.prefix + 'songs -a', '')
            parts = re.split(r'\s*,\s*', msg)
            parts = [part.strip() for part in parts]
            name, url, tags = parts[0].lower(), parts[1], [x.lower() for x in parts[2:]]
            song = self.add(name, url, tags)

            reply = '__Song Added__\n\n' + song.format_menu(1)
            await self.bot.send_message(self.msg.channel, reply)
        if self.args.list:
            await self.list()
        elif self.args.manage:
            await self.manage()
        elif self.args.play:
            await self.select_tag()
        elif self.args.search:
            await self.search_names(self.args.search)
        elif self.args.tag:
            await self.search_tags(self.args.tag)


class SearchWiki(Action):
    """
    Search an OGN wiki site based on their google custom search URL.
    """
    async def execute(self):
        msg = """Searching {}: **{}**
Top {} Results:\n\n{}"""
        terms = ' '.join(self.args.terms)
        match = re.match(r'.*?([^a-zA-Z0-9 -]+)', terms)
        if match:
            raise dice.exc.InvalidCommandArgs('No special characters in search please. ' + match.group(1))

        base_url = getattr(dice.actions, self.args.url)
        full_url = base_url.format(terms.replace(' ', '%20'))
        with concurrent.futures.ProcessPoolExecutor(1) as pool:
            result = await self.bot.loop.run_in_executor(pool, get_results_in_background,
                                                         full_url, self.args.num)

        await self.bot.send_message(self.msg.channel, msg.format(
            self.args.wiki, terms, self.args.num, result))


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

            if total_imgs == 1:
                page_ind, img_ind = 1, 1
            elif total_imgs:
                total_ind = rand.randint(1, total_imgs)
                page_ind = math.ceil(total_ind / 15)
                img_ind = total_ind % 15 - 1

            if total_imgs:
                async with session.get(PONI_URL + full_tag + '&page=' + str(page_ind)) as resp:
                    resp_json = await resp.json()
                    img_found = resp_json["search"][img_ind - 1]["representations"]

                msg = 'https:' + img_found["full"]

        await self.bot.send_message(self.msg.channel, msg)


class Roll(Action):
    """
    Perform one or more rolls of dice according to spec.
    """
    async def make_rolls(self, spec):
        """
        Take a specification of dice rolls and return a string.
        """
        lines = []

        for line in spec.split(','):
            line = line.strip()
            times = 1

            if ':' in line:
                parts = line.split(':')
                times, line = int(parts[0]), parts[1].strip()

            throw = dice.roll.Throw(dice.roll.tokenize_dice_spec(line))
            with concurrent.futures.ProcessPoolExecutor() as pool:
                for _ in range(times):
                    lines += [line + " = {}".format(await self.bot.loop.run_in_executor(pool, throw_in_pool, throw))]

        return lines

    async def execute(self):
        full_spec = ' '.join(self.args.spec).strip()
        user_id = self.msg.author.id
        msg = ''

        if self.args.save:
            duser = dicedb.query.ensure_duser(self.session, self.msg.author)
            roll = dicedb.query.update_saved_roll(self.session, str(duser.id), self.args.save, full_spec)

            msg = 'Added roll: __**{}**__: {}'.format(roll.name, roll.roll_str)

        elif self.args.list:
            rolls = dicedb.query.find_all_saved_rolls(self.session, user_id)
            resp = ['__**Saved Rolls**__:', '']
            resp += ['__{}__: {}'.format(roll.name, roll.roll_str) for roll in rolls]

            msg = '\n'.join(resp)

        elif self.args.remove:
            roll = dicedb.query.remove_saved_roll(self.session, user_id, self.args.remove)

            msg = 'Removed roll: __**{}**__: {}'.format(roll.name, roll.roll_str)

        else:
            try:
                if full_spec == '':
                    raise dice.exc.InvalidCommandArgs('A roll requires some text!')

                saved_roll = dicedb.query.find_saved_roll(self.session, user_id, full_spec)
                full_spec = saved_roll.roll_str
                resp = ['__Dice Rolls__ ({})'.format(saved_roll.name), '']
            except dice.exc.NoMatch:
                resp = ['__Dice Rolls__', '']

            resp += await self.make_rolls(full_spec)
            msg = '\n'.join(resp)

        await self.bot.send_long_message(self.msg.channel, msg)


class Timer(Action):
    """
    Allow users to set timers to remind them of things.
    Users can override the warning times and set a descritpion for the timer.

    Attributes:
        last_msg: The last message sent to user, None if no message has been sent.
        start: The datetime when the Timer started.
        end: The datetime when the Timer will be finished.
        triggers: A series of tuples like (datetime, msg_for_user).
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        if not re.match(r'[0-9:]+', self.args.time) or self.args.time.count(':') > 2:
            raise dice.exc.InvalidCommandArgs("I can't understand time spec! Use format: **HH:MM:SS**")

        self.last_msg = None
        end_offset = parse_time_spec(self.args.time)
        self.start = datetime.datetime.utcnow()
        self.end = self.start + datetime.timedelta(seconds=end_offset)
        self.triggers = self.calc_triggers(end_offset)

    def __str__(self):
        """ Provide a friendly summary for users. """
        diff = self.end - datetime.datetime.utcnow()
        diff = diff - datetime.timedelta(microseconds=diff.microseconds)

        return """{desc}
        __Started__ {start}
        __Ends at__  {end}
        __Remaining__ {remain}
        """.format(desc=self.description,
                   start=self.start.replace(microsecond=0),
                   end=self.end.replace(microsecond=0),
                   remain=diff)

    def __repr__(self):
        keys = ['description', 'start', 'end', 'last_msg', 'triggers']
        kwargs = ['{}={!r}'.format(key, getattr(self, key)) for key in keys]

        return "Timer({})".format(', '.join(kwargs))

    def __eq__(self, other):
        return self.key == other.key

    def __hash__(self):
        return hash(self.msg.author.name, str(self.start))

    @property
    def key(self):
        """
        Unique key to identify the timer.
        """
        return self.msg.author.name + '_' + str(self.start)

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

    def is_expired(self):
        """ The timer has expired. """
        return datetime.datetime.utcnow() > self.end

    def calc_triggers(self, end_offset):
        """
        Calculate the absolute times when the offset warnings from start will be passed.
        Each calculated trigger either warns about time remaining or informs user
        the timer has finished.

        Args:
            end_offset: The offset from start that the timer will end at.

        Returns:
            A list of the form:
                [[trigger_date, msg_to_user], [trigger_date, msg_to_user], ...]
        """
        msg = "{}: Timer '{}'".format(self.msg.author.mention, self.description)

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

    def check_triggers(self):
        """
        Check the timer for having passed any triggers for warnings
        or even expired entirely.

        Returns:
            The last relevant message about timer. None if nothing to report.
        """
        reply = None
        now = datetime.datetime.utcnow()

        del_cnt = 0
        for trigger, msg in self.triggers:
            if now > trigger:
                reply = msg
                del_cnt += 1

        self.triggers = self.triggers[del_cnt:]

        return reply

    async def update_notice(self, new_msg):
        """
        Send the latest warning notice to the user.
        If a previous message exists, attempt deletion first.

        Args:
            new_msg: The new message to send.
        """
        if self.last_msg:
            try:
                await self.last_msg.delete()
            except discord.Forbidden:
                logging.getLogger("dice.actions").error("Bot missing manage messages permission. On: %s", str(self.msg.guild))

        self.last_msg = await self.bot.send_message(self.msg.channel, new_msg)

    async def execute(self):
        TIMERS[self.key] = self
        self.last_msg = await self.bot.send_message(self.msg.channel, "Starting timer for: " + self.args.time)


class TimersMenu(dice.util.PagingMenu):
    """
    Manage the timers the user has active.
    """
    def menu(self):
        header = """**Timers Management**
Page {}/{}
Select a timer to cancel from [1..{}]:

""".format(self.page, self.total_pages, len(self.cur_entries))
        return header + timer_summary(TIMERS, self.msg.author.name) + dice.util.PAGING_FOOTER

    async def handle_msg(self, user_select):
        choice = int(user_select.content) - 1
        if choice < 0 or choice >= len(self.cur_entries):
            raise ValueError

        try:
            del TIMERS[self.entries[choice]]
            del self.entries[choice]
        except (KeyError, ValueError):
            pass

        return True


class Timers(Action):
    """
    Show a users own timers.
    """
    async def execute(self):
        if self.args.clear:
            for key_to_remove in [x for x in TIMERS if self.msg.author.name in x]:
                del TIMERS[key_to_remove]
            await self.bot.send_message(self.msg.channel, "Your timers have been cancelled.")
        elif self.args.manage:
            entries = [x for x in TIMERS if self.msg.author.name in x]
            await TimersMenu(self, entries).run()
        else:
            await self.bot.send_long_message(self.msg.channel,
                                             timer_summary(TIMERS, self.msg.author.name))


class Turn(Action):
    """
    Manipulate a turn order tracker.
    """
    def add(self, session, order):
        """
        Add users to an existing turn order,
        start a new turn order if needed.
        """
        parts = ' '.join(self.args.add).split(',')

        if not order:
            order = dice.turn.TurnOrder()
            parts += dicedb.query.generate_inital_turn_users(session, self.chan_id)

        order.add_all(dice.turn.parse_turn_users(parts))
        dicedb.query.update_turn_order(session, self.chan_id, order)

        return str(order)

    def clear(self, session, _):
        """
        Clear the turn order.
        """
        dicedb.query.remove_turn_order(session, self.chan_id)
        return 'Turn order cleared.'

    def mod(self, session, _):
        """
        Update a user's initiative modifier.
        """
        dicedb.query.update_turn_char(session, str(self.msg.author.id),
                                      self.chan_id, modifier=self.args.mod)
        return 'Updated **modifier** for {} to: {}'.format(self.msg.author.name, self.args.mod)

    def name(self, session, _):
        """
        Update a user's character name for turn order.
        """
        name_str = ' '.join(self.args.name)
        dicedb.query.update_turn_char(session, str(self.msg.author.id),
                                      self.chan_id, name=name_str)
        return 'Updated **name** for {} to: {}'.format(self.msg.author.name, name_str)

    def __single_next(self, session, order):
        """
        Advance the turn order.
        """
        msg = ''
        if order.cur_user:
            effects = order.cur_user.decrement_effects()
            if effects:
                msg += 'The following effects expired for **{}**:\n'.format(order.cur_user.name)
                pad = '\n' + ' ' * 8
                msg += pad + pad.join([x.text for x in effects]) + '\n\n'

        msg += '**Next User**\n' + str(order.next())

        dicedb.query.update_turn_order(session, self.chan_id, order)

        return msg

    def next(self, _, order):
        """
        Advance the turn order next places.
        """
        if self.args.next < 1:
            raise dice.exc.InvalidCommandArgs('!next requires number in range [1, +∞]')

        text, cnt = '', self.args.next
        while cnt:
            text += self.__single_next(_, order) + '\n\n'
            cnt -= 1

        return text.rstrip()

    def remove(self, session, order):
        """
        Remove one or more users from turn order.
        """
        users = ' '.join(self.args.remove).split(',')
        removed = []
        for user in users:
            removed += [order.remove(user)]

        dicedb.query.update_turn_order(session, self.chan_id, order)

        msg = 'Removed the following users:\n'
        return msg + '\n  - ' + '\n  - '.join([x.name for x in removed])

    def unset(self, session, _):
        """
        Unset the default character you set for the channel.
        """
        dicedb.query.remove_turn_char(session, str(self.msg.author.id),
                                      self.chan_id)

        return "Removed you from the default turn order."

    def update(self, session, order):
        """
        Update one or more character's init for this turn order.
        Usually used for some spontaneous change or DM decision.
        """
        msg = 'Updated the following users:\n'
        for spec in ' '.join(self.args.update).split(','):
            try:
                part_name, new_init = spec.split('/')
                changed = order.update_user(part_name.strip(), new_init.strip())
                msg += '    Set __{}__ to {}\n'.format(changed.name, changed.init)
            except ValueError:
                raise dice.exc.InvalidCommandArgs("See usage, incorrect arguments.")

        dicedb.query.update_turn_order(session, self.chan_id, order)

        return msg

    async def execute(self):
        dicedb.query.ensure_duser(self.session, self.msg.author)

        order = dice.turn.parse_order(dicedb.query.get_turn_order(self.session, self.chan_id))
        msg = str(order) if order else 'No turn order to report.'

        if not order and (self.args.next != 'zero' or self.args.remove):
            raise dice.exc.InvalidCommandArgs('Please add some users first.')

        try:
            # Non-numeric default is 'zero', when arg not provided is None
            try:
                self.args.next = int(self.args.next)
            except TypeError:
                self.args.next = 1
            msg = getattr(self, 'next')(self.session, order)
        except (AttributeError, ValueError):
            pass

        methods = [x[0] for x in inspect.getmembers(self, inspect.ismethod)
                   if x[0] not in ['__init__', 'execute', '__single_next', 'next']]
        for name in methods:
            try:
                var = getattr(self.args, name)
                if var is not None and var is not False:  # 0 is allowed for init
                    msg = getattr(self, name)(self.session, order)
                    break
            except AttributeError:
                pass

        await self.bot.send_message(self.msg.channel, msg)


class Effect(Action):
    """
    Manage effects for users in the turn order.
    """
    @staticmethod
    def add(chars, new_effects):
        """
        Add recurring effects to characters in the turn order.

        Args:
            chars: The TurnOrder characters to modify.
            new_effects: The new effects to apply to them.
        """
        msg = ''
        for char in chars:
            for new_effect in new_effects:
                try:
                    char.add_effect(new_effect[0], int(new_effect[1]))
                    msg += '{}: Added {} for {} turns.\n'.format(char.name, new_effect[0], new_effect[1])
                except (IndexError, ValueError):
                    raise dice.exc.InvalidCommandArgs("Invalid round count for effect.")

        return msg

    @staticmethod
    def remove(chars, new_effects):
        """
        Remove recurring effects from characters in turn order.

        Args:
            chars: The TurnOrder characters to modify.
            new_effects: The effects to remove from them.
        """
        msg = ''
        for char in chars:
            for new_effect in new_effects:
                char.remove_effect(new_effect[0])
                msg += '{}: Removed {}.\n'.format(char.name, new_effect[0])

        return msg

    @staticmethod
    def update(chars, new_effects):
        """
        Update recurring effects on characters in turn order.

        Args:
            chars: The TurnOrder characters to modify.
            new_effects: The effects to update,
                         should be textual match to original name with different turn count.
        """
        msg = ''
        for char in chars:
            for new_effect in new_effects:
                try:
                    char.update_effect(new_effect[0], int(new_effect[1]))
                    msg += '{}: Updated {} for {} turns.\n'.format(char.name, new_effect[0], new_effect[1])
                except (IndexError, ValueError):
                    raise dice.exc.InvalidCommandArgs("Invalid round count for effect.")

        return msg

    async def execute(self):
        order = dice.turn.parse_order(dicedb.query.get_turn_order(self.session, self.chan_id))
        if not order:
            raise dice.exc.InvalidCommandArgs('No turn order set to add effects.')

        targets = [target.lstrip() for target in ' '.join(self.args.targets).split(',')
                   if target.lstrip()]
        chars = [user for user in order.users if user.name in targets]

        msg = '__Characters With Effects__\n\n'
        for char in order.users:
            if char.effects:
                msg += '{}\n\n'.format(char)

        effects_args = None
        for name in ['add', 'remove', 'update']:
            effects_args = getattr(self.args, name)
            if effects_args:
                new_effects = [x.strip().split('/') for x in (' '.join(effects_args)).split(',')]
                msg = getattr(self.__class__, name)(chars, new_effects)
                break

        if targets and not effects_args:
            msg = 'No action selected for targets [--add|--remove|--update].'

        dicedb.query.update_turn_order(self.session, self.chan_id, order)

        await self.bot.send_message(self.msg.channel, msg)


class PunMenu(dice.util.PagingMenu):
    """
    Manage the puns in the database.
    """
    def menu(self):
        header = """**Pun Management**
Page {}/{}
Select a pun to remove by number [1..{}]:


""".format(self.page, self.total_pages, len(self.cur_entries))
        return format_pun_list(header, self.entries[:LIMIT_SONGS], dice.util.PAGING_FOOTER, cnt=1)

    async def handle_msg(self, user_select):
        choice = int(user_select.content) - 1
        if choice < 0 or choice >= len(self.cur_entries):
            raise ValueError

        dicedb.query.remove_pun(self.act.session, self.entries[choice])
        del self.entries[choice]

        return True


class Pun(Action):
    """
    Manage puns for users.
    """
    async def execute(self):
        if self.args.add:
            text = ' '.join(self.args.add)
            if dicedb.query.check_for_pun_dupe(self.session, text):
                raise dice.exc.InvalidCommandArgs("Pun already in the database!")
            dicedb.query.add_pun(self.session, text)

            msg = 'Pun added to the abuse database.'

        elif self.args.manage:
            entries = dicedb.query.all_puns(self.session)
            await PunMenu(self, entries).run()
            self.session.commit()

            msg = 'Pun abuse management terminated.'

        else:
            msg = '**Randomly Selected Pun**\n\n'
            msg += dicedb.query.randomly_select_pun(self.session)

        await self.bot.send_message(self.msg.channel, msg)


class YTMenu(dice.util.PagingMenu):
    """
    Select a youtube video to play from search results.
    """
    def menu(self):
        cnt = 1
        msg = """**Youtube Search**
Page {}/{}
Select a song to play by number [1..{}]:


""".format(self.page, self.total_pages, len(self.cur_entries))

        for result in self.cur_entries:
            msg += """    {cnt}) **{title}**    <{url}>
        __Time__ {duration}    __Views__ {views}
""".format(cnt=cnt, **result)
            cnt += 1
        msg = msg.rstrip()
        msg += dice.util.PAGING_FOOTER

        return msg

    async def handle_msg(self, user_select):
        choice = int(user_select.content) - 1
        if choice < 0 or choice >= len(self.cur_entries):
            raise ValueError

        selected = self.entries[choice]
        videos = dicedb.query.validate_videos([selected['url']])
        videos[0].name = selected['title'][:30]

        mplayer = get_guild_player(self.act.guild_id, self.msg)
        msg = await self.send("Please wait, ensuring first song downloaded. Rest will download in background.")
        await mplayer.replace_and_play(videos)
        await self.send(str(mplayer))
        try:
            await msg.delete()
        except discord.Forbidden:
            pass

        return True


class YTSearch(Action):
    """
    Search youtube for videos to play.
    """
    async def execute(self):
        terms = [re.subn(r'[^a-z0-9\',.]+', '', term)[0] for term in self.args.terms]

        entries = await dice.music.yt_search(terms)
        mplayer = get_guild_player(self.guild_id, self.msg)
        if self.args.first:
            videos = dicedb.query.validate_videos([entries[0]['url']])
            videos[0].name = entries[0]['title']
            msg = await self.bot.send_message(self.msg.channel, "Please wait, ensuring first song downloaded. Rest will download in background.")
            await mplayer.replace_and_play(videos)
            await self.bot.send_message(self.msg.channel, str(mplayer))
            try:
                await msg.delete()
            except discord.Forbidden:
                pass
        else:
            await YTMenu(self, entries, 6).run()


async def timer_monitor(timers, sleep_time=CHECK_TIMER_GAP):
    """
    Perform a check on all active timers every sleep_time seconds.

    If a trigger has been reached, send the appropriate message back to channel.
    If timer is_expired, delete it from the timers structure.

    Args:
        timers: A dictionary containing all Timer objects by Timer.key.
        sleep_time: The gap between checks on the timer.
    """
    await asyncio.sleep(sleep_time)
    asyncio.ensure_future(timer_monitor(timers, sleep_time))

    for timer in timers.values():
        msg = timer.check_triggers()
        if msg:
            await timer.update_notice(msg)

        if timer.is_expired():
            try:
                del timers[timer.key]
            except KeyError:
                pass


def timer_summary(timers, name):
    """
    Generate a summary of the timers that name has started.

    Args:
        timers: A dictionary whose values are Timer objects.
        name: The name of the author, will be used to select timers they own.

    Returns:
        A string that summarizes name's timers.
    """
    msg = "Active timers for __{}__:\n\n".format(name)

    user_timers = [x for x in timers.values() if name in x.key]
    if user_timers:
        for ind, timer in enumerate(user_timers, start=1):
            msg += "  **{}**) ".format(ind) + str(timer)
    else:
        msg += "**None**"

    return msg


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


def format_pun_list(header, entries, footer, *, cnt=1):
    """
    Generate the management list of entries.
    """
    msg = header
    for ent in entries:
        msg += '{}) {}\n    Hits: {:4d}\n\n'.format(cnt, ent.text, ent.hits)
        cnt += 1
    msg = msg.rstrip()
    msg += footer

    return msg


def format_song_list(header, songs, footer, *, cnt=1):
    """
    Generate the management list of songs.
    """
    msg = header
    for song in songs:
        msg += song.format_menu(cnt)
        cnt += 1
    msg = msg.rstrip()
    msg += footer

    return msg


def get_results_in_background(full_url, num):
    """
    Fetch the top num results from full_url (a GCS page).
    """
    browser = dice.util.init_chrome()
    browser.get(full_url)

    result = ''
    for ele in browser.find_elements_by_class_name('gsc-thumbnail-inside')[:num]:
        link_text = ele.find_element_by_css_selector('a.gs-title').get_property('href')
        result += '{}\n      <{}>\n'.format(ele.text, link_text)
    browser.quit()
    del browser  # Force cleanup now

    return result.rstrip()


def throw_in_pool(throw):  # pragma: no cover
    """
    Simple wrapper to init random in other process before throw.
    """
    dice.util.seed_random()  # This runs in another process so seed again.
    return throw.next()


def get_guild_player(guild_id, msg):
    """
    Get the guild player for a guild.
    Current model assumes bot can maintain separate streams for each guild.
    """
    try:
        target = msg.author.voice.channel
    except AttributeError:
        target = discord.utils.find(lambda x: isinstance(x, discord.VoiceChannel),
                                    msg.guild.channels)

    if guild_id not in PLAYERS:
        PLAYERS[guild_id] = GuildPlayer(vids=[], target_channel=target)
    PLAYERS[guild_id].target_channel = target

    return PLAYERS[guild_id]
