"""
To facilitate complex actions based on commands create a
hierarchy of actions that can be recombined in any order.
All actions have async execute methods.
"""
from __future__ import absolute_import, print_function
import asyncio
import concurrent.futures
import datetime
import json
import logging
import math
import os
import re

import aiohttp
import bs4
import discord
import numpy.random as rand
from selenium.webdriver.common.by import By

import dice.exc
import dice.roll
import dice.tbl
import dice.turn
import dice.util
#  from dice.music import GuildPlayer

import dicedb
import dicedb.query

ROLL_TIMEOUT = 30
CHECK_TIMER_GAP = 5
TIMERS = {}
TIMER_OFFSETS = ["60:00", "15:00", "5:00", "1:00"]
PF2_URL = 'https://pf2.d20pfsrd.com/?s={}'
PF_URL = 'https://cse.google.com/cse?cx=006680642033474972217%3A6zo0hx_wle8&q={}'
D5_URL = 'https://cse.google.com/cse?cx=006680642033474972217%3A1xq0zf2wtvq&q={}'
STAR_URL = 'https://cse.google.com/cse?cx=006680642033474972217%3Awyjvzq2cjz8&q={}'
PONI_JSON = "https://derpibooru.org/api/v1/json"
PONI_PER_PAGE = 25
LIMIT_SONGS = 8
LIMIT_TAGS = 16
LIMIT_REROLLS = dice.util.get_config('reroll_limit', default=20)
LIMIT_REROLLS_PER_PAGE = 10
LIMIT_ROLL_TIMES = 20
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
        self.db = dicedb.get_db_client()

    @property
    def discord_id(self):
        """Return the discord_id of the original message author. """
        return self.msg.author.id

    @property
    def chan_id(self):
        """
        An id representing the originating channel.
        """
        return self.msg.channel.id

    @property
    def guild_id(self):
        """
        An id representing the guild.
        """
        return self.msg.guild.id

    async def reply(self, reply, **kwargs):
        """
        Reply with a message directly to the user who invoked bot.

        Behaves exactly like Bot.send() except channel is filled in for you.
        """
        return await self.bot.send(self.msg.channel, reply, **kwargs)

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
            f'For more information do: `{prefix}Command -h`',
            f'       Example: `{prefix}drop -h`',
            '',
        ]
        lines = [
            ['Command', 'Effect'],
            [f'{prefix}d5', 'Search on the D&D 5e wiki'],
            #  [f'{prefix}effect', 'Add an effect to a user in turn order'],
            #  [f'{prefix}e', 'Alias for `!effect`'],
            [f'{prefix}math', 'Do some math operations'],
            #  [f'{prefix}music', 'Play songs from youtube and server.'],
            [f'{prefix}m', 'Alias for `!math`'],
            [f'{prefix}n', 'Alias for `!turn --next`'],
            [f'{prefix}pf', 'Search on the Pathfinder wiki'],
            [f'{prefix}pf2', 'Search on the Pathfinder 2e wiki'],
            [f'{prefix}poni', 'Pony?!?!'],
            [f'{prefix}pun', 'Prepare for pain!'],
            [f'{prefix}roll', 'Roll a dice like: 2d6 + 5'],
            [f'{prefix}reroll', 'Reroll previous rolls'],
            [f'{prefix}r', 'Alias for `!roll`'],
            #  [f'{prefix}songs', 'Create manage song lookup.'],
            [f'{prefix}star', 'Search on the Starfinder wiki.'],
            [f'{prefix}status', 'Show status of bot including uptime'],
            [f'{prefix}timer', 'Set a timer for HH:MM:SS in future'],
            [f'{prefix}timers', 'See the status of all YOUR active timers'],
            [f'{prefix}turn', 'Manager turn order for pen and paper combat'],
            [f'{prefix}help', 'This help message'],
            [f'{prefix}o.o', 'Funny eyes ?!?'],
        ]

        response = '\n'.join(over) + dice.tbl.wrap_markdown(dice.tbl.format_table(lines, header=True))
        await self.reply(response, ttl=True)
        try:
            await self.msg.delete()
        except discord.Forbidden:
            logging.getLogger("dice.actions").error(
                "Bot missing manage messages permission. On: %s", str(self.msg.guild))


class Status(Action):
    """
    Display the status of this bot.
    """
    async def execute(self):
        lines = [
            ['Created By', 'GearsandCogs'],
            ['Uptime', self.bot.uptime],
            ['Version', f'{dice.__version__}'],
        ]

        await self.reply(dice.tbl.wrap_markdown(dice.tbl.format_table(lines)))


class Math(Action):
    """
    Perform one or more math operations.
    """
    async def execute(self):
        resp = ['__Math Calculations__', '']
        for line in ' '.join(self.args.spec).split(','):
            line = line.strip()
            if re.match(r'[^0-9 \(\)+-/*]', line):
                resp += [f"'{line}' looks suspicious. Allowed characters: 0-9 ()+-/*"]
                continue

            # FIXME: Dangerous, but re blocking anything not simple maths.
            resp += [line + " = " + str(eval(line))]

        await self.reply('\n'.join(resp))


class PF2Wiki(Action):
    """
    Search an OGN PF2 wiki site, now no longer with google CSE.
    """
    async def execute(self):
        msg = """Searching {}: **{}**
Top {} Results:\n\n{}"""
        terms = ' '.join(self.args.terms)
        match = re.match(r".*?([^a-zA-Z0-9 '-]+)", terms)
        if match:
            raise dice.exc.InvalidCommandArgs('No special characters in search please. ' + match.group(1))

        base_url = getattr(dice.actions, self.args.url)
        full_url = base_url.format(terms.replace(' ', '+'))
        with concurrent.futures.ProcessPoolExecutor(1) as pool:
            result = await self.bot.loop.run_in_executor(pool, get_pf2_results_background,
                                                         full_url, self.args.num)

        await self.reply(msg.format(self.args.wiki, terms, self.args.num, result))


