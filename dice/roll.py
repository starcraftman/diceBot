"""
Dice module for throwing dice.

Based on the Roll20 specification: https://wiki.roll20.net/Dice_Reference

Fixed Order of Evaluation:
    Compounding, Exploding, Rerolls, Keep/Drop, Success/Fail, Sort

Logic regarding modifiers:
    All dice start in keep state.
    Exploded dice still count but have triggered an extra roll.
    Rerolled dice are ignored in all cases except display for user info.
    Dropped dice have intentionally been ignored by predicate.
    Success and Fail are mutually exclusive and once marked will not remark.
    While they are exclusive, user can define both criteria separately.
    Sort will always occur last and just orders by value all rolls regardless of state.
"""
# Few ideas remaining
# TODO: Strong overlap between Die and DiceSet?
# TODO: Grouped rolls {2d10,4d20}kh1, take highest total value.
# TODO: Add reroll once, 2d10ro<2 => 2d10 any roll <=2 reroll it __ONCE__
import abc
import functools
import re

import numpy.random as rand

import dice.exc

PARENS_MAP = {'(': 3, '{': 7, '[': 11, ')': -3, '}': -7, ']': -11}
LIMIT_DIE_NUMBER = 1000
LIMIT_DIE_SIDES = 1000
LIMIT_DICE_SET_STR = 200
DICE_WARN = """**Error**: {}
        {}
Please see reference below and correct the roll.

__Quick Reference__

    5**:** 4d6 + 2                    Roll __5__ times, 4d6 + 2
    d20 + 5**,** d8 + 3           Roll d20 + 5, then separately d8 + 3.
    4d6 **#** For Gordon      Roll 4d6, comment after '#' replayed with roll result
    4d6**kh2**                        Roll 4d6 and keep __2__ highest results
    4d6**dl2**                         Roll 4d6 and drop the __2__ lowest results
    4d6**r1r[5,6]**                Roll 4d6 and reroll if dice lands on 1, 5 or 6
    4d6**!!6**                          Roll 4d6 and compound explode on a roll of 6
    4d6**!p>5**                       Roll 4d6 and explode on a roll of 5 or 6, value - 1 for each new exploded die
    4d6**!>5**                         Roll 4d6 and explode on a roll of 5 or 6
    4d6**f<10**                       Roll 4d6 and fail on a roll <= 10, ignore others
    4d6**>5**                          Roll 4d6 and succeed on rolls 3, 4 or 5. Others ignored
    4d6**s**                             Roll 4d6 and sort the output by ascending values
    4d6**sd**                           Roll 4d6 and sort the output by descending values

__Comparisons__

    [3,5]                           Apply modifier when roll is >=3 and <= 5.
    <4                               Apply modifer when <= 4
    >4                               Apply modifier when >= 4
    4 (or =4)                   Apply modifer when == 4.
                                N.B. The '=' is optional unless no letter separates the number.

All modifiers except kh/dl support comparisons to determine when they apply.
Mix and match as you like.

See `!roll --help` for more complete documentation.
"""
IS_DIE = re.compile(r'(\d+)?d(\d+)', re.ASCII | re.IGNORECASE)
IS_FATEDIE = re.compile(r'(\d+)?df', re.ASCII | re.IGNORECASE)
IS_LITERAL = re.compile(r'([+-])|([-0-9]+)', re.ASCII)
IS_PREDICATE = re.compile(r'(>)?(<)?\[?(=?\d+)(,\d+\])?', re.ASCII)


def check_parentheses(line):
    """
    Go over a string and ensure it has one opening and closing parentheses.

    Raises:
        ValueError: The parentheses are not balanced.

    Returns:
        The line if it passed validation.
    """
    cnt = 0
    for char in line:
        if char in PARENS_MAP:
            cnt += PARENS_MAP[char]

    if cnt != 0:
        raise ValueError(DICE_WARN.format("Unbalanced parentheses detected.", line))

    return line


