"""
Dice module for throwing dice.
"""
# See systems listed: https://wiki.roll20.net/Dice_Reference
# These are a series of ideas rather than firm commitments to implement.
# TODO: Allow comments post roll, i.e. 3d6 + 20 this comment gets replayed back.
# TODO: Grouped rolls {2d10,4d20}kh1, take highest total value.
# TODO: Have a means for fixed offset, i.e. 2d10 + 1
# TODO: Likely need to implement math ops on Die (__add__, __sub__, so on ...)


# First Attempt Done
# TODO: Simple success/fail system, 3d6>4, report # success over 4 or =. 3d6<5 # fails less than or = 5
# TODO: Refactor to a Dice class + some addable modifiers on demand.
# TODO: 4DF, fate dice are 3sides (-1, 0, 1).
# TODO: Exploding dice, 3d6! -> reroll on hitting 6, 3d6!>4, explode greater than 4.
# TODO: Rerolling low dice: 4d6r<2, 4d6r1r3r5
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
IS_DIE = re.compile(r'(\d+)d(\d+)', re.IGNORECASE)
IS_FATEDIE = re.compile(r'(\d+)df', re.IGNORECASE)
IS_PREDICATE = re.compile(r'(>)?(<)?(\d+)')


def determine_predicate(line, max_roll):
    """
    Return the next predicate based on line string that will either:
        - Determine when dice value == a_value (4)
        - Determine when dice value >= a_value (>4)
        - Determine when dice value <= a_value (<4)

    The predicate will work on a Die object or else a simple int.

    Args:
        line: A substring of a dice spec.
        max_roll: The greatest roll possible of given dice.
                  If mixing different variants (i.e. d20, d8, d6 ...) the LOWEST max_roll.

    Raises:
        ValueError: Predicate was impossible to discern or would always be true.

    Returns:
        The predicate.
    """
    match = IS_PREDICATE.match(line)
    if not match:
        raise ValueError("Unable to determine predicate.")
    val = int(match.group(3))

    if match.group(1):
        if val <= 1:
            raise ValueError("Predicate always true on rolled dice.")
        return lambda d: getattr(d, 'value', d) >= val

    if match.group(2):
        if val >= max_roll:
            raise ValueError("Predicate always true on rolled dice.")
        return lambda d: getattr(d, 'value', d) <= val

    return lambda d: getattr(d, 'value', d) == val


def parse_diceset(line):
    """
    Attempt to parse a dice set from the line.
    """
    match = IS_DIE.match(line)
    if not match:
        raise ValueError("No match for dice.")

    dset = DiceSet()
    dset.add_dice(int(match.group(1)), int(match.group(2)))

    return line[match.end():], dset


def parse_fate_diceset(line):
    """
    Attempt to parse a dice set from the line.
    """
    match = IS_FATEDIE.match(line)
    if not match:
        raise ValueError("No match for dice.")

    dset = DiceSet()
    dset.add_fatedice(int(match.group(1)))

    return line[match.end():], dset


def parse_trailing_mods(line, max_roll):
    """
    Parse the trailing modifiers that might follow a dice spec.

    Returns:
        The remainder of the line unprocessed, the list of ModifyDice objects to apply.
    """
    try:
        index = min(line.index(' '), line.index('}'))
        substr, line = line[:index], line[index:]
    except ValueError:
        substr = line

    mods = []
    while substr:
        if substr[0] in ['k', 'd']:
            substr, mod = KeepOrDrop.parse(substr, max_roll)
        elif substr[:2] == '!!':
            substr, mod = CompoundingDice.parse(substr, max_roll)
        elif substr[0] == '!':
            substr, mod = ExplodingDice.parse(substr, max_roll)
        elif substr[0] == 'r':
            substr, mod = RerollDice.parse(substr, max_roll)
            if 'r' in substr:
                raise ValueError("All reroll predicates must be together.")
        else:
            substr, mod = SuccessFail.parse(substr, max_roll)

        mods += [mod]

    if substr and substr[0] not in [' ', '}']:
        raise ValueError("Unable to parse all parts of modifer spec.")

    return substr, mods