class SearchWiki(Action):
    """
    Search an OGN wiki site based on their google custom search URL.
    """
    async def execute(self):
        msg = """Searching {}: **{}**
Top {} Results:\n\n{}"""
        terms = ' '.join(self.args.terms)
        match = re.match(r".*?([^a-zA-Z0-9 '-]+)", terms)
        if match:
            raise dice.exc.InvalidCommandArgs('No special characters in search please. ' + match.group(1))

        base_url = getattr(dice.actions, self.args.url)
        full_url = base_url.format(terms.replace(' ', '%20'))
        with concurrent.futures.ProcessPoolExecutor(1) as pool:
            result = await self.bot.loop.run_in_executor(pool, get_cse_google_results_background,
                                                         full_url, self.args.num)

        await self.reply(msg.format(self.args.wiki, terms, self.args.num, result))


class Poni(Action):
    """
    Poni command.
    API Reference: https://derpibooru.org/pages/api
    """
    async def execute(self):
        page_ind, img_ind = 0, 0
        msg = "No images found!"

        tags = re.split(r'\s*,\s*|\s*,|,s*', self.msg.content.replace(self.bot.prefix + 'poni ', ''))
        full_tag = "?q=" + "%2C".join(tags).replace(" ", "+")
        full_url = os.path.join(PONI_JSON, "search", "images", full_tag)
        logging.getLogger(__name__).info("Poni retrieving: %s", full_url)

        async with aiohttp.ClientSession() as session:
            async with session.get(full_url) as resp:
                resp_text = await resp.text()
                total_imgs = json.loads(resp_text)['total']

            if total_imgs == 1:
                page_ind, img_ind = 1, 0
            elif total_imgs:
                total_ind = rand.randint(0, total_imgs - 1)
                page_ind = math.ceil(total_ind / PONI_PER_PAGE + 0.01)
                img_ind = (total_ind) % PONI_PER_PAGE

            if page_ind:
                full_url += f'&page={page_ind}&per_page={PONI_PER_PAGE}'
                self.log.info("Selecting page %d index %d of %s", page_ind, img_ind, full_url)
                async with session.get(full_url) as resp:
                    resp_json = json.loads(await resp.text())
                    msg = resp_json['images'][img_ind]['representations']['full']

        await self.reply(msg)


class Roll(Action):
    """
    Perform one or more rolls of dice according to spec.
    """
    async def execute(self):
        update_rolls = False
        full_spec = ' '.join(self.args.spec).strip()
        msg = ''

        if self.args.save:
            #  await dicedb.query.ensure_duser(self.db, self.discord_id, self.msg.author.name)
            await dicedb.query.update_saved_roll(self.db, self.discord_id, self.args.save, full_spec)

            msg = f"Added roll: __**{self.args.save}**__: {full_spec}"

        elif self.args.list:
            rolls = await dicedb.query.find_all_saved_rolls(self.db, self.discord_id)
            resp = ['__**Saved Rolls**__:', '']
            resp += [f"__{roll['name']}__: {roll['roll']}" for roll in rolls]

            msg = '\n'.join(resp)

        elif self.args.remove:
            await dicedb.query.remove_saved_roll(self.db, self.discord_id, self.args.remove)

            msg = f"Removed roll: __**{self.args.remove}**__"

        else:
            resp = ['__Dice Rolls__', '']
            if full_spec == '':
                raise dice.exc.InvalidCommandArgs('A roll requires some text!')

            saved_roll = await dicedb.query.find_saved_roll(self.db, self.discord_id, full_spec)
            if saved_roll:
                full_spec = saved_roll['roll']
                resp = [f"__Dice Rolls__ ({saved_roll['name']})", '']

            resp += await make_rolls(full_spec)
            msg = '\n'.join(resp)
            update_rolls = True

        if self.msg.mentions:
            for member in set(self.msg.mentions + [self.msg.author]):
                await member.send(msg)
        else:
            await self.reply(msg)

        if update_rolls:
            entries = [{'roll': full_spec, 'result': ''}]
            await dicedb.query.add_roll_history(self.db, self.discord_id, entries=entries)


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

        self.last_msgs = []
        end_offset = parse_time_spec(self.args.time)
        self.start = datetime.datetime.utcnow()
        self.end = self.start + datetime.timedelta(seconds=end_offset)
        self.triggers = self.calc_triggers(end_offset)

    def __str__(self):
        """ Provide a friendly summary for users. """
        diff = self.end - datetime.datetime.utcnow()
        diff = diff - datetime.timedelta(microseconds=diff.microseconds)

        return f"""{self.description}
        __Started__ {self.start.replace(microsecond=0)}
        __Ends at {self.end.replace(microsecond=0)}
        __Remaining__ {diff}
        """

    def __repr__(self):
        keys = ['description', 'start', 'end', 'last_msgs', 'triggers']
        kwargs = [f'{key}={getattr(self, key)!r}' for key in keys]

        return f"Timer({', '.join(kwargs)})"

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
        msg = f"{self.msg.author.mention}: Timer '{self.description}'"

        if self.args.offsets is None:
            self.args.offsets = TIMER_OFFSETS
        offsets = sorted([-parse_time_spec(x) for x in self.args.offsets])
        offsets = [x for x in offsets if end_offset + x > 0]  # validate offsets applicable

        triggers = []
        for offset in offsets:
            trigger = self.end + datetime.timedelta(seconds=offset)
            triggers.append([trigger, msg + f" has {self.end - trigger} time remaining!"])

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
        if self.last_msgs:
            try:
                for msg in self.last_msgs:
                    await msg.delete()
            except discord.Forbidden:
                logging.getLogger("dice.actions").error("Bot missing manage messages permission. On: %s",
                                                        str(self.msg.guild))

        self.last_msgs = await self.reply(new_msg)

    async def execute(self):
        TIMERS[self.key] = self
        self.last_msgs = await self.reply("Starting timer for: " + self.args.time)


