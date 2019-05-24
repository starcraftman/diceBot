"""
To facilitate complex actions based on commands create a
hierarchy of actions that can be recombined in any order.
All actions have async execute methods.
"""
from __future__ import absolute_import, print_function
import asyncio
import concurrent.futures
import datetime
import functools
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
PAGING_STOP_WORDS = ['done', 'exit', 'stop']
TIMERS = {}
TIMER_OFFSETS = ["60:00", "15:00", "5:00", "1:00"]
TIMER_MSG_TEMPLATE = "{}: Timer '{}'"
TIMERS_MSG = """
Timer #{} with description: **{}**
    __Started at__: {} UTC
    __Ends at__: {} UTC
    __Time remaining__: {}
"""
PF_URL = 'https://cse.google.com/cse?cx=006680642033474972217%3A6zo0hx_wle8&q={}'
D5_URL = 'https://cse.google.com/cse?cx=006680642033474972217%3A1xq0zf2wtvq&q={}'
STAR_URL = 'https://cse.google.com/cse?cx=006680642033474972217%3Awyjvzq2cjz8&q={}'
PONI_URL = "https://derpibooru.org/search.json?q="
SONG_FMT = """        __Song {cnt}__: {name}
        __URL__: <{url}>
        __Tags__: {tags}

"""
SONG_FOOTER = """

Type __done__ or __exit__ or __stop__ to cancel.
Type __next__ to display the next page of entries.
Type __play 1__ to play entry 1 (if applicable).
"""
LIMIT_SONGS = 10
LIMIT_TAGS = 20
PLAYERS = {}


class Action(object):
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
            ['{prefix}m', 'Alias for `!math`'],
            ['{prefix}n', 'Alias for `!turn --next`'],
            ['{prefix}pf', 'Search on the Pathfinder wiki'],
            ['{prefix}play', 'Play songs from youtube and server.'],
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


class Play(Action):
    """
    Transparent mapper from user input onto the music player.
    """
    async def restart(self, mplayer):
        """ Restart the player at the beginning. """
        mplayer.reset_iterator()
        mplayer.play()
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
            mplayer.play()
        return "__**Now Playing**__\n\n{}".format(mplayer.cur_vid)

    async def prev(self, mplayer):
        """ Play the previous video. """
        if mplayer.prev():
            mplayer.play()
        return "__**Now Playing**__\n\n{}".format(mplayer.cur_vid)

    async def repeat_all(self, mplayer):
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
        mplayer.play()
        return "Player shuffle is now: **{}abled**".format('En' if mplayer.shuffle else 'Dis')

    async def status(self, mplayer):
        """ Show current bot status. """
        return str(mplayer)

    async def vids(self, mplayer):
        """ Initialize the player with requested videos and start playing. """
        parts = [part.strip() for part in re.split(r'\s*,\s*', ' '.join(self.args.vids))]

        if dice.util.is_valid_playlist(parts[0]):
            vid_info = await dice.music.get_yt_info(parts[0])
            new_vids = dicedb.query.validate_videos([x[0] for x in vid_info])
            for vid in new_vids:
                _, title = vid_info[0]
                vid_info = vid_info[1:]
                vid.name = title[:30]
        else:
            new_vids = dicedb.query.validate_videos(parts)

        msg = await self.bot.send_message(self.msg.channel, 'Please wait, downloading as needed before playing.')
        await dice.music.prefetch_vids(new_vids)

        if self.args.append:
            mplayer.append_vids(new_vids)
        else:
            mplayer.set_vids(new_vids)
            mplayer.play()

        await asyncio.gather(msg.delete(), self.bot.send_message(self.msg.channel, str(mplayer)))

    async def execute(self):
        mplayer = get_guild_player(self.guild_id, self.msg)
        await mplayer.join_voice_channel()

        if self.args.volume != 'zero':
            mplayer.set_volume(self.args.volume)
            msg = "Player volume: {}/100".format(mplayer.cur_vid.volume_int)
            await self.bot.send_message(self.msg.channel, msg)

        msg = str(mplayer)
        methods = [x[0] for x in inspect.getmembers(self, inspect.ismethod)
                   if x[0] not in ['__init__', 'execute']]
        for name in methods:
            if getattr(self.args, name):
                try:
                    msg = await getattr(self, name)(mplayer)
                except dice.exc.RemoteError as exc:
                    msg = str(exc)
                if msg:
                    await self.bot.send_long_message(self.msg.channel, msg)
                break

        if mplayer.cur_vid.id and (self.args.volume or self.args.repeat):
            song = dicedb.query.get_song_by_id(self.session, mplayer.cur_vid.id)
            song.update(mplayer.cur_vid)
            self.session.add(song)
            self.session.commit()