def parse_literal(spec):
    """
    Ensure only allowed literals continue.
    """
    match = re.match(r'([+-])?([-0-9]+)?', spec)
    if not match:
        raise ValueError("There is no valid literal to parse.")

    if match.group(1):
        return spec[2:], spec[0]

    return spec[match.end() + 1:], match.group(2)


def parse_dice_line(spec):
    """
    Returns a list of parsed Die with modifiers attached.
    """
    throw = AThrow()
    for part in re.split(r'\s+', spec):
        dset = None

        for func in [parse_diceset, parse_fate_diceset, parse_literal]:
            try:
                part, dset = func(part)
                throw.add(dset)

                if dset and issubclass(type(dset), DiceSet):
                    part, mods = parse_trailing_mods(part, dset.max_roll)
                    for mod in mods:
                        dset.add_mod(mod)
                break
            except ValueError:
                pass

    return throw


@functools.total_ordering
class Die():
    """
    Model a single dice with n sides.
    """
    MASK = 0xF
    KEEP = 1 << 0
    DROP = 1 << 1
    EXPLODE = 1 << 2
    REROLL = 1 << 3
    FAIL = 1 << 4
    SUCCESS = 1 << 5

    def __init__(self, *, sides=1, value=1, flags=1):
        self.sides = sides
        self._value = value
        self.flags = flags

    def __repr__(self):
        keys = ['sides', 'value', 'flags']
        kwargs = ['{}={!r}'.format(key, getattr(self, key)) for key in keys]
        return "{}({})".format(self.__class__.__name__, ', '.join(kwargs))

    def __str__(self):
        return self.fmt_string().format(self.value)

    def __hash__(self):
        return hash('{}_{}'.format(self.sides, self.value))

    def __eq__(self, other):
        return issubclass(type(other), Die) and self.value == other.value

    def __lt__(self, other):
        return issubclass(type(other), Die) and self.value < other.value

    @property
    def value(self):
        if self.is_success():
            return "S"
        if self.is_fail():
            return "F"

        return self._value

    @value.setter
    def value(self, new_value):
        if new_value < 1:
            raise ValueError

        self._value = new_value

    @property
    def max_roll(self):
        """ Maximum roll is the total number of sides. """
        return self.sides

    def fmt_string(self):
        fmt = "{}"

        if self.is_exploded():
            fmt = "__" + fmt + "__"
        if self.is_dropped():
            fmt = "~~" + fmt + "~~"
        if self.flags & (Die.FAIL | Die.SUCCESS):
            fmt = "**" + fmt + "**"

        return fmt

    def roll(self):
        """ Reroll the value of this dice. """
        self._value = rand.randint(1, self.sides + 1)
        return self.value

    def dupe(self):
        """ Create a duplicate dice based on this spec. """
        dupe = self.__class__(sides=self.sides)
        dupe.roll()
        return dupe

    def reset_flags(self):
        """ Ensure this dice is kept, resets all other flags. """
        self.flags = Die.KEEP

    def is_kept(self):
        """ True if this dice still counts. """
        return self.flags & Die.KEEP

    def is_dropped(self):
        """ True if this dice should be ignored. """
        return self.flags & Die.DROP

    def is_exploded(self):
        """ True if this dice has exploded at least once. """
        return self.flags & Die.EXPLODE

    def is_rerolled(self):
        """ True if this dice has been rerolled and should be ignored. """
        return self.flags & Die.REROLL

    def is_success(self):
        """ True if this dice passed a required threshold. """
        return self.flags & Die.SUCCESS

    def is_fail(self):
        """ True if this dice failed a required threshold. """
        return self.flags & Die.FAIL

    def set_drop(self):
        """ Ensure this dice is dropped and no longer counted. """
        self.flags = self.flags & (~Die.KEEP & Die.MASK)
        self.flags = self.flags | Die.DROP

    def set_reroll(self):
        """ The dice has been rerolled, ignore it. """
        self.flags = self.flags | Die.REROLL

    def set_success(self):
        """ Set success to display for this roll. """
        self.flags = self.flags & (~Die.FAIL & Die.MASK)
        self.flags = self.flags | Die.SUCCESS

    def set_fail(self):
        """ Set fail to display for this roll. """
        self.flags = self.flags & (~Die.SUCCESS & Die.MASK)
        self.flags = self.flags | Die.FAIL

    def explode(self):
        """
        Explode this dice.
        Marks this one as exploded and returns a new dice of same spec.

        Returns:
            A duplicate of the current Die already rolled.
        """
        self.flags = self.flags | Die.EXPLODE
        return self.dupe()