class TimersMenu(dice.util.PagingMenu):
    """
    Manage the timers the user has active.
    """
    def menu(self):
        header = f"""**Timers Management**
Page {self.page}/{self.total_pages}
Select a timer to cancel from [1..{len(self.cur_entries)}]:

"""
        return header + timer_summary(TIMERS, self.msg.author.name) + dice.util.PAGING_FOOTER

    async def handle_msg(self, user_select):
        choice = int(user_select.content) - 1
        if choice < 0 or choice >= len(self.cur_entries):
            raise ValueError

        try:
            del TIMERS[self.cur_entries[choice]]
            del self.cur_entries[choice]
        except (KeyError, ValueError):
            pass

        return False


class Timers(Action):
    """
    Show a users own timers.
    """
    async def execute(self):
        if self.args.clear:
            for key_to_remove in [x for x in TIMERS if self.msg.author.name in x]:
                del TIMERS[key_to_remove]
            await self.reply("Your timers have been cancelled.")
        elif self.args.manage:
            entries = [x for x in TIMERS if self.msg.author.name in x]
            await TimersMenu(self, entries).run()
        else:
            await self.reply(timer_summary(TIMERS, self.msg.author.name))


class Turn(Action):
    """
    Manipulate a turn order tracker.
    """
    async def add(self, client, tracker):
        """
        Add users to an existing turn order,
        start a new turn order if needed.
        """
        try:
            chars = [x.strip() for x in ' '.join(self.args.chars).split(',')]
        except ValueError as exc:
            raise dice.exc.InvalidCommandArgs("Please check format of command.") from exc

        if tracker:
            dice.turn.combat_tracker_add_chars(tracker, chars)
        else:
            tracker = dice.turn.combat_tracker_generate(discord_id=self.discord_id, channel_id=self.chan_id, chars=chars)
        await dicedb.query.update_turn_order(client, discord_id=self.discord_id,
                                             channel_id=self.chan_id, combat_tracker=tracker)

        return 'Added to the tracker: ' + ', '.join([x[:x.index('/')] for x in chars])

    async def clear(self, client, _):
        """
        Clear the turn order.
        """
        await dicedb.query.remove_turn_order(client, discord_id=self.discord_id, channel_id=self.chan_id)
        return 'Combat tracker cleared.'

    async def next(self, client, tracker):
        """
        Advance the turn order next places.
        """
        if self.args.steps == 'zero':
            self.args.steps = 1

        tracker = dice.turn.combat_tracker_move(tracker, self.args.steps)
        await dicedb.query.update_turn_order(client, discord_id=self.discord_id,
                                             channel_id=self.chan_id, combat_tracker=tracker)
        turn = tracker['turns'][0]
        return f"**Next User**\n{turn['name']} ({turn['init']}): {turn['roll']}"

    async def remove(self, client, tracker):
        """
        Remove one or more users from turn order.
        """
        try:
            chars = [x.strip() for x in ' '.join(self.args.chars).split(',')]
        except ValueError as exc:
            raise dice.exc.InvalidCommandArgs("Please check format of command.") from exc

        dice.turn.combat_tracker_remove_chars(tracker, chars)
        await dicedb.query.update_turn_order(client, discord_id=self.discord_id,
                                             channel_id=self.chan_id, combat_tracker=tracker)

        return 'Removed from the tracker: ' + ', '.join(chars)

    async def update(self, client, tracker):
        """
        Update one or more character's init for this turn order.
        Usually used for some spontaneous change or DM decision.
        """
        changed = False

        try:
            chars = [x.strip().split('/') for x in ' '.join(self.args.chars).split(',')]
            for name, roll in chars:
                found = [x for x in tracker['turns'] if x['name'].lower() == name.lower()]
                if found:
                    changed = True
                    found[0]['roll'] = float(roll)

        except ValueError as exc:
            raise dice.exc.InvalidCommandArgs("Please check format of command.") from exc

        if changed:
            await dicedb.query.update_turn_order(client, discord_id=self.discord_id,
                                                 channel_id=self.chan_id, combat_tracker=tracker)

        return "Updated characters with new inits."

    async def execute(self):
        tracker = await dicedb.query.get_turn_order(self.db, discord_id=self.discord_id, channel_id=self.chan_id)
        if self.args.subcmd == 'n':
            self.args.subcmd = 'next'

        try:
            msg = await getattr(self, self.args.subcmd)(self.db, tracker)
        except TypeError:
            if tracker:
                msg = dice.turn.combat_tracker_format(tracker)
            else:
                raise dice.exc.InvalidCommandArgs("No combat has begun!")

        await self.reply(msg)


