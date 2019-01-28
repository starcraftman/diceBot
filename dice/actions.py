"""
To facilitate complex actions based on commands create a
hierarchy of actions that can be recombined in any order.
All actions have async execute methods.
"""
from __future__ import absolute_import, print_function
import asyncio
import concurrent.futures
import datetime
import glob
import logging
import math
import os
import re

import aiohttp
import discord
import numpy.random as rand

import dice.exc
import dice.roll
import dice.tbl
import dice.turn
import dice.util

import dicedb
import dicedb.query

CHECK_TIMER_GAP = 5
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
PF_URL = 'https://cse.google.com/cse?cx=006680642033474972217%3A6zo0hx_wle8&q={}'
D5_URL = 'https://cse.google.com/cse?cx=006680642033474972217%3A1xq0zf2wtvq&q={}'
STAR_URL = 'https://cse.google.com/cse?cx=006680642033474972217%3Awyjvzq2cjz8&q={}'
PONI_URL = "https://derpibooru.org/search.json?q="
SONG_DB_FILE = os.path.abspath(os.path.join("data", "songs.yml"))
SONG_TAGS_FILE = os.path.abspath(os.path.join("data", "song_tags.yml"))
SONG_FMT = """        __Song {}__: {name}
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
TURN_ORDER = None


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
            ['{prefix}d5', 'Search on the D&D 5e wiki'],
            ['{prefix}effect', 'Add an effect to a user in turn order'],
            ['{prefix}e', 'Alias for `!effect`'],
            ['{prefix}math', 'Do some math operations'],
            ['{prefix}m', 'Alias for `!math`'],
            ['{prefix}n', 'Alias for `!turn --next`'],
            ['{prefix}pf', 'Search on the Pathfinder wiki'],
            ['{prefix}play', 'Play songs from youtube and server.'],
            ['{prefix}poni', 'Pony?!?!'],
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
            await self.bot.delete_message(self.msg)
        except discord.Forbidden as exc:
            self.log.error("Failed to delete msg on: %s/%s\n%s",
                           self.msg.channel.server, self.msg.channel, str(exc))


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
    Transparent mapper from actions onto the mplayer.
    """
    async def execute(self):
        mplayer = self.bot.mplayer

        if self.args.stop:
            mplayer.stop()
        elif self.args.pause:
            mplayer.pause()
        elif self.args.next:
            await mplayer.next()
        elif self.args.prev:
            await mplayer.prev()
        elif self.args.volume != 'zero':
            mplayer.set_volume(self.args.volume)
        elif self.args.loop:
            mplayer.loop = not mplayer.loop
        elif self.args.restart:
            await mplayer.start()
        elif self.args.status:
            pass
        elif self.args.vids:
            parts = [part.strip() for part in re.split(r'\s*,\s*', ' '.join(self.args.vids))]
            new_vids = validate_videos(parts)

            if self.args.append:
                mplayer.vids += new_vids
            else:
                # New videos played so replace playlist
                mplayer.initialize_settings(self.msg, new_vids)
                await mplayer.start()

        await self.bot.send_message(self.msg.channel, str(self.bot.mplayer))


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

    def load(self):
        """
        Load the song dbs from files.
        """
        self.song_db = dice.util.load_yaml(SONG_DB_FILE)
        self.tag_db = dice.util.load_yaml(SONG_TAGS_FILE)

    def save(self):
        """
        Save the song dbs to files.
        """
        dice.util.write_yaml(SONG_DB_FILE, self.song_db)
        dice.util.write_yaml(SONG_TAGS_FILE, self.tag_db)

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
                self.tag_db[tag] = sorted(self.tag_db[tag] + [key])
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

        while entries:
            try:
                num_entries = len(entries[:LIMIT_SONGS])
                reply = format_song_list('**__Songs DB__** Page {}\n\n'.format(page),
                                         entries[:LIMIT_SONGS], SONG_FOOTER, cnt=cnt)
                messages = [await self.bot.send_message(self.msg.channel, reply)]
                user_select = await self.bot.wait_for_message(timeout=30, author=self.msg.author,
                                                              channel=self.msg.channel)

                if user_select:
                    messages += [user_select]
                    user_select.content = user_select.content.lower().strip()

                if not user_select or user_select.content in ['done', 'exit', 'stop']:
                    await self.bot.send_message(self.msg.channel, 'List terminated.')
                    break

                elif user_select.content == 'next':
                    entries = entries[LIMIT_SONGS:]
                    page += 1
                    cnt += LIMIT_SONGS

                else:
                    choice = int(user_select.content.replace('play', '')) - 1
                    if choice < 0 or choice >= LIMIT_SONGS:
                        raise ValueError
                    selected = entries[choice]

                    self.bot.mplayer.initialize_settings(self.msg, validate_videos([selected['url']]))
                    asyncio.ensure_future(asyncio.gather(
                        self.bot.mplayer.start(),
                        self.bot.send_message(self.msg.channel, '**Song Started**\n\n' + SONG_FMT.format(1, **selected)),
                    ))
                    break
            except ValueError:
                await self.bot.send_message(
                    self.msg.channel,
                    'Selection not understood. Make choice in [1, {}]'.format(num_entries)
                )
            finally:
                user_select = None
                asyncio.ensure_future(self.bot.delete_messages(messages))

    async def manage(self):
        """
        Using paging interface similar to list, allow management of song db.
        """
        cnt = 1
        entries = sorted(list(self.song_db.values()), key=lambda x: x['name'])
        num_entries = len(entries[:LIMIT_SONGS])

        while entries:
            try:
                reply = format_song_list("Remove one of these songs? [1..{}]:\n\n".format(num_entries),
                                         entries[:LIMIT_SONGS], SONG_FOOTER, cnt=cnt)
                messages = [await self.bot.send_message(self.msg.channel, reply)]
                user_select = await self.bot.wait_for_message(timeout=30, author=self.msg.author,
                                                              channel=self.msg.channel)

                if user_select:
                    messages += [user_select]
                    user_select.content = user_select.content.lower().strip()

                if not user_select or user_select.content in ['done', 'exit', 'stop']:
                    await self.bot.send_message(self.msg.channel, "Management terminated.")
                    break

                elif user_select.content == 'next':
                    cnt += LIMIT_SONGS
                    entries = entries[LIMIT_SONGS:]
                    num_entries = len(entries[:LIMIT_SONGS])

                else:
                    choice = int(user_select.content) - 1
                    if choice < 0 or choice >= LIMIT_SONGS:
                        raise ValueError

                    self.remove(entries[choice]['name'])
                    del entries[choice]
            except (KeyError, ValueError):
                await self.bot.send_message(
                    self.msg.channel,
                    'Selection not understood. Make choice in [1, {}]'.format(num_entries)
                )
            finally:
                user_select = None
                asyncio.ensure_future(self.bot.delete_messages(messages))

    async def select_song(self, songs):
        all_songs = sorted(songs, key=lambda x: x['name'])
        cnt = 1

        while all_songs:
            try:
                page_songs = all_songs[:LIMIT_SONGS]
                num_entries = len(page_songs)
                song_msg = format_song_list('Choose from the following songs...\n\n',
                                            page_songs, SONG_FOOTER, cnt=cnt)
                song_msg += 'Type __back__ to return to tags.'

                messages = [await self.bot.send_message(self.msg.channel, song_msg)]
                user_select = await self.bot.wait_for_message(timeout=30, author=self.msg.author,
                                                              channel=self.msg.channel)

                if user_select:
                    messages += [user_select]
                    user_select.content = user_select.content.lower().strip()

                if not user_select or user_select.content in ['done', 'exit', 'stop']:
                    await self.bot.send_message(self.msg.channel, 'Play db terminated.')
                    break

                elif user_select.content == 'back':
                    asyncio.ensure_future(self.select_tag())
                    break

                elif user_select.content == 'next':
                    all_songs = all_songs[LIMIT_SONGS:]
                    cnt += LIMIT_SONGS

                else:
                    choice = int(user_select.content.replace('play ', '')) - 1
                    if choice < 0 or choice >= num_entries:
                        raise ValueError
                    selected = page_songs[choice]

                    self.bot.mplayer.initialize_settings(self.msg, validate_videos([selected['url']]))
                    asyncio.ensure_future(asyncio.gather(
                        self.bot.mplayer.start(),
                        self.bot.send_message(self.msg.channel, '**Song Started**\n\n' + SONG_FMT.format(1, **selected)),
                    ))
                    break
            except ValueError:
                await self.bot.send_message(
                    self.msg.channel,
                    'Selection not understood. Make choice in [1, {}]'.format(num_entries)
                )
            finally:
                user_select = None
                asyncio.ensure_future(self.bot.delete_messages(messages))

    async def select_tag(self):
        """
        Use the Songs db to lookup dynamically based on tags.
        """
        all_tags = sorted(list(self.tag_db.keys()))
        cnt = 1

        while all_tags:
            try:
                page_tags = all_tags[:LIMIT_TAGS]
                num_entries = len(page_tags)
                tag_msg = 'Select one of the following tags by number to explore:\n\n'
                for ind, tag in enumerate(page_tags, start=cnt):
                    tag_msg += '        **{}**) {} ({} songs)\n'.format(ind, tag, len(self.tag_db[tag]))
                tag_msg = tag_msg.rstrip()
                tag_msg += SONG_FOOTER
                messages = [await self.bot.send_message(self.msg.channel, tag_msg)]
                user_select = await self.bot.wait_for_message(timeout=30, author=self.msg.author,
                                                              channel=self.msg.channel)

                if user_select:
                    messages += [user_select]
                    user_select.content = user_select.content.lower().strip()

                if not user_select or user_select.content in ['done', 'exit', 'stop']:
                    await self.bot.send_message(self.msg.channel, 'Play db terminated.')
                    break

                elif user_select.content == 'next':
                    all_tags = all_tags[LIMIT_TAGS:]
                    cnt += LIMIT_TAGS

                else:
                    choice = int(user_select.content) - 1
                    if choice < 0 or choice >= num_entries:
                        raise ValueError

                    songs = [self.song_db[x] for x in self.tag_db[page_tags[choice]]]
                    asyncio.ensure_future(self.select_song(songs))
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
                asyncio.ensure_future(self.bot.delete_messages(messages))

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

            reply = '__Song Added__\n\n' + SONG_FMT.format(1, **self.song_db[key])
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
            for _ in range(times):
                lines += [line + " = {}".format(await throw.next(self.bot.loop))]

        return lines

    async def execute(self):
        session = dicedb.Session()
        full_spec = ' '.join(self.args.spec).strip()
        user_id = self.msg.author.id
        msg = ''

        if self.args.save:
            duser = dicedb.query.ensure_duser(session, self.msg.author)
            roll = dicedb.query.update_saved_roll(session, duser.id, self.args.save, full_spec)

            msg = 'Added roll: __**{}**__: {}'.format(roll.name, roll.roll_str)

        elif self.args.list:
            rolls = dicedb.query.find_all_saved_rolls(session, user_id)
            resp = ['__**Saved Rolls**__:', '']
            resp += ['__{}__: {}'.format(roll.name, roll.roll_str) for roll in rolls]

            msg = '\n'.join(resp)

        elif self.args.remove:
            roll = dicedb.query.remove_saved_roll(session, user_id, self.args.remove)

            msg = 'Removed roll: __**{}**__: {}'.format(roll.name, roll.roll_str)

        else:
            try:
                if full_spec == '':
                    raise dice.exc.InvalidCommandArgs('A roll requires some text!')

                saved_roll = dicedb.query.find_saved_roll(session, user_id, full_spec)
                full_spec = saved_roll.roll_str
                resp = ['__Dice Rolls__ ({})'.format(saved_roll.name), '']
            except dice.exc.NoMatch:
                resp = ['__Dice Rolls__', '']

            resp += await self.make_rolls(full_spec)
            msg = '\n'.join(resp)

        await self.bot.send_message(self.msg.channel, msg)


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
                        await self.bot.delete_message(self.sent_msg)
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
                user_select = await self.bot.wait_for_message(timeout=30, author=self.msg.author,
                                                              channel=self.msg.channel)

                if user_select:
                    messages += [user_select]
                    user_select.content = user_select.content.lower().strip()

                if not user_select or user_select.content in ['done', 'exit', 'stop']:
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
        elif self.args.manage:
            await self.manage_timers()
        else:
            await self.bot.send_message(self.msg.channel, self.timer_summary())