class FateDie(Die):
    """
    A Fate die is nothing more than a d3 where the value is mapped down -2.
    """
    REP = {
        -1: '-',
        0: '0',
        1: '+',
        'S': 'S',
        'F': 'F',
    }

    def __init__(self, **kwargs):
        kwargs['sides'] = 3
        super().__init__(**kwargs)

        if 'value' not in kwargs:
            self.value = 0

    def __str__(self):
        fmt = self.fmt_string()
        value = self.__class__.REP[self.value]

        return fmt.format(value)

    @property
    def value(self):
        if self.is_success():
            return "S"
        if self.is_fail():
            return "F"

        return self._value - 2

    @value.setter
    def value(self, new_value):
        if new_value not in range(-1, 2):
            raise ValueError

        self._value = new_value + 2


class DiceSet():
    """
    A diset set is simply a collection of dice. It can contain:
        - A group of die or fate die.
    Allow modifiers to be popped onto the set and applied after rolling.
    """
    def __init__(self, *, all_die=None, mods=None):
        self.all_die = all_die if all_die else []
        self.mods = mods if mods else []

    def __repr__(self):
        return "DiceSet(all_die={!r}, mods={!r})".format(self.all_die, self.mods)

    def __str__(self):
        if not self.all_die:
            return ""

        msg = str(self.all_die[0])
        for prev_die, die in zip(self.all_die[:-1], self.all_die[1:]):
            if not prev_die.is_rerolled():
                msg += " + "
            else:
                msg += " >> "
            msg += str(die)

        return msg

    @property
    def value(self):
        """ The value of this grouping is the sum of all non-dropped rolls. """
        return sum([x.value for x in self.all_die if x.is_kept()])

    @property
    def max_roll(self):
        """ The lowest maximum roll within this dice set. """
        return min([x.max_roll for x in self.all_die])

    def add_dice(self, number, sides):
        """
        Add a number of Die to this set.
        All Die default to value of 1 until rolled.

        Args:
            number: The number of Die to add.
            sides: The number of sides on the Die.
        """
        self.all_die += [Die(sides=sides) for _ in range(0, number)]

    def add_fatedice(self, number):
        """
        Add a number of FateDie to this set.
        All FateDie default to value of 0 until rolled.

        Args:
            number: The number of FateDie to add.
        """
        self.all_die += [FateDie() for _ in range(0, number)]

    def add_mod(self, mod):
        """
        Add a modifier to this dice set.
        Enforces internal ordering of application.

        Order:
            Reroll all required rolls first.
            Explode any dice that require explosions.
            Apply KeeporDrop/SuccessFail in order applied.
        """
        if not issubclass(type(mod), ModifyDice):
            raise ValueError("Not a subclass of ModifyDice.")

        if isinstance(mod, RerollDice):
            self.mods = [mod] + self.mods

        elif issubclass(type(mod), ExplodingDice) and self.mods and isinstance(self.mods[0], RerollDice):
            self.mods.insert(1, mod)

        else:
            self.mods += [mod]

    def roll(self):
        """
        Roll all the die in this set.
        """
        for die in self.all_die:
            die.roll()
            die.reset_flags()

    def apply_mods(self):
        """
        Apply the modifers to the current roll of die.
        """
        for mod in self.mods:
            mod.modify(self)


class AThrow():
    """
    A container that represents an entire throw line.
    Composes the following elements:
        - DiceSets (made of Die and FateDie + modifiers)
        - Constants
        - Operators

    Attributes:
        parts: The list of all parts of AThrow.
    """
    def __init__(self, parts=None):
        self.parts = parts if parts else []

    def __repr__(self):
        return "AThrow(parts={!r})".format(self.parts)

    def __str__(self):
        return " ".join([str(x) for x in self.parts])

    def add(self, part):
        """
        Add one part to the container.

        Args:
            part: A Die subclass or a string that is an operator or a number.
        """
        self.parts += [part]

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
        value = 0
        next_coeff = 1

        for part in self.parts:
            if part == "-":
                next_coeff = -1

            elif part == "+":
                next_coeff = 1

            elif issubclass(type(part), DiceSet):
                part.roll()
                part.apply_mods()
                value = value + next_coeff * part.value

            else:
                value = value + next_coeff * int(part)

        return "{} = {}".format(str(self), value)