#  class Effect(Action):
    #  """
    #  Manage effects for users in the turn order.
    #  """
    #  @staticmethod
    #  def add(chars, new_effects):
        #  """
        #  Add recurring effects to characters in the turn order.

        #  Args:
            #  chars: The TurnOrder characters to modify.
            #  new_effects: The new effects to apply to them.
        #  """
        #  msg = ''
        #  for char in chars:
            #  for new_effect in new_effects:
                #  try:
                    #  char.add_effect(new_effect[0], int(new_effect[1]))
                    #  msg += '{}: Added {} for {} turns.\n'.format(char.name, new_effect[0], new_effect[1])
                #  except (IndexError, ValueError):
                    #  raise dice.exc.InvalidCommandArgs("Invalid round count for effect.")

        #  return msg

    #  @staticmethod
    #  def remove(chars, new_effects):
        #  """
        #  Remove recurring effects from characters in turn order.

        #  Args:
            #  chars: The TurnOrder characters to modify.
            #  new_effects: The effects to remove from them.
        #  """
        #  msg = ''
        #  for char in chars:
            #  for new_effect in new_effects:
                #  char.remove_effect(new_effect[0])
                #  msg += '{}: Removed {}.\n'.format(char.name, new_effect[0])

        #  return msg

    #  @staticmethod
    #  def update(chars, new_effects):
        #  """
        #  Update recurring effects on characters in turn order.

        #  Args:
            #  chars: The TurnOrder characters to modify.
            #  new_effects: The effects to update,
                         #  should be textual match to original name with different turn count.
        #  """
        #  msg = ''
        #  for char in chars:
            #  for new_effect in new_effects:
                #  try:
                    #  char.update_effect(new_effect[0], int(new_effect[1]))
                    #  msg += '{}: Updated {} for {} turns.\n'.format(char.name, new_effect[0], new_effect[1])
                #  except (IndexError, ValueError):
                    #  raise dice.exc.InvalidCommandArgs("Invalid round count for effect.")

        #  return msg

    #  async def execute(self):
        #  order = dice.turn.parse_order(dicedb.query.get_turn_order(self.session, self.chan_id))
        #  if not order:
            #  raise dice.exc.InvalidCommandArgs('No turn order set to add effects.')

        #  targets = [target.lstrip() for target in ' '.join(self.args.targets).split(',')
                   #  if target.lstrip()]
        #  chars = [user for user in order.users if user.name in targets]

        #  msg = '__Characters With Effects__\n\n'
        #  for char in order.users:
            #  if char.effects:
                #  msg += '{}\n\n'.format(char)

        #  effects_args = None
        #  for name in ['add', 'remove', 'update']:
            #  effects_args = getattr(self.args, name)
            #  if effects_args:
                #  new_effects = [x.strip().split('/') for x in (' '.join(effects_args)).split(',')]
                #  msg = getattr(self.__class__, name)(chars, new_effects)
                #  break

        #  if targets and not effects_args:
            #  msg = 'No action selected for targets [--add|--remove|--update].'

        #  dicedb.query.update_turn_order(self.session, self.chan_id, order)

        #  await self.reply(msg)


class PunMenu(dice.util.PagingMenu):
    """
    Manage the puns in the database.
    """
    def menu(self):
        header = f"""**Pun Management**
Page {self.page}/{self.total_pages}
Select a pun to remove by number [1..{len(self.cur_entries)}]:


"""
        return format_pun_list(header, self.cur_entries, dice.util.PAGING_FOOTER, cnt=1)

    async def handle_msg(self, user_select):
        choice = int(user_select.content) - 1
        if choice < 0 or choice >= len(self.cur_entries):
            raise ValueError

        await dicedb.query.remove_pun(self.act.db, self.act.discord_id, self.cur_entries[choice]['text'])
        del self.cur_entries[choice]

        return True


class Pun(Action):
    """
    Manage puns for users.
    """
    async def execute(self):
        if self.args.add:
            text = ' '.join(self.args.add)
            await dicedb.query.add_pun(self.db, self.discord_id, text)

            msg = 'Pun added to the abuse database.'

        elif self.args.manage:
            entries = await dicedb.query.get_all_puns(self.db, self.discord_id)
            await PunMenu(self, entries['puns']).run()

            msg = 'Pun abuse management terminated.'

        else:
            msg = '**Randomly Selected Pun**\n\n'
            msg += await dicedb.query.randomly_select_pun(self.db, self.discord_id)

        await self.reply(msg)


class Googly(Action):
    """
    Track amazing googly eyes.
    """
    async def execute(self):
        googly = await dicedb.query.get_googly(self.db, self.discord_id)

        if self.args.set:
            googly['total'] = max(self.args.set, 0)
        if self.args.used:
            googly['used'] = max(self.args.used, 0)
        if self.args.offset:
            googly['total'] = max(googly['total'] + self.args.offset, 0)
            if self.args.offset < 0:
                googly['used'] = max(googly['used'] - self.args.offset, 0)

        await dicedb.query.update_googly(self.db, googly)
        await self.reply(f"Googlies: left {googly['total']}, used: {googly['used']}")


class RerollMenu(dice.util.PagingMenu):
    """
    Select a youtube video to play from search results.
    """
    def menu(self):
        msg = f"""**Last {LIMIT_REROLLS} Rolls**
Page {self.page}/{self.total_pages}
Select a roll by number [1..{len(self.cur_entries)}]:

"""

        for cnt, entry in enumerate(self.cur_entries, start=1):
            msg += f"    {cnt}) {entry['roll']}\n"
        msg = msg.rstrip()
        msg += dice.util.PAGING_FOOTER

        return msg

    async def handle_msg(self, user_select):
        choice = int(user_select.content) - 1
        if choice < 0 or choice >= len(self.cur_entries):
            raise ValueError

        return self.cur_entries[choice]