# TODO: Deduplicate code in 'management interface', make reusable.
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
        page = 1
        entries = dicedb.query.get_song_choices(self.session)

        while entries:
            try:
                reply = format_song_list('**__Songs DB__** Page {}\n\n'.format(page),
                                         entries[:LIMIT_SONGS], SONG_FOOTER)
                messages = [await self.bot.send_message(self.msg.channel, reply)]

                user_select = await self.bot.wait_for(
                    'message', check=functools.partial(check_messages, self.msg), timeout=30)

                if user_select:
                    messages += [user_select]
                    user_select.content = user_select.content.lower().strip()

                if not user_select or user_select.content in PAGING_STOP_WORDS:
                    await self.bot.send_message(self.msg.channel, 'List terminated.')
                    break

                elif user_select.content == 'next':
                    entries = entries[LIMIT_SONGS:]
                    page += 1

                else:
                    choice = int(user_select.content.replace('play', '')) - 1
                    if choice < 0 or choice >= LIMIT_SONGS:
                        raise ValueError
                    selected = entries[choice]

                    msg = await self.bot.send_message(self.msg.channel, 'Please wait, downloading as needed before playing.')
                    await get_guild_player(self.guild_id, self.msg).replace_and_play([selected])
                    await asyncio.gather(msg.delete(),
                                         self.bot.send_message(self.msg.channel, '**Song Started**\n\n' + format_a_song(1, selected)))
                    break
            except ValueError:
                await self.bot.send_message(
                    self.msg.channel,
                    'Selection not understood. Make choice in [1, {}]'.format(LIMIT_SONGS)
                )
            finally:
                user_select = None
                asyncio.ensure_future(messages[0].channel.delete_messages(messages))

    async def manage(self):
        """
        Using paging interface similar to list, allow management of song db.
        """
        entries = dicedb.query.get_song_choices(self.session)
        num_entries = len(entries[:LIMIT_SONGS])

        while entries:
            try:
                reply = format_song_list("Remove one of these songs? [1..{}]:\n\n".format(num_entries),
                                         entries[:LIMIT_SONGS], SONG_FOOTER)
                messages = [await self.bot.send_message(self.msg.channel, reply)]
                user_select = await self.bot.wait_for(
                    'message', check=functools.partial(check_messages, self.msg), timeout=30)

                if user_select:
                    messages += [user_select]
                    user_select.content = user_select.content.lower().strip()

                if not user_select or user_select.content in PAGING_STOP_WORDS:
                    await self.bot.send_message(self.msg.channel, "Management terminated.")
                    break

                elif user_select.content == 'next':
                    entries = entries[LIMIT_SONGS:]
                    num_entries = len(entries[:LIMIT_SONGS])

                else:
                    choice = int(user_select.content) - 1
                    if choice < 0 or choice >= LIMIT_SONGS:
                        raise ValueError

                    dicedb.query.remove_song_with_tags(self.session, entries[choice].name)
                    del entries[choice]
            except (KeyError, ValueError):
                await self.bot.send_message(
                    self.msg.channel,
                    'Selection not understood. Make choice in [1, {}]'.format(num_entries)
                )
            finally:
                user_select = None
                asyncio.ensure_future(messages[0].channel.delete_messages(messages))

        if not entries:
            await self.bot.send_message(self.msg.channel, "Management terminated.")

    async def select_song(self, tagged_songs):
        while tagged_songs:
            try:
                page_songs = tagged_songs[:LIMIT_SONGS]
                num_entries = len(page_songs)
                song_msg = format_song_list('Choose from the following songs...\n\n',
                                            page_songs, SONG_FOOTER)
                song_msg += 'Type __back__ to return to tags.'

                messages = [await self.bot.send_message(self.msg.channel, song_msg)]
                user_select = await self.bot.wait_for(
                    'message', check=functools.partial(check_messages, self.msg), timeout=30)

                if user_select:
                    messages += [user_select]
                    user_select.content = user_select.content.lower().strip()

                if not user_select or user_select.content in PAGING_STOP_WORDS:
                    await self.bot.send_message(self.msg.channel, 'Play db terminated.')
                    break

                elif user_select.content == 'back':
                    asyncio.ensure_future(self.select_tag())
                    break

                elif user_select.content == 'next':
                    tagged_songs = tagged_songs[LIMIT_SONGS:]

                else:
                    choice = int(user_select.content.replace('play ', '')) - 1
                    if choice < 0 or choice >= num_entries:
                        raise ValueError
                    selected = page_songs[choice]

                    msg = await self.bot.send_message(self.msg.channel, 'Please wait, downloading as needed before playing.')
                    await get_guild_player(self.guild_id, self.msg).replace_and_play([selected])
                    await asyncio.gather(msg.delete(),
                                         self.bot.send_message(self.msg.channel, '**Song Started**\n\n' + format_a_song(1, selected)))
                    break
            except ValueError:
                await self.bot.send_message(
                    self.msg.channel,
                    'Selection not understood. Make choice in [1, {}]'.format(num_entries)
                )
            finally:
                user_select = None
                asyncio.ensure_future(messages[0].channel.delete_messages(messages))

    async def select_tag(self):
        """
        Use the Songs db to lookup dynamically based on tags.
        """
        all_tags = dicedb.query.get_tag_choices(self.session)

        while all_tags:
            try:
                page_tags = all_tags[:LIMIT_TAGS]
                num_entries = len(page_tags)
                tag_msg = 'Select one of the following tags by number to explore:\n\n'
                for ind, tag in enumerate(page_tags, start=1):
                    tagged_songs = dicedb.query.get_songs_with_tag(self.session, tag)
                    tag_msg += '        **{}**) {} ({} songs)\n'.format(ind, tag, len(tagged_songs))
                tag_msg = tag_msg.rstrip()
                tag_msg += SONG_FOOTER.replace('__play ', '__') + "Type __all 1__ to play all songs with tag 1."
                messages = [await self.bot.send_message(self.msg.channel, tag_msg)]
                user_select = await self.bot.wait_for(
                    'message', check=functools.partial(check_messages, self.msg), timeout=30)

                if user_select:
                    messages += [user_select]
                    user_select.content = user_select.content.lower().strip()

                if not user_select or user_select.content in PAGING_STOP_WORDS:
                    await self.bot.send_message(self.msg.channel, 'Play db terminated.')
                    break

                elif user_select.content == 'next':
                    all_tags = all_tags[LIMIT_TAGS:]

                else:
                    choice = int(user_select.content.replace('play', '').replace('all', '')) - 1
                    if choice < 0 or choice >= num_entries:
                        raise ValueError

                    songs = dicedb.query.get_songs_with_tag(self.session, page_tags[choice])
                    if 'all' in user_select.content:
                        mplayer = get_guild_player(self.guild_id, self.msg)
                        msg = await self.bot.send_message(self.msg.channel, 'Please wait, downloading as needed before playing.')
                        await mplayer.replace_and_play(songs)
                        await asyncio.gather(msg.delete(), self.bot.send_message(self.msg.channel, str(mplayer)))
                    else:
                        await self.select_song(songs)
                    break
            except ValueError:
                await self.bot.send_message(
                    self.msg.channel,
                    'Selection not understood. Make choice in [1, {}]'.format(num_entries)
                )
            except dice.exc.InvalidCommandArgs as exc:
                await self.bot.send_message(self.msg.channel, str(exc))
            finally:
                user_select = None
                asyncio.ensure_future(messages[0].channel.delete_messages(messages))

    async def search_names(self, term):
        """
        Search for a name across key entries in the song db.
        """
        reply = '**__Songs DB__** - Searching Names for __{}__\n\n'.format(term)
        cnt = 1

        l_term = ' '.join(term).lower().strip()
        for song in dicedb.query.search_songs_by_name(dicedb.Session(), l_term):
            reply += format_a_song(cnt, song)
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
                reply += format_a_song(cnt, song)
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

            reply = '__Song Added__\n\n' + format_a_song(1, song)
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

    async def check_timer(self, sleep_time):
        """
        Perform a check on the triggers of this timer.

        If a trigger has been reached, send the appropriate message back to channel.
        If no triggers left, stop scheduling a new check_timer invocation.

        Args:
            sleep_time: The gap between checks on the timer.
        """
        del_cnt = 0
        now = datetime.datetime.utcnow()
        for trigger, msg in self.triggers:
            if now > trigger:
                if self.sent_msg:
                    try:
                        await self.sent_msg.delete()
                    except discord.Forbidden as exc:
                        self.log.error("Failed to delete msg on: %s/%s\n%s",
                                       self.msg.channel.server, self.msg.channel, str(exc))
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
        await self.check_timer(CHECK_TIMER_GAP)


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
                user_select = await self.bot.wait_for(
                    'message', check=functools.partial(check_messages, self.msg), timeout=30)

                if user_select:
                    messages += [user_select]
                    user_select.content = user_select.content.lower().strip()

                if not user_select or user_select.content in PAGING_STOP_WORDS:
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
                asyncio.ensure_future(messages[0].channel.delete_messages(messages))

    async def execute(self):
        if self.args.clear:
            remove_user_timers(TIMERS, self.msg.author.name)
        elif self.args.manage:
            await self.manage_timers()
        else:
            await self.bot.send_message(self.msg.channel, self.timer_summary())


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
                msg += pad + pad.join(effects) + '\n\n'

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
    def add(self, chars, new_effects):
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

    def remove(self, chars, new_effects):
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

    def update(self, chars, new_effects):
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
                msg = getattr(self, name)(chars, new_effects)
                break

        if targets and not effects_args:
            msg = 'No action selected for targets [--add|--remove|--update].'

        dicedb.query.update_turn_order(self.session, self.chan_id, order)

        await self.bot.send_message(self.msg.channel, msg)


