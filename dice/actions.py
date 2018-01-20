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


OP_DICT = {
    '__add__': '+',
    '__sub__': '-',
    '+': '__add__',
    '-': '__sub__',
}


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
            ['{prefix}m', 'Do some math operations'],
            ['{prefix}roll', 'Roll a dice like: 2d6 + 5'],
            ['{prefix}r', 'Roll a dice like: 2d6 + 5'],
            ['{prefix}status', 'Show status of bot including uptime'],
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
                resp += ["'{}' looks suspicious, I won't evaluate.\nI only allow: 0-9 ()+-/*".format(line)]
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
            throw = Throw(tokenize_dice_spec(line))
            resp += [line + " = {}".format(throw.throw())]

        await self.bot.send_message(self.msg.channel, '\n'.join(resp))


class Dice(object):
    def __init__(self, next_op=""):
        self.values = []
        self.next_op = next_op  # Either "__add__" or "__sub__"
        self.acu = ""  # Slot to accumulate text, used in reduction

    @property
    def num(self):
        return functools.reduce(lambda x, y: x + y, self.values)

    def __str__(self):
        trailing_op = ' {} '.format(OP_DICT[self.next_op]) if self.next_op else ""
        line = "({})".format(" + ".join([str(x) for x in self.values]))
        return line + trailing_op

    def __add__(self, other):
        if not isinstance(other, Dice):
            raise ValueError
        return FixedRoll(self.num + other.num, other.next_op)

    def __sub__(self, other):
        if not isinstance(other, Dice):
            raise ValueError
        return FixedRoll(self.num - other.num, other.next_op)

    def roll(self):
        raise NotImplementedError


class FixedRoll(Dice):
    def __init__(self, num, next_op=""):
        super().__init__(next_op)
        self.values = [int(num)]

    @property
    def spec(self):
        return str(self)

    def roll(self):
        return self.num


class DiceRoll(Dice):
    def __init__(self, spec, next_op=""):
        super().__init__(next_op)
        self.rolls, self.dice = parse_dice_spec(spec)

    @property
    def spec(self):
        return "({}d{})".format(self.rolls, self.dice)

    def roll(self):
        self.values = []
        for _ in range(self.rolls):
            self.values += [random.randint(1, self.dice)]

        return self.num


class DiceRollKeepHigh(DiceRoll):
    def __init__(self, spec, next_op=""):
        index = spec.index('kh')
        self.keep = int(spec[index + 2:])
        super().__init__(spec[:index], next_op)

    def __str__(self):
        trailing_op = ' {} '.format(OP_DICT[self.next_op]) if self.next_op else ""
        line = ''
        emphasize = sorted(self.values)[:-self.keep]

        for val in self.values:
            if val in emphasize:
                line += "~~{}~~ + ".format(val)
                emphasize.remove(val)
            else:
                line += "{} + ".format(val)

        return line[:-3] + trailing_op

    @property
    def spec(self):
        return "({}d{}kh{})".format(self.rolls, self.dice, self.keep)

    @property
    def num(self):
        vals = sorted(self.values)[-self.keep:]
        return functools.reduce(lambda x, y: x + y, vals)


class DiceRollKeepLow(DiceRoll):
    def __init__(self, spec, next_op=""):
        index = spec.index('kl')
        self.keep = int(spec[index + 2:])
        super().__init__(spec[:index], next_op)

    def __str__(self):
        trailing_op = ' {} '.format(OP_DICT[self.next_op]) if self.next_op else ""
        line = ''
        emphasize = sorted(self.values)[self.keep:]

        for val in self.values:
            if val in emphasize:
                line += "~~{}~~ + ".format(val)
                emphasize.remove(val)
            else:
                line += "{} + ".format(val)

        return line[:-3] + trailing_op

    @property
    def spec(self):
        return "({}d{}kl{})".format(self.rolls, self.dice, self.keep)

    @property
    def num(self):
        vals = sorted(self.values)[:self.keep]
        return functools.reduce(lambda x, y: x + y, vals)


class Throw(object):
    """
    Throws 1 or more Dice. Knows how to format the text output for a single throw.
    """
    def __init__(self, dice=None):
        if not dice:
            dice = []
        self.dice = dice

    def add_dice(self, dice):
        """ Add one or more dice to be thrown. """
        self.dice += dice

    def throw(self):
        """ Throw the dice and return the individual rolls and total. """
        for die in self.dice:
            die.roll()

        self.dice[0].acu = str(self.dice[0])
        tot = functools.reduce(pick_op, self.dice)

        return "{} = {}".format(tot.acu, tot.num)


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
        raise dice.exc.InvalidCommandArgs("Invalid number for rolls or dice.")

    return (rolls, sides)


def pick_op(d1, d2):
    """
    Just a slightly larger lambda.
    To be used as a reduction across dice.
    """
    result = getattr(d1, d1.next_op)(d2)
    if not d1.acu:
        d1.acu = str(d1)
    result.acu = d1.acu + str(d2)
    return result


def tokenize_dice_spec(spec):
    """
    Tokenize a string of arbitrary Fixed and Dice rolls into tokens.
    """
    tokens = []
    for roll in re.split(r'\s+', spec):
        if roll in ['+', '-'] and tokens:
            tokens[-1].next_op = OP_DICT[roll]
            continue

        if 'kh' in roll:
            tokens += [DiceRollKeepHigh(roll)]
            continue
        elif 'kl' in roll:
            tokens += [DiceRollKeepLow(roll)]
            continue

        try:
            tokens += [FixedRoll(int(roll))]
        except ValueError:
            tokens += [DiceRoll(roll)]

    return tokens


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