class Reroll(Action):
    """
    Reoll the last n commands.
    """
    async def execute(self):
        rolls = await dicedb.query.get_roll_history(self.db, self.discord_id)

        if not rolls['history']:
            raise dice.exc.InvalidCommandArgs("No rolls stored, make a !roll first.")

        if self.args.menu:
            selected = await RerollMenu(self, list(reversed(rolls['history'])), LIMIT_REROLLS_PER_PAGE).run()
            if not selected:
                return
        else:
            try:
                if self.args.offset > -1:
                    raise IndexError
                selected = list(reversed(rolls['history']))[self.args.offset]
            except IndexError as exc:
                raise dice.exc.InvalidCommandArgs(f"Please select a negative offset from : [-1, -{LIMIT_REROLLS}]") from exc

        msg = "**Reroll Result**\n\n" + '\n'.join(await make_rolls(selected['roll']))
        await self.reply(msg)


class Movies(Action):
    """
    Managed the movies list, a means of tracking things to watch later.
    """
    async def execute(self):
        arg_movies, msg = [], "__Movies__\n\n"
        arg_movies = []
        if self.args.sub in ['add', 'remove', 'set']:
            arg_movies = [x.strip() for x in ' '.join(self.args.movies).split(',') if x]

        list_obj = await dicedb.query.get_list(self.db, self.discord_id, 'Movies')
        if self.args.sub == 'add':
            await dicedb.query.add_list_entries(self.db, self.discord_id, 'Movies', arg_movies)
            msg += "Added:\n\n" + '\n'.join(arg_movies)

        elif self.args.sub == 'remove':
            await dicedb.query.remove_list_entries(self.db, self.discord_id, 'Movies', arg_movies)
            msg += "Removed:\n\n" + '\n'.join(arg_movies)

        elif self.args.sub == 'set':
            await dicedb.query.replace_list_entries(self.db, self.discord_id, 'Movies', arg_movies)
            msg += "Replaced list:\n\n" + '\n'.join(arg_movies)

        elif self.args.sub == 'roll':
            if len(list_obj['entries']) < 1:
                raise dice.exc.InvalidCommandArgs("No movies in the current list.")

            limit = max(self.args.num, 1)
            if limit > len(list_obj['entries']):
                limit = len(list_obj['entries'])

            roll = rand.randint(0, limit)
            selected = list_obj['entries'][roll]
            await dicedb.query.remove_list_entries(self.db, self.discord_id, 'Movies', [selected])

            msg += f"Rolled: {roll + 1}, selected: {selected}"

        else:
            if self.args.short:
                msg += ", ".join(list_obj['entries'])
            else:
                msg += "\n".join([f"{ind}) {movie}" for ind, movie in enumerate(list_obj['entries'], 1)])

        await self.reply(msg)


#  class Music(Action):
    #  """
    #  Transparent mapper from user input onto the music player.
    #  """
    #  @staticmethod
    #  async def make_videos(arg_vids):
        #  """
        #  Preprocess the arguments and return a list of valid videos
        #  the player can handle.

        #  Args:
            #  arg_vids: The args.vids list of arguments from user.

        #  Returns:
            #  A list of valid Song objects that can be played.
        #  """
        #  parts = [part.strip() for part in re.split(r'\s*,\s*', ' '.join(arg_vids))]

        #  if dice.util.is_valid_playlist(parts[0]):
            #  vid_info = await dice.music.get_yt_info(parts[0])
            #  new_vids = dicedb.query.validate_videos([x[0] for x in vid_info])
            #  for vid in new_vids:
                #  _, title = vid_info[0]
                #  vid_info = vid_info[1:]
                #  vid.name = title[:30]
        #  else:
            #  new_vids = dicedb.query.validate_videos(parts)

        #  return new_vids

    #  async def clear(self, mplayer):
        #  """ Clear all Songs from current queue, implies player stopping. """
        #  await mplayer.disconnect()
        #  mplayer.set_vids([])
        #  return "Player has stopped and the queue is clear.\n\nPlay something new or browse songs."

    #  async def dedupe(self, mplayer):
        #  """ Clear all Songs from current queue, implies player stopping. """
        #  count = mplayer.dedupe()
        #  return "{} songs have been removed.\n\n".format(count) + str(mplayer)

    #  async def restart(self, mplayer):
        #  """ Restart the player at the beginning. """
        #  mplayer.reset_iterator()
        #  mplayer.play()
        #  return "__**Now Playing**__\n\n{}".format(mplayer.cur_vid)

    #  async def stop(self, mplayer):
        #  """ Stop the player. """
        #  await mplayer.disconnect()
        #  return "Player has been stopped.\n\nRestart it or play other vids to continue."

    #  async def pause(self, mplayer):
        #  """ Pause the player. """
        #  if mplayer.is_paused():
            #  msg = "The player is already paused."
        #  elif mplayer.is_playing():
            #  mplayer.pause()
            #  msg = """To resume playing: `!music resume`