class Comp():
    """
    The only reason this exists is that lambda functions don't automatically
    pickle like objects do. This is little more than a waste of space otherwise.
    All comparisons are inclusive, that is ==, <=, >= or [min, max].

    Attributes:
        left: The left bound of the comparison (default used if not a range).
        right: The right bound of the comparison.
        func: The function to invoke to compare when __call__ is used.
              See Comp.CHOICES .
    """
    CHOICES = ['equal', 'greater_equal', 'less_equal', 'range']

    def __init__(self, *, left=2, right=5, func=None):
        self.left = left
        self.right = right

        if func and func not in Comp.CHOICES:
            raise ValueError("Func must be one of:\n" + "\n".join(Comp.CHOICES))
        self.func = func

    def __repr__(self):
        return "Comp(left={!r}, right={!r}, func={!r})".format(self.left, self.right, self.func)

    def __call__(self, other):
        return getattr(self, self.func)(other)

    def range(self, other):
        """
        Implement a simple range check predicate against other.
        Supports Die subclasses and Numbers.

        Returns:
            True IFF other is in range [left, right].
        """
        return self.left <= int(other) <= self.right

    def less_equal(self, other):
        """
        Check other for <= predetermined value (left).
        Supports Die subclasses and Numbers.

        Returns:
            True IFF other is <= left.
        """
        return int(other) <= self.left

    def greater_equal(self, other):
        """
        Check other for >= predetermined value (left).
        Supports Die subclasses and Numbers.

        Returns:
            True IFF other is <= left.
        """
        return int(other) >= self.left

    def equal(self, other):
        """
        Check other == predetermined value (left).
        Supports Die subclasses and Numbers.

        Returns:
            True IFF other other == left.
        """
        return int(other) == self.left


def parse_predicate(line, max_roll):
    """
    Return the next predicate based on line that will either:
        - Determine when dice value == a_value (4)
        - Determine when dice value >= a_value (>4)
        - Determine when dice value <= a_value (<4)
        - Determine when dice value >= a_value, <= b_value ([4,6])

    The predicate will work on a Die object or else a simple int.

    Args:
        line: A substring of a dice spec.
        max_roll: The greatest roll possible of given dice.
                  If mixing different variants (i.e. d20, d8, d6 ...) the LOWEST max_roll.

    Raises:
        ValueError: Predicate was impossible to discern or would always be true.

    Returns:
        (substr, dset)
            substr: The remainder of line after processing.
            dset: A DiceSet object containing the correct amount of dice.
    """
    match = IS_PREDICATE.match(line)
    if not match:
        raise ValueError(DICE_WARN.format("Unable to determine predicate.", line))

    try:
        val = int(match.group(3))
    except ValueError:
        val = int(match.group(3)[1:])

    if match.group(4):
        right = int(match.group(4)[1:-1])
        if right < val or val < 1 or right > max_roll or (val == 1 and right == max_roll):
            raise ValueError(DICE_WARN.format("Predicate range is invalid, check bounds.", line))

        comp = Comp(left=val, right=right, func='range')

    elif match.group(1):
        if val <= 1:
            raise ValueError(DICE_WARN.format("Predicate will always be true (>=).", line))
        comp = Comp(left=val, func='greater_equal')

    elif match.group(2):
        if val >= max_roll:
            raise ValueError(DICE_WARN.format("Predicate will always be true (<=).", line))
        comp = Comp(left=val, func='less_equal')

    else:
        comp = Comp(left=val, func='equal')

    return line[match.end():], comp


