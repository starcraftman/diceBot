"""
Dice module for throwing dice.
"""
import abc
import functools
import re

import numpy.random as rand

import dice.exc

DICE_ROLL_LIMIT = 1000000
MAX_DIE = 10000
MAX_DIE_STR = 20
OP_DICT = {
    '__add__': '+',
    '__sub__': '-',
    '+': '__add__',
    '-': '__sub__',
}


# TODO: Remove OP_DICT and associated, replace by always adding and when subtraction
#       requested simply multiply num on request by -1.
#       That is default op always +, and explicit ops get put on right operand.
class Dice(abc.ABC):
    """
    An abstract interface for a dice.

    Attributes:
        rolls: This many rolls to make, 4 rolls for 4d6.
        sides: How many sides a dice has, 4d6 has 6 sides.
        values: The list of values for the last roll.
        next_op: The next operand, either a + or -.
        acu: An acumulator slot used to gather strings.
    """
    def __init__(self, *, values=None, rolls=1, sides=1, next_op="", acu=""):
        if not values:
            values = []
        self.rolls = rolls
        self.sides = sides
        self.values = values
        self.next_op = next_op  # Either "__add__" or "__sub__"
        self.acu = acu  # Slot to accumulate text, used in reduction

    def __repr__(self):
        keys = ['rolls', 'sides', 'next_op', 'values', 'acu']
        kwargs = ['{}={!r}'.format(key, getattr(self, key)) for key in keys]

        return "Dice({})".format(', '.join(kwargs))

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

        return FixedRoll(str(self.num + other.num), next_op=other.next_op,
                         acu=self.acu + str(other))

    def __sub__(self, other):
        """
        Subtract one dice from another dice. Always returns a FixedRoll (i.e. fixed Dice).
        """
        if not isinstance(other, Dice):
            raise ValueError("Can only add Dice")

        return FixedRoll(str(self.num - other.num), next_op=other.next_op,
                         acu=self.acu + str(other))

    @property
    def num(self):
        """
        The sum of the dice roll(s) for the spec.
        """
        return functools.reduce(lambda x, y: x + y, self.values)

    @property
    @abc.abstractmethod
    def spec(self):
        """
        The specification of how to roll the dice.
        """
        raise NotImplementedError

    @property
    def trailing_op(self):
        """
        The operation to combine this dice with next.
        """
        return ' {} '.format(OP_DICT[self.next_op]) if self.next_op else ""

    @abc.abstractmethod
    def roll(self):
        """
        Perform the roll as specified.
        """
        raise NotImplementedError


class FixedRoll(Dice):
    """
    A fixed dice roll, always returns the same number.
    You might even say the dice was loaded.
    """
    def __init__(self, dice_spec=None, **kwargs):
        if dice_spec:
            kwargs.update(parse_dice_spec(dice_spec))
            kwargs['values'] = [kwargs['sides']]
        super().__init__(**kwargs)

    @property
    def spec(self):
        return str(self)

    def __repr__(self):
        keys = ['rolls', 'sides', 'next_op', 'values', 'acu']
        kwargs = ['{}={!r}'.format(key, getattr(self, key)) for key in keys]

        return "FixedRoll({})".format(', '.join(kwargs))

    def roll(self):
        return self.num


class DiceRoll(Dice):
    """
    A standard dice roll of the standard form, like 4d6.
    """
    def __init__(self, dice_spec=None, **kwargs):
        if dice_spec:
            kwargs.update(parse_dice_spec(dice_spec))
        super().__init__(**kwargs)

    @property
    def spec(self):
        return "({}d{})".format(self.rolls, self.sides)

    def __repr__(self):
        keys = ['rolls', 'sides', 'next_op', 'values', 'acu']
        kwargs = ['{}={!r}'.format(key, getattr(self, key)) for key in keys]

        return "DiceRoll({})".format(', '.join(kwargs))

    def roll(self):
        self.values = rand.randint(1, self.sides + 1, self.rolls)
        return self.num