class Turn(Action):
    """
    Manipulate a global turn order tracker.
    """
    def add(self, session):
        """
        Add users to an existing turn order,
        start a new turn order if needed.
        """
        global TURN_ORDER
        parts = ' '.join(self.args.add).split(',')
        users = dice.turn.parse_turn_users(parts)

        if not TURN_ORDER:
            TURN_ORDER = dice.turn.TurnOrder()
            init_users = dice.turn.parse_turn_users(
                dicedb.query.generate_inital_turn_users(session))
            TURN_ORDER.add_all(init_users)
        TURN_ORDER.add_all(users)

        return str(TURN_ORDER)

    def clear(self, _):
        """
        Clear the turn order.
        """
        global TURN_ORDER
        TURN_ORDER = None
        return 'Turn order cleared.'

    def init(self, session):
        """
        Update a user's permanent starting init.
        """
        dicedb.query.update_duser_init(session, self.msg.author, self.args.init)
        return 'Updated **init** for {} to: {}'.format(self.msg.author.name, self.args.init)

    def next(self, _):
        """
        Advance the turn order.
        """
        msg = ''
        if TURN_ORDER.cur_user:
            effects = TURN_ORDER.cur_user.decrement_effects()
            if effects:
                msg += 'The following effects expired for **{}**:\n'.format(TURN_ORDER.cur_user.name)
                pad = '\n' + ' ' * 8
                msg += pad + pad.join(effects) + '\n\n'

        return msg + '**Next User**\n' + str(TURN_ORDER.next())

    def next_num(self, _):
        """
        Advance the turn order next_num places.
        """
        if self.args.next_num < 1:
            raise dice.exc.InvalidCommandArgs('Can only accept numbers in [0, +8]')

        text = ''
        cnt = self.args.next_num
        while cnt:
            text += self.next(_) + '\n\n'
            cnt -= 1

        return text.rstrip()

    def remove(self, _):
        """
        Remove one or more users from turn order.
        """
        users = ' '.join(self.args.remove).split(',')
        for user in users:
            TURN_ORDER.remove(user)

        msg = 'Removed the following users:\n'
        msg += '\n  - ' + '\n  - '.join(users)

    def name(self, session):
        """
        Update a user's character name for turn order.
        """
        name_str = ' '.join(self.args.name)
        dicedb.query.update_duser_character(session, self.msg.author, name_str)
        return 'Updated **name** for {} to: {}'.format(self.msg.author.name, name_str)

    def update(self, _):
        """
        Update one or more character's init for this turn order.
        Usually used for some spontaneous change or DM decision.
        """
        msg = 'Updated the following users:\n'
        for spec in ' '.join(self.args.update).split(','):
            part_name, new_init = spec.split('/')
            TURN_ORDER.update_user(part_name.strip(), new_init.strip())
            msg += '    Set __{}__ to {}\n'.format(part_name, new_init)

        return msg

    async def execute(self):
        session = dicedb.Session()
        dicedb.query.ensure_duser(session, self.msg.author)

        msg = str(TURN_ORDER)
        if not TURN_ORDER and (self.args.next or self.args.remove):
            raise dice.exc.InvalidCommandArgs('Please add some users first.')
        elif not TURN_ORDER:
            msg = 'No turn order to report.'

        for action in ['add', 'clear', 'init', 'name', 'next_num', 'next', 'remove', 'update']:
            try:
                var = getattr(self.args, action)
                if var is not None and var is not False:  # 0 is allowed for init
                    msg = getattr(self, action)(session)
                    break
            except AttributeError:
                pass

        await self.bot.send_message(self.msg.channel, msg)