def parse_diceset(line):
    """
    Attempt to parse a dice set from the line.

    Raises:
        ValueError: No dice specification could be found at the start of line.
        InvalidCommandArgs: User specified an amount of dice or sides that is unreasonable.

    Returns:
        (substr, dset)
            substr: The remainder of line after processing.
            dset: A DiceSet object containing the correct amount of dice.
    """
    match = IS_DIE.match(line)
    if not match:
        raise ValueError(DICE_WARN.format("Invalid D20 dice roll.", line))

    number = int(match.group(1)) if match.group(1) else 1
    sides = int(match.group(2))
    if sides > LIMIT_DIE_SIDES or number > LIMIT_DIE_NUMBER:
        raise dice.exc.InvalidCommandArgs("Roll request is unreasonable. Please roll a lower number of dice or sides.")

    dset = DiceSet()
    dset.add_dice(number, sides)

    return line[match.end():], dset


def parse_fate_diceset(line):
    """
    Attempt to parse a fate dice set from the line.

    Raises:
        ValueError: No dice specification could be found at the start of line.
        InvalidCommandArgs: User specified an amount of dice that is unreasonable.

    Returns:
        (substr, dset)
            substr: The remainder of line after processing.
            dset: A DiceSet object containing the correct amount of dice.
    """
    match = IS_FATEDIE.match(line)
    if not match:
        raise ValueError(DICE_WARN.format("Invalid FATE/FUDGE dice roll.", line))

    number = int(match.group(1)) if match.group(1) else 1
    if number > LIMIT_DIE_NUMBER:
        raise dice.exc.InvalidCommandArgs("Roll request is unreasonable. Please roll a lower number of dice.")

    dset = DiceSet()
    dset.add_fatedice(number)

    return line[match.end():], dset


def parse_trailing_mods(line, max_roll):
    """
    Attempt to parse the remaining modifiers of a dice set.

    Raises:
        ValueError: A failure to parse part of the modifiers.

    Returns:
        (substr, dset)
            substr: The remainder of line after processing.
            mods: A list of ModifyDice modifiers to apply to last DiceSet.
    """
    mods = []
    while line:
        if line[0] in [' ', '}', ',']:
            break

        if line[0] in ['k', 'd']:
            line, mod = KeepDrop.parse(line, max_roll)
        elif line[:2] == '!!':
            line, mod = CompoundDice.parse(line, max_roll)
        elif line[0] == '!':
            line, mod = ExplodeDice.parse(line, max_roll)
        elif line[0] == 'r':
            line, mod = RerollDice.parse(line, max_roll)
            if 'r' in line:
                raise ValueError(DICE_WARN.format("Reroll predicates must be together.", line))
        elif line[0] == 's':
            line, mod = SortDice.parse(line, max_roll)
        else:
            line, mod = SuccessFail.parse(line, max_roll)

        mods += [mod]

    return line, mods


def parse_literal(spec):
    """
    Parse allowed literals in the dice spec line and return them.

    Raises:
        ValueError: Disallowed literals were found.

    Returns:
        (substr, dset)
            substr: The remainder of line after processing.
            dset: A DiceSet object containing the correct amount of dice.
    """
    match = IS_LITERAL.match(spec)
    if not match:
        raise ValueError("There is no valid literal to parse.")

    if match.group(1):
        return spec[2:], spec[0]

    return spec[match.end() + 1:], match.group(2)


def parse_dice_line(spec):
    """
    Take a complete dice specification with optional literals and return
    AThrow object containing all required parts to model the throw.

    Raises:
        ValueError: Some part of the dice spec could not be parsed.

    Returns:
        AThrow object with the required parts.
    """
    try:
        ind = spec.index('#')
        note, spec = spec[ind + 1:], spec[:ind]
    except ValueError:
        note = ''
    throw = AThrow(spec=check_parentheses(spec).rstrip(), note=note.strip())

    while spec:
        if spec[0].isspace():
            spec = spec[1:]
            continue

        dset = None
        for func in [parse_diceset, parse_fate_diceset, parse_literal]:
            try:
                spec, dset = func(spec)
                throw.add(dset)

                if dset and issubclass(type(dset), DiceSet):
                    spec, mods = parse_trailing_mods(spec, dset.max_roll)
                    dset.mods = sorted(mods)
            except ValueError:
                pass

        if not dset:
            raise ValueError(DICE_WARN.format("Failed to parse part of line.", spec))

    return throw