#  To stop playing entirely: `!music stop`"""
        #  else:
            #  msg = "The bot cannot be paused at this time."

        #  return "Player is: {}\n\n{}".format(mplayer.state, msg)

    #  async def resume(self, mplayer):
        #  """ Resume the player from stopped or paused. """
        #  if mplayer.is_paused():
            #  mplayer.resume()
            #  msg = str(mplayer)
        #  elif not mplayer.is_done():
            #  mplayer.play()
            #  msg = str(mplayer)
        #  else:
            #  msg = "The bot cannot resume at this time.\nIf queue is finished restart it or choose new songs."

        #  return "Player is: **{}**\n\n{}".format(mplayer.state, msg)

    #  async def next(self, mplayer):
        #  """ Play the next video. """
        #  try:
            #  mplayer.next()
            #  mplayer.play()
            #  return "__**Now Playing**__\n\n{}".format(mplayer.cur_vid)
        #  except StopIteration:
            #  return "Queue finished. Stopping."

    #  async def prev(self, mplayer):
        #  """ Play the previous video. """
        #  try:
            #  mplayer.prev()
            #  mplayer.play()
            #  return "__**Now Playing**__\n\n{}".format(mplayer.cur_vid)
        #  except StopIteration:
            #  return "Queue finished. Stopping."

    #  async def repeatqueue(self, mplayer):
        #  """ Set player to loop to beginning. """
        #  mplayer.repeat_all = not mplayer.repeat_all
        #  msg = "Player will stop playing after last song in list."
        #  if mplayer.repeat_all:
            #  msg = "Player will return to and play first song after finishing list."

        #  return msg

    #  async def repeat(self, mplayer):
        #  """ Set player to repeat video when it finishes normally. """
        #  mplayer.cur_vid.repeat = not mplayer.cur_vid.repeat
        #  msg = "Current video {} will **NO** longer repeat.".format(mplayer.cur_vid.name)
        #  if mplayer.cur_vid.repeat:
            #  msg = "Current video {} **will** repeat.\n\nAdvance list with '--next'.".format(mplayer.cur_vid.name)

        #  return msg

    #  async def shuffle(self, mplayer):
        #  """ Set player to repeat video when it finishes normally. """
        #  mplayer.toggle_shuffle()
        #  mplayer.play()
        #  return "Player shuffle is now: **{}abled**".format('En' if mplayer.shuffle else 'Dis')

    #  async def status(self, mplayer):
        #  """ Show current bot status. """
        #  return str(mplayer)

    #  async def volume(self, mplayer):
        #  """ Set the volume for current song. """
        #  mplayer.set_volume(self.args.volume)
        #  msg = "Player volume: {}/100".format(mplayer.cur_vid.volume_int)
        #  await self.reply(msg)

    #  async def add(self, mplayer):
        #  """ Append to the end of the queue. """
        #  new_vids = await self.__class__.make_videos(self.args.vids)
        #  mplayer.append_vids(new_vids)
        #  await self.reply(str(mplayer))

    #  async def play(self, mplayer):
        #  """ Start playing or replace entire playlist. """
        #  new_vids = await self.__class__.make_videos(self.args.vids)
        #  mplayer.set_vids(new_vids)
        #  await self.reply(str(mplayer))
        #  mplayer.play()

    #  replace = play

    #  async def execute(self):
        #  mplayer = get_guild_player(self.guild_id, self.msg)
        #  await mplayer.join_voice_channel()

        #  if not getattr(self.args, 'sub'):
            #  self.args.sub = 'status'

        #  try:
            #  msg = await getattr(self, self.args.sub)(mplayer)
        #  except dice.exc.RemoteError as exc:
            #  msg = str(exc)
        #  if msg:
            #  await self.reply(msg)

        #  if mplayer.cur_vid and mplayer.cur_vid.id and self.args.sub in ['repeat', 'volume']:
            #  song = dicedb.query.get_song_by_id(self.session, mplayer.cur_vid.id)
            #  song.update(mplayer.cur_vid)
            #  self.session.add(song)
            #  self.session.commit()


#  class SongRemoval(dice.util.PagingMenu):
    #  """
    #  Generate the management interface for removing songs from db.
    #  """
    #  def menu(self):
        #  header = """**Remove Songs**
#  Page {}/{}
#  Select a song to remove by number [1..{}]:

#  """.format(self.page, self.total_pages, len(self.cur_entries))
        #  return format_song_list(header, self.cur_entries, dice.util.PAGING_FOOTER)

    #  async def handle_msg(self, user_select):
        #  choice = int(user_select.content) - 1
        #  if choice < 0 or choice >= len(self.cur_entries):
            #  raise ValueError

        #  dicedb.query.remove_song_with_tags(self.act.session, self.cur_entries[choice].name)
        #  del self.cur_entries[choice]
        #  await self.reply("**Song Deleted**\n\n    {}".format(self.cur_entries[choice].name))

        #  return False


#  class SelectTag(dice.util.PagingMenu):
    #  """
    #  Select a tag to play all songs with tag or fursther select a single song from.
    #  """
    #  def menu(self):
        #  menu = """**Select A Tag**
#  Page {}/{}
#  Select a tag from blow to play or explore further:

#  """.format(self.page, self.total_pages)
        #  for ind, tag in enumerate(self.cur_entries, start=1):
            #  tagged_songs = dicedb.query.get_songs_with_tag(self.act.session, tag)
            #  menu += '        **{}**) {} ({} songs)\n'.format(ind, tag, len(tagged_songs))
        #  menu = menu.rstrip() + dice.util.PAGING_FOOTER
        #  menu += """Type __all 1__ to play all songs with tag 1
#  Type __list__ to go select by song list"""

        #  return menu

    #  async def handle_msg(self, user_select):
        #  if user_select.content == 'list':
            #  entries = dicedb.query.get_song_choices(self.act.session)
            #  asyncio.ensure_future(SelectSong(self.act, entries).run())
            #  return True

        #  choice = int(user_select.content.replace('all', '')) - 1
        #  if choice < 0 or choice >= len(self.cur_entries):
            #  raise ValueError

        #  songs = dicedb.query.get_songs_with_tag(self.act.session, self.cur_entries[choice])
        #  if 'all' in user_select.content:
            #  mplayer = get_guild_player(self.act.guild_id, self.msg)
            #  self.msgs += await self.reply('Appending new selection(s) to playlist. Select another or exit.')
            #  mplayer.append_vids(songs)
            #  await self.reply(str(mplayer))
            #  if not mplayer.is_playing():
                #  mplayer.play()
        #  else:
            #  await SelectSong(self.act, songs).run()
            #  return True

        #  return False


