"""
Dice module for throwing dice.
"""
# See systems listed: https://wiki.roll20.net/Dice_Reference
# These are a series of ideas rather than firm commitments to implement.
# TODO: Allow comments post roll, i.e. 3d6 + 20 this comment gets replayed back.
# TODO: Simple success/fail system, 3d6>4, report # sucess over 4 or =. 3d6<5 # fails less than or = 5
# TODO: Grouped rolls {2d10,4d20}kh1, take highest total value.

# TODO: Rerolling low dice: 4d6r<2, 4d6r1r3r5
#           Consider how they overlap and can cause infinite rerolls

# TODO: Refactor to a Dice class + some addable modifiers on demand.
# TODO: 4DF, fate dice are 3sides (-1, 0, 1).
# TODO: Exploding dice, 3d6! -> reroll on hitting 6, 3d6!>4, explode greater than 4.
import abc
import functools
import re

import numpy.random as rand

import dice.exc

DICE_ROLL_LIMIT = 1000000
MAX_DIE = 10000
MAX_DIE_STR = 20
OP_DICT = {
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


def determine_predicate(partial, max_roll):
    """
    Raises:
        ValueError: Predicate was impossible to discern or would always be true.

    Returns:
        The predicate.
    """
    match = re.match(r'(>)?(<)?(\d+)', partial)
    if not match:
        raise ValueError("Unable to determine predicate.")
    val = int(match.group(3))

    if match.group(1):
        if val == 1:
            raise ValueError("Predicate always true on rolled dice.")
        return lambda d: d.value >= val

    if match.group(2):
        if val == max_roll:
            raise ValueError("Predicate always true on rolled dice.")
        return lambda d: d.value <= val

    return lambda d: d.value == val


@functools.total_ordering
class Die():
    """
    Model a single dice with n sides.
    """
    def __init__(self, *, sides=1, value=1, kept=True, exploded=False):
        self.sides = sides
        self.kept = kept
        self.exploded = exploded
        self.value = value
        self.fmt = "{}"

    def __repr__(self):
        keys = ['sides', 'value', 'kept', 'exploded']
        kwargs = ['{}={!r}'.format(key, getattr(self, key)) for key in keys]

        return "{}({})".format(self.__class__.__name__, ', '.join(kwargs))

    def __str__(self):
        return self.fmt.format(self.value)

    def __hash__(self):
        return hash('{}_{}'.format(self.sides, self.value))

    def __eq__(self, other):
        return issubclass(type(other), Die) and self.value == other.value

    def __lt__(self, other):
        return issubclass(type(other), Die) and self.value < other.value

    def dupe(self):
        """ Create a duplicate dice based on this spec. """
        dupe = self.__class__(sides=self.sides)
        dupe.roll()
        return dupe

    def set_drop(self):
        """ Ensure this dice is dropped. """
        self.kept = False
        self.fmt = "~~{}~~"

    def set_keep(self):
        """ Ensure this dice is kept. """
        self.kept = True
        self.fmt = "{}"

    def set_sucess(self):
        self.fmt = "**{}**"
        self.value = "S"

    def set_fail(self):
        self.fmt = "**{}**"
        self.value = "F"

    def explode(self):
        """
        Explode this dice.
        Marks this one as exploded and returns a new dice of same spec.
        """
        self.fmt = "__{}__"
        self.exploded = True
        return self.dupe()

    def roll(self):
        """ Reroll the value of this dice. """
        self.value = rand.randint(1, self.sides + 1)
        return self.value


class FateDie(Die):
    def roll(self):
        self.value = rand.randint(-1, 2)
        return self.value


class DiceSet():
    """
    Contain a group of dice to roll together.
    Allow modifiers to be popped onto the set and applied after rolling.
    """
    def __init__(self, all_die=None, mods=None):
        self.all_die = all_die if all_die else []
        self.mods = all_die if all_die else []

    def __str__(self):
        return " + ".join([str(d) for d in self.all_die])

    def add_dice(self, number, sides):
        self.all_die += [Die(sides=sides) for _ in range(0, number)]

    def roll(self):
        for die in self.all_die:
            die.roll()
            die.set_keep()

    def apply_mods(self):
        for mod in self.mods:
            mod.modify_dice(self)

    def register_mod(self, mod):
        self.mods += [mod]


class ModifyDice(abc.ABC):
    """
    Standard interface to modify a dice set.
    """
    @abc.abstractstaticmethod
    def parse(partial):
        raise NotImplementedError

    @abc.abstractmethod
    def modify_dice(self, die_list):
        raise NotImplementedError


class KeepOrDrop(ModifyDice):
    """
    Keep or drop N high or low rolls.
    """
    def __init__(self, *, keep=True, high=True, num=1):
        self.keep = keep
        self.high = high
        self.num = num

    def parse(partial):
        """
        Parse the partial string for an object.
        Supports: kh4, kl3, dh4, dl2, k2
            N. B. k2 == kh2

        Raises:
            ValueError: Could not understand specification.

        Returns:
            KeepOrDrop object on sucessful parsing.
        """
        if len(partial) < 3:
            raise ValueError("Partial string too short.")

        if partial[0] not in ('k', 'd'):
            raise ValueError("First letter must be 'k' or 'd'.")
        keep = True if partial[0] == 'k' else False

        if partial[0] == 'd' and partial[1] not in ('h', 'l'):
            raise ValueError("No default with drop, specify high or low.")
        high = True if partial[1] != 'l' else False

        return KeepOrDrop(keep=keep, high=high, num=int(partial[2:]))

    def modify_dice(self, dice_set):
        """
        Depending on arguements can, keep or drop the num highest or lowest dice values.
        Will not modify dice that have already been dropped.

        Returns:
            The original DiceSet.
        """
        all_die = sorted([d for d in dice_set.all_die.copy() if d.kept])
        if not self.keep:
            all_die = list(reversed(all_die))

        first, second = ['set_drop', 'set_keep'] if self.high else ['set_keep', 'set_drop']
        for die in all_die[:-self.num]:
            getattr(die, first)()
        for die in all_die[-self.num:]:
            getattr(die, second)()

        return dice_set


class ExplodingDice(ModifyDice):
    """
    Explode on some predicate.

    Predicate of form:
        def pred(die):
            return True IFF should explode this dice.
    """
    def __init__(self, pred):
        self.pred = pred

    def parse(partial):
        """
        Parse the partial string for an object.
        Supports format: !6, !>6, !<6

        Raises:
            ValueError: Could not understand specification.

        Returns:
            ExplodingDice object on sucessful parsing.
        """
        if len(partial) < 2:
            raise ValueError("Partial string too short.")

        match = re.match(r'!(>)?(<)?(\d+)', partial)
        if not match:
            raise ValueError("ExplodingDice spec invalid.")

        return ExplodingDice(determine_predicate(partial[1:]))

    def modify_dice(self, dice_set):
        """
        Modifies the actual dice in the dice set.

        Returns:
            The original DiceSet.
        """
        to_explode = [d for d in dice_set.all_die if self.pred(d)]

        while to_explode:
            explosions = [d.explode() for d in to_explode]
            dice_set.all_die += explosions

            to_explode = [d for d in explosions if self.pred(d)]

        return dice_set


class CompoundingDice(ExplodingDice):
    """
    A specialized variant of exploding dice.
    """
    def parse(partial):
        """
        Parse the partial string for an object.
        Supports format: !!6, !!>6, !!<6

        Raises:
            ValueError: Could not understand specification.

        Returns:
            CompoundingDice object on sucessful parsing.
        """
        if len(partial) < 3:
            raise ValueError("Partial string too short.")

        match = re.match(r'!!(>)?(<)?(\d+)', partial)
        if not match:
            raise ValueError("CompoundingDice spec invalid.")

        return CompoundingDice(determine_predicate(partial[2:]))

    def modify_dice(self, dice_set):
        """
        Keep exploding the dice until predicate failes.
        All rolls are simply added to first explosion.
        """
        for d in dice_set.all_die:
            new_explode = d
            while self.pred(new_explode):
                new_explode = d.explode()
                d.value += new_explode.value

        return dice_set


class RerollDice(ModifyDice):
    def __init__(self, pred):
        self.pred = pred

    def parse(partial):
        """
        Parse the partial string for an object.
        Supports format: r6, r<2, r>5

        Raises:
            ValueError: Could not understand specification.

        Returns:
            RerollDice object on sucessful parsing.
        """
        if len(partial) < 2:
            raise ValueError("Partial string too short.")

        match = re.match(r'r(>)?(<)?(\d+)', partial)
        if not match:
            raise ValueError("RerollDice spec invalid.")

        return RerollDice(determine_predicate(partial[1:]))

    def modify_dice(self, dice_set):
        for d in dice_set.all_die:
            while self.pred(d):
                d.roll()


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
        return ' {} '.format(self.next_op) if self.next_op else ""

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


class Throw():
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
        tot = functools.reduce(lambda x, y: getattr(x, OP_DICT[x.next_op])(y), self.all_dice)

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
            tokens[-1].next_op = dice_spec

        else:
            tokens += [Dice.factory(dice_spec)]

    return tokens
