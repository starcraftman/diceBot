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
SONG_FILE = os.path.abspath(os.path.join("data", "songs.yml"))
SONG_HEADER = "{} - {} - {}\n\n".format('**Name**', '**URI**', '**Tags**')


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
    stopped = 0
    playing = 1
    paused = 2


# TODO: Tests? This is just a wrapper so should be covered by discord.py
class MPlayer(Action):
    """
    Music player interface.
    """
    def __init__(self, bot):
        self.bot = bot
        self.channel = None
        self.voice = None
        self.player = None
        self.vids = []
        self.vid_index = 0
        self.loop = False
        self.last_activity = datetime.datetime.utcnow()
        self.state = MPlayerState.stopped

    def __repr__(self):
        return "MPlayer(bot={}, channel={}, voice={}, player={},"\
            " vids={}, vid_index={}, loop={}, last_activity={}, state={})".format(
                self.bot, self.channel, self.voice, self.player,
                self.vids, self.vid_index, self.loop, self.last_activity, self.state
            )

    @property
    def active(self):
        return self.player and not self.player.is_done()

    @property
    def timed_out(self):
        return (datetime.datetime.utcnow() - self.last_activity).seconds > 300

    def initialize_settings(self, msg, args):
        self.channel = msg.author.voice.voice_channel
        if not self.channel:
            self.channel = discord.utils.get(msg.server.channels,
                                             type=discord.ChannelType.voice)

        self.loop = args.loop
        self.vids = validate_videos(args.vids)

    async def update_voice_channel(self):
        """
        Join the right channel before beginning transmission.
        """
        if self.voice:
            if self.channel != self.voice.channel:
                await self.voice.move_to(self.channel)
        else:
            self.voice = await self.bot.join_voice_channel(self.channel)

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
            self.player = await self.voice.create_ytdl_player(vid)
        else:
            self.player = self.voice.create_ffmpeg_player(vid)
        self.player.start()
        self.state = MPlayerState.playing

    def pause(self):
        """ Toggle player pause function. """
        if self.state == MPlayerState.playing:
            self.player.pause()
            self.state = MPlayerState.paused
        elif self.state == MPlayerState.paused:
            self.player.resume()
            self.state = MPlayerState.playing

    def stop(self):
        """
        Stop playing the stream.
        """
        try:
            self.state = MPlayerState.stopped
            self.player.stop()
        except AttributeError:
            pass

    async def quit(self):
        """
        Ensure player stopped and quit the voice channel.
        """
        try:
            self.stop()
            await self.voice.disconnect()
            self.player = None
            self.voice = None
        except AttributeError:
            pass

    def prev(self):
        """
        Go to the previous song.
        """
        if self.player and len(self.vids) > 1:
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
        if self.player and len(self.vids) > 1:
            if self.loop or self.vid_index + 1 < len(self.vids):
                self.vid_index = (self.vid_index + 1) % len(self.vids)
                asyncio.ensure_future(self.start())
            else:
                self.vid_index = 0
                self.stop()
                raise dice.exc.InvalidCommandArgs("Loop is not set, queue finished. Stopping.")

    async def monitor(self, sleep_time=3):
        """
        Simple monitor thread that lives as long as the bot runs.
        """
        while True:
            try:
                if self.player and self.state == MPlayerState.playing:
                    self.last_activity = datetime.datetime.utcnow()

                if self.state == MPlayerState.playing and self.player.is_done():
                    self.next()

                if self.timed_out:
                    self.quit()
            except youtube_dl.utils.DownloadError:
                await self.bot.send_message("Error fetching youtube vid: most probably copyright issue.\nTry another.")
            except youtube_dl.utils.YoutubeDLError:
                await self.bot.send_message("Something went wrong in YoutubeDL not related to copyright.\nTry again?.")
            except AttributeError:
                pass

            await asyncio.sleep(sleep_time)


class Play(Action):
    """
    Transparent mapper from actions onto the mplayer.
    """
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
            if self.args.volume < 0 or self.args.volume > 100:
                raise dice.exc.InvalidCommandArgs("Volume must be between [0, 100]")
            if not mplayer.player:
                raise dice.exc.InvalidCommandArgs("Volume can only be modified once player started.")
            mplayer.player.volume = self.args.volume / 100
        elif self.args.append:
            mplayer.vids += new_vids
        elif self.args.loop:
            mplayer.loop = not mplayer.loop
        else:
            if new_vids:
                # New videos played so replace playlist
                mplayer.initialize_settings(self.msg, self.args)
            await mplayer.start()