class Pun(Action):
    """
    Manage puns for users.
    """
    async def manage(self, session):
        """
        Using paging interface similar to list, allow management of puns in db.
        """
        entries = dicedb.query.all_puns(session)
        num_entries = len(entries[:LIMIT_SONGS])

        while entries:
            try:
                reply = format_pun_list("Remove one of these puns? [1..{}]:\n\n".format(num_entries),
                                        entries[:LIMIT_SONGS], SONG_FOOTER, cnt=1)
                messages = [await self.bot.send_message(self.msg.channel, reply)]
                user_select = await self.bot.wait_for(
                    'message', check=functools.partial(check_messages, self.msg), timeout=30)

                if user_select:
                    messages += [user_select]
                    user_select.content = user_select.content.lower().strip()

                if not user_select or user_select.content in PAGING_STOP_WORDS:
                    break

                elif user_select.content == 'next':
                    entries = entries[LIMIT_SONGS:]
                    num_entries = len(entries[:LIMIT_SONGS])

                else:
                    choice = int(user_select.content) - 1
                    if choice < 0 or choice >= LIMIT_SONGS:
                        raise ValueError

                    dicedb.query.remove_pun(session, entries[choice])
                    del entries[choice]
            except (KeyError, ValueError):
                await self.bot.send_message(
                    self.msg.channel,
                    'Selection not understood. Make choice in [1, {}]'.format(num_entries)
                )
            finally:
                user_select = None
                asyncio.ensure_future(messages[0].channel.delete_messages(messages))

    async def execute(self):
        if self.args.add:
            text = ' '.join(self.args.add)
            if dicedb.query.check_for_pun_dupe(self.session, text):
                raise dice.exc.InvalidCommandArgs("Pun already in the database!")
            dicedb.query.add_pun(self.session, text)

            msg = 'Pun added to the abuse database.'

        elif self.args.manage:
            await self.manage(self.session)
            self.session.commit()

            msg = 'Pun abuse management terminated.'

        else:
            msg = '**Randomly Selected Pun**\n\n'
            msg += dicedb.query.randomly_select_pun(self.session)

        await self.bot.send_message(self.msg.channel, msg)


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


def format_song_list(header, entries, footer, *, cnt=1):
    """
    Generate the management list of entries.
    """
    msg = header
    for ent in entries:
        msg += format_a_song(cnt, ent)
        cnt += 1
    msg = msg.rstrip()
    msg += footer

    return msg


def format_a_song(cnt, song):
    """
    Helper for format_song_list.
    """
    return SONG_FMT.format(**{
        'cnt': cnt,
        'name': song.name,
        'tags': [x.name for x in song.tags],
        'url': song.url,
    })


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


def check_messages(original, msg):
    """
    Simply check if message came from same author and text channel.
    Use functools to bind self.msg into original to make predicate.
    """
    return msg.author == original.author and msg.channel == original.channel


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