class Effect(Action):
    """
    Manage effects for users in the turn order.
    """
    def update_targets(self):
        """
        Update effects for characters in the turn order.
        """
        targets = [target.lstrip() for target in ' '.join(self.args.targets).split(',')]
        tusers = [user for user in TURN_ORDER.users if user.name in targets]
        new_effects = [x.strip().split('/') for x in (' '.join(self.args.effects)).split(',')]

        msg = ''
        for tuser in tusers:
            for new_effect in new_effects:
                if self.args.add:
                    tuser.add_effect(new_effect[0], int(new_effect[1]))
                    msg += '{}: Added {} for {} turns.\n'.format(tuser.name, new_effect[0], new_effect[1])

                elif self.args.remove:
                    tuser.remove_effect(new_effect[0])
                    msg += '{}: Removed {}.\n'.format(tuser.name, new_effect[0])

                elif self.args.update:
                    tuser.update_effect(new_effect[0], int(new_effect[1]))
                    msg += '{}: Updated {} for {} turns.\n'.format(tuser.name, new_effect[0], new_effect[1])

                else:
                    msg = 'No action selected for targets [--add|remove|update].'

        return msg

    async def execute(self):
        global TURN_ORDER
        if not TURN_ORDER:
            raise dice.exc.InvalidCommandArgs('No turn order set to add effects.')

        if self.args.targets:
            msg = self.update_targets()

        else:
            msg = '__Characters With Effects__\n\n'
            for tuser in TURN_ORDER.users:
                if tuser.effects:
                    msg += '{}\n\n'.format(tuser)

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


def validate_videos(list_vids):
    """
    Validate the videos asked to play. Accepted formats:
        - youtube links
        - names of songs in the song db
        - names of files on the local HDD

    Raises:
        InvalidCommandArgs - A video link or name failed validation.
    """
    song_db = dice.util.load_yaml(SONG_DB_FILE)
    new_vids = []

    for vid in list_vids:
        if vid[0] == '<' and vid[-1] == '>':
            vid = vid[1:-1]

        if vid in song_db:
            new_vids.append(song_db[vid]['url'])

        elif dice.util.is_valid_yt(vid):
            new_vids.append(vid)

        elif dice.util.is_valid_url(vid):
            raise dice.exc.InvalidCommandArgs("Only youtube links supported: " + vid)

        else:
            globbed = glob.glob(os.path.join(MUSIC_PATH, vid + "*"))
            if len(globbed) != 1:
                raise dice.exc.InvalidCommandArgs("Cannot find local video: " + vid)
            new_vids.append(globbed[0])

    return new_vids


def format_song_list(header, entries, footer, *, cnt=1):
    """
    Generate the management list of entries.
    """
    msg = header
    for ent in entries:
        msg += SONG_FMT.format(cnt, **ent)
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

    return result.rstrip()
