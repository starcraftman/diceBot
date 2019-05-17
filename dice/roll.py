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
DICE_WARN = """Malformed dice string was received. Please check what you wrote!

Supported dice format:

    **4d6** Roll 4 d6 dice and sum results.
    **4d6kh2** Roll 4d6 and keep 2 highest results.
    **4d6kl1** Roll 4d6 and keep the lowest result.

    All values must be in range [1, +∞].
    If leading number omitted, one roll is made.
"""
DICE_REGEX = re.compile(r'(\d*)d(\d+)((kh?|kl)?(\d+))?', re.ASCII | re.IGNORECASE)


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

        return "{}({})".format(self.__class__.__name__, ', '.join(kwargs))

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
            raise TypeError("Must add a subclass of Dice.")

        return FixedRoll(str(self.num + other.num), next_op=other.next_op,
                         acu=self.acu + str(other))

    def __sub__(self, other):
        """
        Subtract one dice from another dice. Always returns a FixedRoll (i.e. fixed Dice).
        """
        if not isinstance(other, Dice):
            raise TypeError("Must add a subclass of Dice.")

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

    @staticmethod
    def factory(dice_spec):
        """
        Given a dice_spec, return the applicable Dice subclass.

        Raises:
            InvalidCommandArgs - Bad dice spec input from user.

        Returns:
            An instance of Dice subclass.
        """
        if 'kh' in dice_spec and 'kl' in dice_spec:
            raise dice.exc.InvalidCommandArgs("__kh__ and __kl__ are mutually exclusive. Pick one!")

        kwargs = parse_dice_spec(dice_spec, include_cls=True)
        cls = kwargs['cls']
        del kwargs['cls']

        return cls(**kwargs)


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

    def roll(self):
        self.values = rand.randint(1, self.sides + 1, self.rolls)
        return self.num


class DiceRollKeepHigh(DiceRoll):
    """
    Same as a dice roll but only keep n high rolls.
    """
    def __init__(self, dice_spec=None, **kwargs):
        if dice_spec:
            kwargs.update(parse_dice_spec(dice_spec))

        keep = kwargs['keep']
        del kwargs['keep']
        super().__init__(**kwargs)

        self.keep = keep

    def __repr__(self):
        keys = ['rolls', 'sides', 'keep', 'next_op', 'values', 'acu']
        kwargs = ['{}={!r}'.format(key, getattr(self, key)) for key in keys]

        return "{}({})".format(self.__class__.__name__, ', '.join(kwargs))

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


class DiceRollKeepLow(DiceRollKeepHigh):
    """
    Same as a dice roll but only keep n low rolls.
    """
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
    A container to throw a collection of dice and format the response to users.

    Attributes:
        all_dice: The list of Dice objects to roll each time.
    """
    def __init__(self, all_dice=None):
        if not all_dice:
            all_dice = []
        self.all_dice = all_dice

    def add_all(self, new_dice):
        """
        Add one or more dice to the container.

        Args:
            new_dice: A list of Dice to add to the collection.
        """
        for die in new_dice:
            if not issubclass(die.__class__, Dice):
                raise TypeError("Must add a subclass of Dice.")

        self.all_dice += new_dice

    def next(self):
        """
        Throw all_dice and return the formatted rolls as a string that shows the
        individual components of the rolls.

        Raises:
            InvalidCommandArgs - Requested an excessive amount of dice rolls, refuse
                                 to waste cycles on the server.

        Returns:
            A string that shows the user how he rolled.
        """
        for die in self.all_dice:
            if die.rolls > DICE_ROLL_LIMIT or die.sides > MAX_DIE:
                msg = "{} is excessive.\n\n\
I won't waste my otherworldly resources on it, insufferable mortal.".format(die.spec[1:-1])
                raise dice.exc.InvalidCommandArgs(msg)

        for die in self.all_dice:
            die.roll()

        self.all_dice[0].acu = str(self.all_dice[0])
        tot = functools.reduce(lambda x, y: getattr(x, x.next_op)(y), self.all_dice)

        return "{} = {}".format(tot.acu, tot.num)


def parse_dice_spec(spec, *, include_cls=False):
    """
    Parses a single dice spec of form 2d6(kh|kl)2

    Args:
        spec: A dice specification of form 2d6. If leading number missing, assume 1 roll.
        include_cls: Provide the correct subclass to instantiate in returned dictionary.

    Raises:
        InvalidCommandArgs: The spec was not properly formatted, user likely made a mistake.

    Returns:
        A dictionary of the form below, can be used to instantiate the dice.
        The cls entry denotes what class should be created and passed rest of kwargs.
        {
            'rolls': num_rolls,
            'sides': num_sides,
            'keep': num_to_keep,
            'cls': Dice subclass
        }
    """
    spec = str(spec).lower()
    try:
        parsed = {'rolls': 1, 'sides': int(spec), 'cls': FixedRoll}
    except ValueError:
        match = DICE_REGEX.match(spec)
        if not match:
            raise dice.exc.InvalidCommandArgs(DICE_WARN)

        parsed = {
            'rolls': int(match.group(1)) if match.group(1) else 1,
            'sides': int(match.group(2)),
            'cls': DiceRoll,
        }

        if match.group(3):
            parsed['keep'] = int(match.group(5))
            parsed['cls'] = DiceRollKeepLow if match.group(4) == 'kl' else DiceRollKeepHigh

    if not include_cls:
        del parsed['cls']

    return parsed


def tokenize_dice_spec(spec):
    """
    Tokenize a single string into individual Dice.
    String should be of form:

        4d6 + 10d6kh2 - 4
    """
    tokens = []
    spec = re.sub(r'([+-])', r' \1 ', spec.lower())  # People sometimes do not space.

    for dice_spec in re.split(r'\s+', spec):
        if dice_spec in ['+', '-'] and tokens:
            tokens[-1].next_op = OP_DICT[dice_spec]

        else:
            tokens += [Dice.factory(dice_spec)]

    return tokens