class FlaggableMixin():
    """
    Implement a flaggable interface that can be used to indicate different
    states for a rolled Dice-like object.

    Attributes:
        flags: A bit field that stores the flags.
    """
    MASK = 0x3F
    KEEP = 1 << 0
    EXPLODE = 1 << 1
    PENETRATE = 1 << 2
    DROP = 1 << 3
    REROLL = 1 << 4
    FAIL = 1 << 5
    SUCCESS = 1 << 6

    def __init__(self):
        super().__init__()
        self.flags = 1

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

    def is_penetrated(self):
        """ True if this dice has exploded and was a penetrated roll. """
        return self.flags & Die.PENETRATE

    def is_rerolled(self):
        """ True if this dice has been rerolled and should be ignored. """
        return self.flags & Die.REROLL

    def is_fail(self):
        """ True if this dice failed a required threshold. """
        return self.flags & Die.FAIL

    def is_success(self):
        """ True if this dice passed a required threshold. """
        return self.flags & Die.SUCCESS

    def set_drop(self):
        """ Ensure this dice is dropped and no longer counted. """
        self.flags = self.flags & (~Die.KEEP & Die.MASK)
        self.flags = self.flags | Die.DROP

    def set_explode(self):
        """ The dice has been exploded. """
        self.flags = self.flags | Die.EXPLODE

    def set_penetrate(self):
        """ The dice has been exploded. """
        self.flags = self.flags | Die.PENETRATE

    def set_reroll(self):
        """ The dice has been rerolled, ignore it. """
        self.flags = self.flags | Die.REROLL

    def set_fail(self):
        """ Set fail to display for this roll. """
        self.flags = self.flags & (~Die.SUCCESS & Die.MASK)
        self.flags = self.flags | Die.FAIL

    def set_success(self):
        """ Set success to display for this roll. """
        self.flags = self.flags & (~Die.FAIL & Die.MASK)
        self.flags = self.flags | Die.SUCCESS


@functools.total_ordering
class Die(FlaggableMixin):
    """
    Model a single dice with n sides.
    """
    def __init__(self, *, sides=1, value=1, flags=1):
        super().__init__()
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

    def __int__(self):
        return self.value

    def __add__(self, other):
        return self.value + getattr(other, 'value', other)

    def __sub__(self, other):
        return self.value - getattr(other, 'value', other)

    def __mul__(self, other):
        return self.value * getattr(other, 'value', other)

    def __floordiv__(self, other):
        return self.value // getattr(other, 'value', other)

    def __radd__(self, other):
        return self + other

    def __rsub__(self, other):
        return getattr(other, 'value', other) - self.value

    def __rmul__(self, other):
        return self * other

    def __rfloordiv__(self, other):
        return getattr(other, 'value', other) // self.value

    def __iadd__(self, other):
        self.value += getattr(other, 'value', other)
        return self

    def __isub__(self, other):
        self.value -= getattr(other, 'value', other)
        return self

    def __imul__(self, other):
        self.value *= getattr(other, 'value', other)
        return self

    def __ifloordiv__(self, other):
        self.value //= getattr(other, 'value', other)
        return self

    @property
    def value(self):
        """ The value of this die. """
        return self._value

    @value.setter
    def value(self, new_value):
        """ The set value of this die. """
        min_val = 0 if self.is_penetrated() else 1
        if new_value < min_val:
            raise ValueError("Dice value must be >= {}.".format(min_val))

        self._value = new_value

    @property
    def max_roll(self):
        """ Maximum roll is the total number of sides. """
        return self.sides

    def fmt_string(self):
        """ Return the correct formatting string given the die's current flags. """
        fmt = "{}"

        if self.is_rerolled():
            fmt = fmt + "r"
        if self.is_exploded():
            fmt = "__" + fmt + "__"
        if self.is_dropped():
            fmt = "~~" + fmt + "~~"
        if self.is_success():
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

    def explode(self):
        """
        Explode this dice.
        Marks this one as exploded and returns a new dice of same spec.

        Returns:
            A duplicate of the current Die already rolled.
        """
        self.set_explode()
        return self.dupe()