#  class SelectSong(dice.util.PagingMenu):
    #  """
    #  Select a song from a list of tags provided.
    #  """
    #  def menu(self):
        #  header = """**Select A Song**
#  Page {}/{}
#  Select a song to play by number [1..{}]:

#  """.format(self.page, self.total_pages, len(self.cur_entries))
        #  menu = format_song_list(header, self.cur_entries, dice.util.PAGING_FOOTER)
        #  menu += 'Type __tags__ to go select by tags'

        #  return menu

    #  async def handle_msg(self, user_select):
        #  if user_select.content == 'tags':
            #  entries = dicedb.query.get_tag_choices(self.act.session)
            #  asyncio.ensure_future(SelectTag(self.act, entries, LIMIT_TAGS).run())
            #  return True

        #  choice = int(user_select.content) - 1
        #  if choice < 0 or choice >= len(self.cur_entries):
            #  raise ValueError
        #  selected = self.cur_entries[choice]

        #  self.msgs += await self.reply('Appending new selection(s) to playlist. Select another or exit.')
        #  mplayer = get_guild_player(self.act.guild_id, self.act.msg)
        #  mplayer.append_vids([selected])
        #  if not mplayer.is_playing():
            #  mplayer.play()

        #  return False


#  TODO: Need tests here
#  class Songs(Action):
    #  """
    #  Songs command, manages an internal database of songs to play.
    #  """
    #  def add(self, name, url, tags):
        #  """
        #  Add a song entry to the database and tags files.
        #  """
        #  return dicedb.query.add_song_with_tags(self.session, name, url, tags)

    #  def remove(self, name):
        #  """
        #  Remove an entry based on its key in the songs file.
        #  """
        #  dicedb.query.remove_song_with_tags(self.session, name)

    #  async def list(self):
        #  """
        #  List all entries in the song db. Implements a paging like interface.
        #  """
        #  entries = dicedb.query.get_song_choices(self.session)
        #  await SelectSong(self, entries, LIMIT_SONGS).run()

    #  async def manage(self):
        #  """
        #  Using paging interface similar to list, allow management of song db.
        #  """
        #  entries = dicedb.query.get_song_choices(self.session)
        #  await SongRemoval(self, entries, LIMIT_SONGS).run()

    #  async def select_tag(self):
        #  """
        #  Use the Songs db to lookup dynamically based on tags.
        #  """
        #  entries = dicedb.query.get_tag_choices(self.session)
        #  await SelectTag(self, entries, LIMIT_TAGS).run()

    #  async def search_names(self, term):
        #  """
        #  Search for a name across key entries in the song db.
        #  """
        #  reply = '**__Songs DB__** - Searching Names for __{}__\n\n'.format(term)
        #  cnt = 1

        #  l_term = ' '.join(term).lower().strip()
        #  for song in dicedb.query.search_songs_by_name(dicedb.Session(), l_term):
            #  reply += song.format_menu(cnt)
            #  cnt += 1

        #  await self.reply(reply)

    #  async def search_tags(self, term):
        #  """
        #  Search loosely accross the tags.
        #  """
        #  reply = '**__Songs DB__** - Searching Tags for __{}__\n\n'.format(term)
        #  cnt = 1

        #  session = dicedb.Session()
        #  l_term = ' '.join(term).lower().strip()
        #  for tag in dicedb.query.get_tag_choices(session, l_term):
            #  reply += '__**{}**__\n'.format(tag)
            #  for song in dicedb.query.get_songs_with_tag(session, tag):
                #  reply += song.format_menu(cnt)
                #  cnt += 1
            #  reply += "\n"

        #  await self.bot.reply(reply)

    #  async def execute(self):
        #  await get_guild_player(self.guild_id, self.msg).join_voice_channel()

        #  if self.args.add:
            #  msg = self.msg.content.replace(self.bot.prefix + 'songs --add', '')
            #  msg = msg.replace(self.bot.prefix + 'songs -a', '')
            #  parts = re.split(r'\s*,\s*', msg)
            #  parts = [part.strip() for part in parts]
            #  name, url, tags = parts[0].lower(), parts[1], [x.lower() for x in parts[2:]]
            #  song = self.add(name, url, tags)

            #  reply = '__Song Added__\n\n' + song.format_menu(1)
            #  await self.reply(reply)
        #  if self.args.list:
            #  await self.list()
        #  elif self.args.manage:
            #  await self.manage()
        #  elif self.args.play:
            #  await self.select_tag()
        #  elif self.args.search:
            #  await self.search_names(self.args.search)
        #  elif self.args.tag:
            #  await self.search_tags(self.args.tag)


#  class YTMenu(dice.util.PagingMenu):
    #  """
    #  Select a youtube video to play from search results.
    #  """
    #  def menu(self):
        #  cnt = 1
        #  msg = """**Youtube Search**
#  Page {}/{}
#  Select a song to play by number [1..{}]:


#  """.format(self.page, self.total_pages, len(self.cur_entries))

        #  for result in self.cur_entries:
            #  msg += """    {cnt}) **{title}**    <{url}>
        #  __Time__ {duration}    __Views__ {views}