# TODO: Need tests here
class Songs(Action):
    """
    Songs command.
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        try:
            with open(SONG_FILE) as fin:
                self.db = yaml.load(fin, Loader=Loader)
            self.tag_db = {}
        except FileNotFoundError:
            self.db = {}
            self.save()

    def save(self):
        with open(SONG_FILE, 'w') as fout:
            yaml.dump(self.db, fout, Dumper=Dumper, endoding='UTF-8', indent=2,
                      explicit_start=True, default_flow_style=False)

    def refresh_tags(self):
        """
        Invert the yaml db into a tags lookup db.
        """
        self.tag_db = {}
        for key in self.db:
            ele = self.db[key]
            for tag in ele['tags']:
                try:
                    self.tag_db[tag].append(key)
                except KeyError:
                    self.tag_db[tag] = [key]

    def add(self):
        parts = re.split(r'\s*,\s*', self.msg.content.replace('!songs --add', ''))
        parts = [part.strip() for part in parts]
        self.db[parts[0]] = {
            'name': parts[0],
            'url': parts[1],
            'tags': parts[2:],
        }

        self.save()

    async def list(self):
        reply = 'Music Db\n\n'
        reply += SONG_HEADER

        for key in self.db:
            ent = self.db[key]
            reply += fmt_music_entry(ent)

        await self.bot.send_message(self.msg.channel, reply)

    async def manage(self):
        limit = 10
        keys = sorted(self.db.keys())

        while keys:
            try:
                subset_keys = keys[:limit]

                reply = "Do you want to manage the following? [1..{}]:\n".format(len(subset_keys))
                reply += "The selection will be removed from db.\n\n"
                for key in subset_keys:
                    reply += fmt_music_entry(self.db[key])
                reply += "\nWrite 'done' or 'stop' to finish."
                reply += "\nWrite 'next' to display the next page of entries."
                responses = [await self.bot.send_message(self.msg.channel, reply)]
                user_select = await self.bot.wait_for_message(timeout=30, author=self.msg.author,
                                                              channel=self.msg.channel)

                if user_select:
                    responses += [user_select]

                if not user_select or user_select.content.lower() == 'done'\
                        or user_select.content.lower() == 'stop':
                    return

                if user_select.content.lower() == 'next':
                    keys = keys[limit:]
                    continue

                choice = int(user_select.content) - 1
                if choice < 0 or choice >= len(subset_keys):
                    raise ValueError

                del self.db[subset_keys[choice]]
                keys.remove(subset_keys[choice])
                self.save()
            except (KeyError, ValueError):
                pass
            finally:
                user_select = None
                asyncio.ensure_future(asyncio.gather(
                    *[self.bot.delete_message(response) for response in responses]))

        await self.bot.send_message(self.msg.channel, "Management terminated.")

    async def search_names(self, term):
        reply = 'Music Db - Searching Names for "{}"\n\n'.format(term)
        reply += SONG_HEADER

        l_term = term.lower()
        for key in self.db:
            if l_term in key.lower():
                ent = self.db[key]
                reply += fmt_music_entry(ent)

        await self.bot.send_message(self.msg.channel, reply)

    async def search_tags(self, term):
        self.refresh_tags()
        reply = 'Music Db - Searching Tags for "{}"\n\n'.format(term)
        reply += SONG_HEADER

        l_term = term.lower()
        for key in self.tag_db:
            if l_term in key.lower():
                reply += '__**{}**__\n'.format(key)
                for name_key in self.tag_db[key]:
                    ent = self.db[name_key]
                    reply += fmt_music_entry(ent)
            reply += "\n"

        await self.bot.send_message(self.msg.channel, reply)

    async def execute(self):
        if self.args.add:
            self.add()
        if self.args.list:
            await self.list()
        elif self.args.manage:
            await self.manage()
        elif self.args.search_name:
            await self.search_names(self.args.search_name)
        elif self.args.search_tag:
            await self.search_tags(self.args.search_tag)


class Poni(Action):
    """
    Poni command.
    """
    async def execute(self):
        msg = "No images found!"
        tags = re.split(r'\s*,\s*|\s*,|,s*', self.msg.content[5:])
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
                responses = [await self.bot.send_message(self.msg.channel, reply)]
                user_select = await self.bot.wait_for_message(timeout=30, author=self.msg.author,
                                                              channel=self.msg.channel)

                if user_select:
                    responses += [user_select]

                if not user_select or user_select.content.lower() == 'done'\
                        or user_select.content.lower() == 'stop':
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
                asyncio.ensure_future(asyncio.gather(
                    *[self.bot.delete_message(response) for response in responses]))

    async def execute(self):
        if self.args.clear:
            remove_user_timers(TIMERS, self.msg.author.name)
            return
        elif self.args.manage:
            await self.manage_timers()
            return

        await self.bot.send_message(self.msg.channel, self.timer_summary())


def fmt_music_entry(ent):
    """
    Format an entry in the music db.
    """
    return "{} - {} - {}\n".format(
        ent['name'], '<{}>'.format(ent['url']) if 'youtu' in ent['url'] else ent['url'],
        ', '.join(ent.get('tags', []))
    )


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