class FateDie(Die):
    """
    A Fate die is nothing more than a d3 where the value is mapped down -2.
    """
    def __init__(self, **kwargs):
        kwargs['sides'] = 3
        super().__init__(**kwargs)

        if 'value' not in kwargs:
            self.value = 0

    def __str__(self):
        value = self.value
        if value == -1:
            value = "-"
        elif value == 1:
            value = "+"

        return self.fmt_string().format(value)

    @property
    def value(self):
        return self._value - 2

    @value.setter
    def value(self, new_value):
        if new_value not in range(-1, 2):
            raise ValueError("FATE/FUDGE dice value must be in [-1, 1].")

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
            if issubclass(type(prev_die), FateDie):
                msg += ' '
            else:
                msg += " + "
            msg += str(die)

        if len(msg) > LIMIT_DICE_SET_STR:
            parts = msg.split(' + ')
            msg = '{} + {} + ... {}'.format(parts[0], parts[1], parts[-1])

        return '(' + msg + ')'

    def __int__(self):
        """ Value represents the integer value of this roll. """
        return self.value

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
    def __init__(self, *, spec=None, parts=None, note=None):
        self.spec = spec
        self.parts = parts if parts else []
        self.note = note

    def __repr__(self):
        return "AThrow(spec={!r}, parts={!r})".format(self.spec, self.parts)

    def __str__(self):
        return " ".join([str(x) for x in self.parts])

    def add(self, part):
        """
        Add one part to the container.

        Args:
            part: A Die subclass or a string that is an operator or a number.
        """
        self.parts += [part]

    def roll(self):
        """ Ensure all not fixed parts reroll. """
        for part in self.parts:
            if issubclass(type(part), DiceSet):
                part.roll()
                part.apply_mods()

    def numeric_value(self):
        """
        Get the numeric value of all rolls summed.

        Returns:
            The total value of the roll.
        """
        value = 0
        next_coeff = 1
        for part in self.parts:
            if part == "-":
                next_coeff = -1

            elif part == "+":
                next_coeff = 1

            else:
                value = value + next_coeff * int(part)

        return value

    def success_string(self):
        """
        Count and print the total number of successes and fails in the complete throw.

        Returns:
            The formatted string to print to user.
        """
        msg = ""
        fcnt = 0
        scnt = 0
        display_success = False
        for part in [x for x in self.parts if issubclass(type(x), DiceSet)]:
            for mod in part.mods:
                if isinstance(mod, SuccessFail):
                    display_success = True

            for die in part.all_die:
                if die.is_fail():
                    fcnt += 1
                elif die.is_success():
                    scnt += 1

        if display_success:
            diff = scnt - fcnt
            msg += "({}{}) **{}** Failure(s), **{}** Success(es)".format(
                '+' if diff >= 0 else '', diff, fcnt, scnt)

        return msg

    def next(self):
        """
        Throw all_dice and return the formatted rolls as a string that shows the
        individual components of the rolls.

        Raises:
            InvalidCommandArgs: Requested an excessive amount of dice rolls, refuse
                                to waste cycles on the server. Used to shortcircuit further
                                attampts.
            ValueError: Some part of the specification failed to parse.

        Returns:
            A string that shows the user how he rolled.
        """
        self.roll()

        success = self.success_string()
        trail = ""
        if success:
            trail += "\n        " + success
        if self.note:
            trail += "\n        Note: " + self.note

        return "{} = {} = {}{}".format(self.spec, str(self), self.numeric_value(), trail)