#  """.format(cnt=cnt, **result)
            #  cnt += 1
        #  msg = msg.rstrip()
        #  msg += dice.util.PAGING_FOOTER

        #  return msg

    #  async def handle_msg(self, user_select):
        #  choice = int(user_select.content) - 1
        #  if choice < 0 or choice >= len(self.cur_entries):
            #  raise ValueError

        #  selected = self.cur_entries[choice]
        #  videos = dicedb.query.validate_videos([selected['url']])
        #  videos[0].name = selected['title'][:30]

        #  mplayer = get_guild_player(self.act.guild_id, self.msg)
        #  mplayer.append_vids(videos)
        #  self.msgs += await self.reply('Appending new selection(s) to playlist. Select another or exit.')

        #  return False


#  class YTSearch(Action):
    #  """
    #  Search youtube for videos to play.
    #  """
    #  async def execute(self):
        #  terms = [re.subn(r'[^a-z0-9\',.]+', '', term)[0] for term in self.args.terms]

        #  entries = await dice.music.yt_search(terms)
        #  mplayer = get_guild_player(self.guild_id, self.msg)
        #  if self.args.first:
            #  videos = dicedb.query.validate_videos([entries[0]['url']])
            #  videos[0].name = entries[0]['title']

            #  mplayer.append_vids(videos)
            #  await self.reply('Appending first match to playlist. ' + videos[0].name)
        #  else:
            #  await YTMenu(self, entries, 6).run()


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
    msg = f"Active timers for __{name}__:\n\n"

    user_timers = [x for x in timers.values() if name in x.key]
    if user_timers:
        for ind, timer in enumerate(user_timers, start=1):
            msg += f"  **{ind}**) {timer}"
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
    except (IndexError, ValueError) as exc:
        if secs == 0:
            raise dice.exc.InvalidCommandArgs("I can't understand time spec! Use format: **HH:MM:SS**") from exc

    return secs


def format_pun_list(header, entries, footer, *, cnt=1):
    """
    Generate the management list of entries.
    """
    msg = header
    for ent in entries:
        msg += f"{cnt}) {ent['text']}\n    Hits: {ent['hits']:4d}\n\n"
        cnt += 1
    msg = msg.rstrip()
    msg += footer

    return msg


#  def format_song_list(header, songs, footer, *, cnt=1):
    #  """
    #  Generate the management list of songs.
    #  """
    #  msg = header
    #  for song in songs:
        #  msg += song.format_menu(cnt)
        #  cnt += 1
    #  msg = msg.rstrip()
    #  msg += footer

    #  return msg


def get_cse_google_results_background(full_url, num):
    """
    Fetch the top num results from full_url (a GCS page).
    """
    with dice.util.get_chrome_driver(dev=False) as browser:
        browser.get(full_url)

        result = ''
        for ele in browser.find_elements(By.CLASS_NAME, 'gsc-thumbnail-inside')[:num]:
            link_text = ele.find_element(By.CSS_SELECTOR, 'a.gs-title').get_property('href')
            result += f'{ele.text}\n      <{link_text}>\n'

    return result.rstrip()


def get_pf2_results_background(full_url, num):
    """
    Fetch the top num results from full_url (a GCS page).
    """
    with dice.util.get_chrome_driver(dev=False) as browser:
        browser.get(full_url)

        result = ''
        soup = bs4.BeautifulSoup(browser.page_source, 'html.parser')
        try:
            for ele in soup.find_all('article')[:num]:
                result += f"{ele.h2.a.text}\n      <{ele.h2.a.get('href')}>\n"
        except AttributeError:
            result = "No results!"

    return result.rstrip()


def throw_in_pool(throw):  # pragma: no cover
    """
    Simple wrapper to init random in other process before throw.
    """
    return throw.next()


async def make_rolls(spec):
    """
    Take a specification of dice rolls and return a string.
    This function will process additional modifiers to normal dice spec.
        4: d20 + 8, d8 + 2 -> Will roll 4 times d20 + 8 followed by d8 + 2.
    """
    loop = asyncio.get_event_loop()
    jobs = []
    with concurrent.futures.ProcessPoolExecutor(initializer=dice.util.seed_random) as pool:
        for line in re.split(r's*,\s+', spec):
            line = line.strip()
            times = 1

            if ':' in line:
                parts = line.split(':')
                times, line = int(parts[0]), parts[1].strip()
                if times > LIMIT_ROLL_TIMES:
                    raise dice.exc.InvalidCommandArgs(f"Please run <= {LIMIT_ROLL_TIMES} times a dice roll.")

            try:
                throw = dice.roll.parse_dice_line(line)
                jobs += [loop.run_in_executor(pool, throw_in_pool, throw) for _ in range(times)]
            except ValueError as exc:
                raise dice.exc.InvalidCommandArgs(str(exc))

        try:
            lines = await asyncio.wait_for(asyncio.gather(*jobs), ROLL_TIMEOUT)
        except concurrent.futures.TimeoutError:
            lines = ["Timeout! One or more of the dice took too long computing."]

    return lines


#  def get_guild_player(guild_id, msg):
    #  """
    #  Get the guild player for a guild.
    #  Current model assumes bot can maintain separate streams for each guild.
    #  """
    #  try:
        #  text = msg.channel
        #  voice = msg.author.voice.channel
    #  except AttributeError:
        #  voice = discord.utils.find(lambda x: isinstance(x, discord.VoiceChannel),
                                   #  msg.guild.channels)

    #  if guild_id not in PLAYERS:
        #  PLAYERS[guild_id] = GuildPlayer(vids=[], voice_channel=voice, text_channel=text)
    #  PLAYERS[guild_id].voice_channel = voice
    #  PLAYERS[guild_id].text_channel = text

    #  return PLAYERS[guild_id]