class ModifyDice(abc.ABC):
    """
    Standard interface to modify a dice set.

    Consider them like friend functions that modify an existing roll set.
    """
    @abc.abstractstaticmethod
    def parse(line, max_roll):
        """
        A method to parse a line and return the associated ModifyDice subclass
        if and only if enough information is present.
        The max_roll is used to check if any predicates would be invalid that may be required.

        Args:
            line: A substring of the dice spec that conforms to the modifier's spec.
            max_roll: The maximum roll of the dice in the collection. For example, d6 = 6.

        Returns:
            The line minus parsed text, A ModifyDice subclass.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def modify(self, dice_set):
        """
        Apply the modifier to the dice and make marks/selections as required.

        Args:
            dice_set: A collection of dice.

        Returns:
            The dice_set passed in, it will have been modified.
        """
        raise NotImplementedError


class KeepOrDrop(ModifyDice):
    """
    Keep or drop N high or low rolls.
    """
    def __init__(self, *, keep=True, high=True, num=1):
        self.keep = keep
        self.high = high
        self.num = num

    def __repr__(self):
        return "KeepOrDrop(keep={!r}, high={!r}, num={!r})".format(
            self.keep, self.high, self.num)

    @staticmethod
    def parse(line, _):
        """
        Parse the line string for an object.
        Supports: kh4, kl3, dh4, dl2

        Raises:
            ValueError: Could not understand specification.

        Returns:
            KeepOrDrop object on successful parsing.
        """
        if len(line) < 3:
            raise ValueError("line string too short.")

        match = re.match(r'(k|d)(h|l)(\d+)', line, re.ASCII | re.IGNORECASE)
        if not match:
            raise ValueError("Invalid spec for.")

        keep = line[0] == 'k'
        high = line[1] == 'h'
        return line[match.end():], KeepOrDrop(keep=keep, high=high, num=int(match.group(3)))

    def modify(self, dice_set):
        """
        Depending on arguements can, keep or drop the num highest or lowest dice values.
        Will not modify dice that have already been dropped.

        Returns:
            The original DiceSet.
        """
        all_die = sorted([d for d in dice_set.all_die if not d.is_rerolled() and not d.is_dropped()])
        if not self.keep:
            all_die = list(reversed(all_die))

        first, second = ['set_drop', 'NOP'] if self.high else ['NOP', 'set_drop']
        for die in all_die[:-self.num]:
            getattr(die, first, lambda: True)()
        for die in all_die[-self.num:]:
            getattr(die, second, lambda: True)()

        return dice_set


class ExplodingDice(ModifyDice):
    """
    Explode on some predicate.

    Predicate of form:
        def pred(die):
            return True IFF should explode this dice.
    """
    def __init__(self, *, pred):
        self.pred = pred

    def __repr__(self):
        return "{}(pred={!r})".format(self.__class__.__name__, self.pred)

    @staticmethod
    def parse(line, max_roll):
        """
        Parse the line string for an object.
        Supports format: !6, !>6, !<6

        Raises:
            ValueError: Could not understand specification.

        Returns:
            ExplodingDice object on successful parsing.
        """
        if len(line) < 2:
            raise ValueError("line string too short.")

        match = re.match(r'![><]?\d+', line)
        if not match:
            raise ValueError("ExplodingDice spec invalid.")

        return line[match.end():], ExplodingDice(pred=determine_predicate(line[1:], max_roll))

    def modify(self, dice_set):
        """
        Modifies the actual dice in the dice set.

        Returns:
            The original DiceSet.
        """
        to_explode = [d for d in dice_set.all_die if not d.is_rerolled() and self.pred(d)]

        while to_explode:
            explosions = [d.explode() for d in to_explode]
            dice_set.all_die += explosions

            to_explode = [d for d in explosions if self.pred(d)]

        return dice_set


class CompoundingDice(ExplodingDice):
    """
    A specialized variant of exploding dice.
    """
    @staticmethod
    def parse(line, max_roll):
        """
        Parse the line string for an object.
        Supports format: !!6, !!>6, !!<6

        Raises:
            ValueError: Could not understand specification.

        Returns:
            CompoundingDice object on successful parsing.
        """
        if len(line) < 3:
            raise ValueError("line string too short.")

        match = re.match(r'!![><]?\d+', line)
        if not match:
            raise ValueError("CompoundingDice spec invalid.")

        return line[match.end():], CompoundingDice(pred=determine_predicate(line[2:], max_roll))

    def modify(self, dice_set):
        """
        Keep exploding the dice until predicate failes.
        All rolls are simply added to first explosion.
        """
        for die in [d for d in dice_set.all_die if not d.is_rerolled()]:
            new_explode = die
            while self.pred(new_explode):
                new_explode = die.explode()
                die.value += new_explode.value

        return dice_set


class RerollDice(ModifyDice):
    """
    Set predicates to trigger a reroll of dice.
    Dice that failed the predicate will be dropped.
    """
    def __init__(self, *, invalid_rolls=None):
        self.invalid_rolls = invalid_rolls if invalid_rolls else []

    def __repr__(self):
        return "RerollDice(invalid_rolls={!r})".format(self.invalid_rolls)

    @staticmethod
    def parse(line, max_roll):
        """
        Parse the line string for an object.
        Supports format: r6, r<2, r>5
        When multiple rerolls declared, flatten down to single list of invalids.

        Raises:
            ValueError: Could not understand specification.

        Returns:
            RerollDice object on successful parsing.
        """
        if len(line) < 2:
            raise ValueError("line string too short.")

        possible = list(range(1, max_roll + 1))
        invalid = []
        while line:
            if not line[0] == 'r':
                break

            match = IS_PREDICATE.match(line[1:])
            if not match:
                break

            try:
                pred = determine_predicate(line[1:], max_roll)
                invalid += [x for x in possible if pred(x)]
            except ValueError:
                break

            line = line[1 + match.end():]

        if not invalid:
            raise ValueError("Invalid RerollDice spec.")

        invalid = sorted(set(invalid))
        if not set(possible) - set(invalid):
            raise ValueError("Impossible set of predicates. Would always reroll!")

        return line, RerollDice(invalid_rolls=invalid)

    def modify(self, dice_set):
        for die in dice_set.all_die.copy():
            while die.value in self.invalid_rolls:
                die.set_reroll()
                die = die.dupe()
                dice_set.all_die += [die]


class SuccessFail(ModifyDice):
    """
    Set predicates to trigger the success or fail of a die.
    Dice that failed the predicate will be set to fail.
    """
    def __init__(self, *, pred, mark_success=True):
        self.pred = pred
        self.mark = 'set_success' if mark_success else 'set_fail'

    def __repr__(self):
        return "SuccessFail(pred={!r}, mark={!r})".format(self.pred, self.mark)

    @staticmethod
    def parse(line, max_roll):
        """
        Parse a line for success or failure criteria for the associated dice.
        Supports:
            Success: '<2' success on <=2 , '>5' success on >= 5
            Fail: 'f1' fail if == 1, 'f<3' fail on <=3, 'f>4' fail on >=4

        Raises:
            ValueError: Could not understand specification.

        Returns:
            Returns a SuccessFail object ready to mark based on predicate.
        """
        if len(line) < 2:
            raise ValueError("line string too short.")

        mark_success = line[0] != 'f'
        if line[0] == 'f':
            line = line[1:]
        elif line[0] not in ['>', '<']:
            raise ValueError("Invalid SuccessFail spec.")

        match = IS_PREDICATE.match(line)
        if not match:
            raise ValueError("Invalid SuccessFail spec.")

        return line[match.end():], SuccessFail(pred=determine_predicate(line, max_roll), mark_success=mark_success)

    def modify(self, dice_set):
        for die in [x for x in dice_set.all_die if not x.is_success() and not x.is_fail() and not x.is_rerolled()]:
            if self.pred(die):
                getattr(die, self.mark)()


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
