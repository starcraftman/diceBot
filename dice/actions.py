"""
To facilitate complex actions based on commands create a
hierarchy of actions that can be recombined in any order.
All actions have async execute methods.
"""
from __future__ import absolute_import, print_function
import asyncio
import functools
import logging
import random
import re
import sys

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
# TODO: Store on start, remove on finish. Add listing timers command.
TIMERS = {}


async def bot_shutdown(bot, delay=30):  # pragma: no cover
    """
    Shutdown the bot. Not ideal, I should reconsider later.
    """
    await asyncio.sleep(delay)
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
            ['{prefix}roll', 'Roll a dice like: 2d6 + 5'],
            ['{prefix}r', 'Alias for `!roll`'],
            ['{prefix}status', 'Show status of bot including uptime'],
            ['{prefix}timer', 'Set a timer for HH:MM:SS in future'],
            ['{prefix}help', 'This help message'],
        ]
        lines = [[line[0].format(prefix=prefix), line[1]] for line in lines]

        response = '\n'.join(over) + dice.tbl.wrap_markdown(dice.tbl.format_table(lines, header=True))
        await self.bot.send_ttl_message(self.msg.channel, response)
        await self.bot.delete_message(self.msg)


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


# TODO: Properly fill in data on creation.
# TODO: Allow users to override the amount/timing of warnings.
class Timer(Action):
    """
    Display the status of this bot.
    """
    def __self__(self, user, start, end):
        self.user = user
        self.start = start
        self.end = end

    async def execute(self):
        if not re.match(r'[0-9:]+', self.args.time) or self.args.time.count(':') > 2:
            raise dice.exc.InvalidCommandArgs("I can't understand time spec! Use format: **HH:MM:SS**")
        t_spec = self.args.time.split(':')
        t_spec.reverse()

        try:
            secs = 0
            secs += int(t_spec[0])
            secs += int(t_spec[1]) * 60
            secs += int(t_spec[2]) * 3600
        except (IndexError, ValueError):
            if secs == 0:
                raise dice.exc.InvalidCommandArgs("I can't understand time spec! Use format: **HH:MM:SS**")

        timers = []
        ping = "{} Timer '{}'".format(self.msg.author.mention, self.args.time)
        if secs - 60 >= 0:
            timers += [[60, "{} has 60 seconds left!".format(ping)]]
            secs -= 60
        if secs - 240 >= 0:
            timers += [[240, "{} has 5 minutes left!".format(ping)]]
            secs -= 240
        if secs >= 0:
            timers += [[secs, "Timer '{}' was requested, I got this.".format(self.args.time)]]
        timers.reverse()
        timers += [[0, "{} has expired. Do something meatbag!".format(ping)]]

        sent_msg = None
        for time, msg in timers:
            if sent_msg:
                await self.bot.delete_message(sent_msg)
            sent_msg = await self.bot.send_message(self.msg.channel, msg)
            await asyncio.sleep(time)


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