class DiceRollKeepHigh(DiceRoll):
    """
    Same as a dice roll but only keep n high rolls.
    """
    def __init__(self, dice_spec=None, keep=None, **kwargs):
        if dice_spec:
            front = dice_spec[:dice_spec.rindex('k')]
            kwargs.update(parse_dice_spec(front))
        super().__init__(**kwargs)

        if keep:
            self.keep = keep
        else:
            match = re.match(r'.*kh?(\d+)', dice_spec)
            if match:
                self.keep = int(match.group(1))

    def __repr__(self):
        keys = ['rolls', 'sides', 'keep', 'next_op', 'values', 'acu']
        kwargs = ['{}={!r}'.format(key, getattr(self, key)) for key in keys]

        return "DiceRollKeepHigh({})".format(', '.join(kwargs))

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
        return "({}d{}kh{})".format(self.rolls, self.sides, self.keep)

    @property
    def num(self):
        vals = sorted(self.values)[-self.keep:]
        return functools.reduce(lambda x, y: x + y, vals)


class DiceRollKeepLow(DiceRoll):
    """
    Same as a dice roll but only keep n low rolls.
    """
    def __init__(self, dice_spec=None, keep=None, **kwargs):
        if dice_spec:
            front = dice_spec[:dice_spec.rindex('kl')]
            kwargs.update(parse_dice_spec(front))
        super().__init__(**kwargs)

        if keep:
            self.keep = keep
        else:
            match = re.match(r'.*kl(\d+)', dice_spec)
            if match:
                self.keep = int(match.group(1))

    def __repr__(self):
        keys = ['rolls', 'sides', 'keep', 'next_op', 'values', 'acu']
        kwargs = ['{}={!r}'.format(key, getattr(self, key)) for key in keys]

        return "DiceRollKeepLow({})".format(', '.join(kwargs))

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
        return "({}d{}kl{})".format(self.rolls, self.sides, self.keep)

    @property
    def num(self):
        vals = sorted(self.values)[:self.keep]
        return functools.reduce(lambda x, y: x + y, vals)


class Throw(object):
    """
    Throws 1 or more Dice. Acts as a simple container.
    Can be used primarily to reroll a complex dice setup.
    """
    def __init__(self, n_dice=None):
        self.dice = n_dice
        if not self.dice:
            self.dice = []

    def add_dice(self, n_dice):
        """
        Add one or more dice to be thrown.

        Args:
            dice: A list of Dice.
        """
        for die in n_dice:
            if not issubclass(die.__class__, Dice):
                raise ValueError("Must add subclass of Dice")

        self.dice += n_dice

    def next(self):
        """ Throw the dice and return the individual rolls and total. """
        for die in self.dice:
            if die.rolls > DICE_ROLL_LIMIT or die.sides > MAX_DIE:
                msg = "{} is excessive.\n\n\
I won't waste my otherworldly resources on it, insufferable mortal.".format(die.spec[1:-1])
                raise dice.exc.InvalidCommandArgs(msg)

        for die in self.dice:
            die.roll()

        self.dice[0].acu = str(self.dice[0])
        tot = functools.reduce(lambda x, y: getattr(x, x.next_op)(y), self.dice)

        return "{} = {}".format(tot.acu, tot.num)


def parse_dice_spec(spec):
    """
    Parses a single dice spec of form 2d6.

    Args:
        spec: A dice specification of form 2d6. If leading number missing, assume 1 roll.

    Raises:
        InvalidCommandArgs: The spec was not properly formatted, user likely made a mistake.

    Returns:
        {'rolls': num_rolls, 'sides': num_sides}
    """
    terms = str(spec).lower().split('d')
    terms.reverse()

    if terms == ['']:
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

    return {'rolls': rolls, 'sides': sides}


def tokenize_dice_spec(spec):
    """
    Tokenize a single string into multiple Dice.
    String should be of form:

        4d6 + 10d6kh2 - 4
    """
    tokens = []
    spec = re.sub(r'([+-])', r' \1 ', spec.lower())  # People sometimes do not space.

    for roll_spec in re.split(r'\s+', spec):
        if roll_spec in ['+', '-'] and tokens:
            tokens[-1].next_op = OP_DICT[roll_spec]
            continue

        if 'kh' in roll_spec and 'kl' in roll_spec:
            raise dice.exc.InvalidCommandArgs("__kh__ and __kl__ are mutually exclusive. Pick one!")

        if 'kl' in roll_spec:
            tokens.append(DiceRollKeepLow(roll_spec))
        elif 'k' in roll_spec:
            tokens.append(DiceRollKeepHigh(roll_spec))
        elif 'd' in roll_spec:
            tokens.append(DiceRoll(roll_spec))
        else:
            tokens.append(FixedRoll(roll_spec))

    return tokens