@functools.total_ordering
class ModifyDice(abc.ABC):
    """
    Standard interface to modify a dice set.

    Consider them like friend functions that modify an existing roll set.
    """
    WEIGHT = 0

    def __eq__(self, other):
        return self.__class__.WEIGHT == other.__class__.WEIGHT

    def __lt__(self, other):
        return self.__class__.WEIGHT < other.__class__.WEIGHT

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


class KeepDrop(ModifyDice):
    """
    Keep or drop N high or low rolls.
    """
    WEIGHT = 4

    def __init__(self, *, keep=True, high=True, num=1):
        self.keep = keep
        self.high = high
        self.num = num

    def __repr__(self):
        return "KeepDrop(keep={!r}, high={!r}, num={!r})".format(
            self.keep, self.high, self.num)

    @staticmethod
    def parse(line, _):
        """
        Parse the line string for an object.
        Supports: kh4, kl3, dh4, dl2

        Raises:
            ValueError: Could not understand specification.

        Returns:
            KeepDrop object on successful parsing.
        """
        match = re.match(r'(k|d)(h|l)?(\d+)', line, re.ASCII | re.IGNORECASE)
        if not match:
            raise ValueError("Keep or Drop spec is invalid.")

        keep = high = match.group(1) == 'k'
        if match.group(2) == 'h':
            high = True
        elif match.group(2) == 'l':
            high = False

        return line[match.end():], KeepDrop(keep=keep, high=high, num=int(match.group(3)))

    def modify(self, dice_set):
        """
        Depending on arguements can, keep or drop the num highest or lowest dice values.
        Will not modify dice that have already been dropped.

        Returns:
            The original DiceSet.
        """
        f_mask = ~(Die.REROLL | Die.DROP) & Die.MASK
        all_die = sorted([d for d in dice_set.all_die if d.flags & f_mask])
        if not self.keep:
            all_die = list(reversed(all_die))

        first, second = ['set_drop', 'NOP'] if self.high else ['NOP', 'set_drop']
        for die in all_die[:-self.num]:
            getattr(die, first, lambda: True)()
        for die in all_die[-self.num:]:
            getattr(die, second, lambda: True)()

        return dice_set


class ExplodeDice(ModifyDice):
    """
    Explode on some predicate.

    Predicate of form:
        def pred(die):
            return True IFF should explode this dice.
    """
    WEIGHT = 2

    def __init__(self, *, pred, penetrate=False):
        self.pred = pred
        self.penetrate = penetrate

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
            ExplodeDice object on successful parsing.
        """
        if line[0] != '!' or line[1] == '!':
            raise ValueError("Exploding spec is invalid.")

        penetrate = False
        if line[1] == 'p':
            penetrate = True
            line = line[1:]

        rest, pred = parse_predicate(line[1:], max_roll)

        return rest, ExplodeDice(pred=pred, penetrate=penetrate)

    def modify(self, dice_set):
        """
        Modifies the actual dice in the dice set.

        Returns:
            The original DiceSet.
        """
        all_die = []
        f_mask = ~(Die.EXPLODE | Die.REROLL) & Die.MASK
        for die in [d for d in dice_set.all_die if d.flags & f_mask]:
            all_die += [die]

            while self.pred(die):
                die = die.explode()
                if self.penetrate:
                    die.set_penetrate()
                all_die += [die]

        for die in [d for d in all_die if d.is_penetrated()]:
            die.value -= 1

        dice_set.all_die = all_die
        return dice_set


class CompoundDice(ExplodeDice):
    """
    A specialized variant of exploding dice.
    """
    WEIGHT = 1

    @staticmethod
    def parse(line, max_roll):
        """
        Parse the line string for an object.
        Supports format: !!6, !!>6, !!<6

        Raises:
            ValueError: Could not understand specification.

        Returns:
            CompoundDice object on successful parsing.
        """
        if line[0:2] != '!!':
            raise ValueError("Compounding spec is invalid.")

        rest, pred = parse_predicate(line[2:], max_roll)

        return rest, CompoundDice(pred=pred)

    def modify(self, dice_set):
        """
        Keep exploding the dice until predicate failes.
        All rolls are simply added to first explosion.
        """
        f_mask = ~(Die.EXPLODE | Die.REROLL) & Die.MASK
        for die in [d for d in dice_set.all_die if d.flags & f_mask]:
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
    WEIGHT = 3

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
        if line[0] != 'r':
            raise ValueError("Reroll spec is invalid.")

        possible = list(range(1, max_roll + 1))
        invalid = []
        while line:
            if not line[0] == 'r':
                break

            try:
                line, pred = parse_predicate(line[1:], max_roll)
                invalid += [x for x in possible if pred(x)]
            except ValueError:
                break

        if not invalid:
            raise ValueError("Reroll spec is invalid.")

        invalid = sorted(set(invalid))
        if not set(possible) - set(invalid):
            raise ValueError("Reroll predicates are impossible. Would always reroll!")

        return line, RerollDice(invalid_rolls=invalid)

    def modify(self, dice_set):
        for die in dice_set.all_die.copy():
            while die.value in self.invalid_rolls:
                die.set_reroll()
                die.set_drop()
                die = die.dupe()
                dice_set.all_die += [die]


class SuccessFail(ModifyDice):
    """
    Set predicates to trigger the success or fail of a die.
    Dice that failed the predicate will be set to fail.
    """
    WEIGHT = 5

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
            Success: '=2', success if equal to 2, '<2' success on <=2 , '>5' success on >= 5
            Fail: 'f1' fail if == 1, 'f<3' fail on <=3, 'f>4' fail on >=4

        Raises:
            ValueError: Could not understand specification.

        Returns:
            Returns a SuccessFail object ready to mark based on predicate.
        """
        mark_success = True
        if line[0] == 'f':
            mark_success = False
            line = line[1:]
        elif line[0] not in ['>', '<', '=', '[']:
            raise ValueError("Success or Fail spec is invalid.")

        rest, pred = parse_predicate(line, max_roll)

        return rest, SuccessFail(pred=pred, mark_success=mark_success)

    def modify(self, dice_set):
        f_mask = ~(Die.REROLL | Die.DROP | Die.FAIL | Die.SUCCESS) & Die.MASK
        for die in [x for x in dice_set.all_die if x.flags & f_mask]:
            if self.pred(die):
                getattr(die, self.mark)()


class SortDice(ModifyDice):
    """
    Sort the final dice in ascending or descending order.
    Importantly, rerolls and dropped dice will be sorted below, remainder to right and sorted.
    """
    WEIGHT = 6

    def __init__(self, *, ascending=True):
        self.ascending = ascending

    def __repr__(self):
        return "SortDice(ascending={!r})".format(self.ascending)

    @staticmethod
    def parse(line, max_roll):
        """
        Parse a line for success or failure criteria for the associated dice.
        Supports:
            Success: '=2', success if equal to 2, '<2' success on <=2 , '>5' success on >= 5
            Fail: 'f1' fail if == 1, 'f<3' fail on <=3, 'f>4' fail on >=4

        Raises:
            ValueError: Could not understand specification.

        Returns:
            Returns a SuccessFail object ready to mark based on predicate.
        """
        if line[0] != 's':
            raise ValueError("Sort spec is invalid.")

        ascending = True
        rest = line[1:]
        try:
            if rest[0] == 'd':
                ascending = False
            if rest[0] in ['a', 'd']:
                rest = rest[1:]
        except IndexError:
            pass

        return rest, SortDice(ascending=ascending)

    def modify(self, dice_set):
        ordered = sorted(dice_set.all_die)
        if not self.ascending:
            ordered = list(reversed(ordered))
        dice_set.all_die = ordered
