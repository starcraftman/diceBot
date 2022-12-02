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
# TODO: Strong overlap between Die and DiceList?
# TODO: Grouped rolls {2d10,4d20}kh1, take highest total value.
import abc
import functools
import re

import numpy.random as rand

import dice.exc
from dice.util import ReprMixin

PAD_LEN = 8
IS_DIE = re.compile(r'(\d+)?d(\d+)', re.ASCII | re.IGNORECASE)
IS_FATEDIE = re.compile(r'(\d+)?df', re.ASCII | re.IGNORECASE)
IS_LITERAL = re.compile(r'([-+])|([0-9]+\b)', re.ASCII)
IS_PREDICATE = re.compile(r'(>)?(<)?\[?(=?\d+)(,\d+\])?', re.ASCII)
REROLL_MATCH = re.compile(r'(ro?\[\d+,\d+\])|(ro?[><=]\d+)|(ro?\d+)', re.ASCII | re.IGNORECASE)
LIMIT_DIE_NUMBER = 1000
LIMIT_DIE_SIDES = 1000
LIMIT_DICE_LIST_STR = 200
PARENS_MAP = {'(': 3, '{': 7, '[': 11, ')': -3, '}': -7, ']': -11}
DICE_WARN = """**Error**: {}
        {}
Please see reference below and correct the roll.

__Quick Reference__

    5**:** 4d6 + 2                    Roll __5__ times, 4d6 + 2
    d20 + 5**,** d8 + 3           Roll d20 + 5, then separately d8 + 3.
    4d6 For Gordon          Roll 4d6, non-roll related text following roll is replayed with result.
    4d6**kh2**                        Roll 4d6 and keep __2__ highest results
    4d6**dl2**                         Roll 4d6 and drop the __2__ lowest results
    4d6**r1r[5,6]**                Roll 4d6 and reroll if dice lands on 1, 5 or 6
    4d6**ro[5,6]**                  Roll 4d6 and reroll if dice lands on 5 or 6 __exactly once__
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

All modifiers that support comparisons support all available comparisons.

See `!roll --help` for more complete documentation.
"""


class Comparison(ReprMixin, abc.ABC):
    """
    The only reason this exists is that lambda functions don't automatically
    pickle like objects do.
    Subclasses are used as predicates that determine when modifiers apply.

    Attributes:
        left: The left bound of the comparison (default used if not a range).
        right: The right bound of the comparison.
    """
    _repr_keys = ['left']

    def __init__(self, *, left=0):
        self.left = left

    @abc.abstractmethod
    def __call__(self, other):
        """
        Implement the actual comparison here.

        Returns:
            True IFF the comparison is true for other (an integer cast supporting object).
        """
        raise NotImplementedError


class CompareEqual(Comparison):  # pylint: disable=too-few-public-methods
    """
    Compare if an object is equal to a value.
    """
    def __call__(self, other):
        """
        Check other == predetermined value (left).

        Returns:
            True IFF other other == left.
        """
        return int(other) == self.left


class CompareLessEqual(Comparison):  # pylint: disable=too-few-public-methods
    """
    Compare if an object is less or equal to a value.
    """
    def __call__(self, other):
        """
        Check other for <= predetermined value (left).

        Returns:
            True IFF other is <= left.
        """
        return int(other) <= self.left


class CompareGreaterEqual(Comparison):  # pylint: disable=too-few-public-methods
    """
    Compare if an object is greater or equal to a value.
    """
    def __call__(self, other):
        """
        Check other for >= predetermined value (left).

        Returns:
            True IFF other is <= left.
        """
        return int(other) >= self.left


class CompareRange(Comparison):  # pylint: disable=too-few-public-methods
    """
    Compare if an object of integer value is in a range.
    """
    _repr_keys = ['left', 'right']

    def __init__(self, *, left=0, right=0):
        super().__init__(left=left)
        self.right = right

    def __call__(self, other):
        """
        Implement a simple range check predicate against other.

        Returns:
            True IFF other is in range [left, right].
        """
        return self.left <= int(other) <= self.right


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
        (substr, obj)
            substr: The remainder of line after processing.
            comp: A Comp predicate.
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
        comp = CompareRange(left=val, right=right)

    elif match.group(1):
        if val <= 1:
            raise ValueError(DICE_WARN.format("Predicate will always be true (>=).", line))
        comp = CompareGreaterEqual(left=val)

    elif match.group(2):
        if val >= max_roll:
            raise ValueError(DICE_WARN.format("Predicate will always be true (<=).", line))
        comp = CompareLessEqual(left=val)

    else:
        comp = CompareEqual(left=val)

    return line[match.end():], comp


def parse_dicelist(line):
    """
    Attempt to parse a dice list from the line.

    Raises:
        ValueError: No dice specification could be found at the start of line.
        InvalidCommandArgs: User specified an amount of dice or sides that is unreasonable.

    Returns:
        (line, dlist)
            line: The remainder of line after processing.
            dlist: A DiceList object containing the dice and any modifiers.
    """
    match = IS_DIE.match(line)
    if not match:
        raise ValueError(DICE_WARN.format("Invalid D20 dice roll.", line))

    number = int(match.group(1)) if match.group(1) else 1
    sides = int(match.group(2))
    if sides > LIMIT_DIE_SIDES or number > LIMIT_DIE_NUMBER:
        raise dice.exc.InvalidCommandArgs("Please roll a lower number of dice or sides.")

    dlist = DiceList()
    dlist.add_dice(number, sides)

    line, mods = parse_trailing_mods(line[match.end():], dlist.max_roll)
    dlist.mods = sorted(mods)

    return line, dlist


def parse_fate_dicelist(line):
    """
    Attempt to parse a fate dice list from the line.

    Raises:
        ValueError: No dice specification could be found at the start of line.
        InvalidCommandArgs: User specified an amount of dice that is unreasonable.

    Returns:
        (line, dlist)
            line: The remainder of line after processing.
            dlist: A DiceList object containing the dice and any modifiers.
    """
    match = IS_FATEDIE.match(line)
    if not match:
        raise ValueError(DICE_WARN.format("Invalid FATE/FUDGE dice roll.", line))

    number = int(match.group(1)) if match.group(1) else 1
    if number > LIMIT_DIE_NUMBER:
        raise dice.exc.InvalidCommandArgs("Please roll a lower number of dice.")

    dlist = DiceList()
    dlist.add_fatedice(number)

    line, mods = parse_trailing_mods(line[match.end():], dlist.max_roll)
    dlist.mods = sorted(mods)

    return line, dlist


def parse_trailing_mods(line, max_roll):
    """
    Attempt to parse the remaining modifiers of a dice list.

    Raises:
        ValueError: A failure to parse part of the modifiers.

    Returns:
        (line, mods)
            line: The remainder of line after processing.
            mods: A list of modifiers to apply to a DiceList.
    """
    mods = []
    while line:
        if line[0] in [' ', '}', ',', '+', '-', '*', '/']:
            break

        mod = None
        for cls in (CompoundDice, ExplodeDice, RerollDice,
                    KeepDrop, SuccessFail, SortDice):
            if cls.should_parse(line):
                line, mod = cls.parse(line, max_roll)
                break

        if not mod:
            raise ValueError("Unable to parse dice spec, stuck at: " + line)

        mods += [mod]

    return line, mods


def parse_literal(line):
    """
    Parse allowed literals in the dice spec line and return them.

    Raises:
        ValueError: Disallowed literals were found.

    Returns:
        (line, literal)
            line: The remainder of line after processing.
            literal: A literal string that is supported.
    """
    match = IS_LITERAL.match(line)
    if not match:
        raise ValueError("There is no valid literal to parse.")

    if match.group(2):
        literal = match.group(2)
    else:
        literal = match.group(1)

    return line[match.end():], literal


def check_parentheses(line):
    """
    Go over a string and ensure it has one opening and closing parentheses.

    Raises:
        ValueError: The parentheses are not balanced.

    Returns:
        The line that was passed in.
    """
    cnt = 0
    for char in line:
        if char in PARENS_MAP:
            cnt += PARENS_MAP[char]

    if cnt != 0:
        raise ValueError(DICE_WARN.format("Unbalanced parentheses detected.", line))

    return line


def parse_comments_from_back(line):
    """
    Scan for tokens back to front in line.
    Any token that does not start with a valid dice spec or a literal is a comment.
    Return separately the line substring without comments and the comments.

    Returns:
        (line, comment):
            line: Remainder of the line that is not a comment.
            comment: The part of the line that is a comment.
    """
    token, comment = '', ''
    word_boundary = False

    pos = len(line) - 1
    while pos != -1:
        token = line[pos] + token

        if not line[1:] or (word_boundary and line[pos].isspace()):
            is_comment, token_copy = True, token.strip()
            for matcher in [IS_DIE, IS_FATEDIE, IS_LITERAL]:
                if matcher.match(token_copy):
                    is_comment = False
                    break

            if is_comment:
                comment = token + comment
            else:
                line += token[1:]
                break
            token, word_boundary = '', False

        elif not line[pos].isspace():
            word_boundary = True

        pos, line = pos - 1, line[:-1]

    return line, comment.strip()


def parse_dice_line(line):
    """
    Take a complete dice specification with optional literals and return
    AThrow object containing all required parts to model the throw.

    Examples valid:
        4d20kh2 + 6d6 + 20
    Examples invalid:
        4: 6d6, 4d20 + 2
        6d6 + 2, d8 + 4

    Raises:
        ValueError: Some part of the dice spec could not be parsed.

    Returns:
        AThrow object with the required parts.
    """
    spec, note = parse_comments_from_back(line)
    throw = AThrow(spec=check_parentheses(spec).rstrip(), note=note)

    while spec:
        if spec[0].isspace():
            spec = spec[1:]
            continue

        obj = None
        for func in [parse_dicelist, parse_fate_dicelist, parse_literal]:
            try:
                spec, obj = func(spec)
                throw += [obj]
                break
            except ValueError:
                pass

        if not obj:
            raise ValueError(DICE_WARN.format("Failed to parse part of line.", spec))

    if not throw:
        raise ValueError(DICE_WARN.format("No dice specification detected.", line))

    return throw


class FlaggableMixin():
    """
    Store a series of flags in a bit field that tracks a series of states.
    States can be toggled by named methods or directly with flag masks.
    Some flags toggle other flags if they are exclusive.

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
class Die(ReprMixin, FlaggableMixin):
    """
    Model a single dice with n sides, it can:
        - roll itself
        - format itself for user
        - flag itself to track states
        - duplicate itself if needed

    Attributes:
        sides: The die has this many sides.
        _value: The value of the last roll, always [1, sides].
        flags: The flags tracking the Die's state.
    """
    _repr_keys = ['sides', 'value', 'flags']

    def __init__(self, *, sides=1, value=1, flags=1):
        super().__init__()
        self.sides = sides
        self._value = value
        self.flags = flags

    def __str__(self):
        return self.fmt_string().format(self.value)

    def __hash__(self):
        return hash(f'{self.sides}_{self.value}')

    def __eq__(self, other):
        return issubclass(type(other), Die) and self.value == other.value

    def __lt__(self, other):
        return issubclass(type(other), Die) and self.value < other.value

    def __int__(self):
        return self.value

    @property
    def value(self):
        """ The value of this die. """
        return self._value

    @value.setter
    def value(self, new_value):
        """ The set value of this die. """
        min_val = 0 if self.is_penetrated() else 1
        if new_value < min_val:
            raise ValueError(f"Dice value must be >= {min_val}.")

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
    Representation is modified to be -, 0 or + due to the possible values.
    """
    def __init__(self, **kwargs):
        kwargs['sides'] = 3
        if 'value' not in kwargs:
            kwargs['value'] = 2

        super().__init__(**kwargs)

    def __repr__(self):
        kwargs = [f'{key}={getattr(self, key)!r}' for key in ['sides', '_value', 'flags']]
        return f'{self.__class__.__name__}({", ".join(kwargs)})'.replace('_value', 'value')

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


class DiceList(list):
    """
    A dice list is simply a collection of dice.
    Allow modifiers to be added to the list and applied after rolling.

    Attributes:
        items: The dice in the list, the main list stores them.
        mods: The modifiers that apply to the parts.
    """
    def __init__(self, *, items=None, mods=None):
        super().__init__(items if items else [])
        self.mods = mods if mods else []

    def __repr__(self):
        return f"DiceList(items={self[:]!r}, mods={self.mods!r})"

    def __str__(self):
        if not self:
            return ""

        msg = str(self[0])
        for prev_die, die in zip(self[:-1], self[1:]):
            if issubclass(type(prev_die), FateDie):
                msg += ' '
            else:
                msg += " + "
            msg += str(die)

        if len(msg) > LIMIT_DICE_LIST_STR:
            parts = msg.split(' ')
            msg = f"{' '.join(parts[:4])} ... {parts[-1]}"

        return '(' + msg + ')'

    def __eq__(self, other):
        if not isinstance(other, DiceList) or len(self) != len(other):
            return False

        for die, o_die in zip(self, other):
            if die != o_die:
                return False

        return True

    def __int__(self):
        """ Value represents the integer value of this roll. """
        return self.value

    @property
    def value(self):
        """ The value of this grouping is the sum of all non-dropped rolls. """
        return sum(x.value for x in self if x.is_kept())

    @property
    def max_roll(self):
        """ The lowest maximum roll within this dice list. """
        return min(x.max_roll for x in self)

    def add_dice(self, number, sides):
        """
        Add a number of Die to this list.
        All Die default to value of 1 until rolled.

        Args:
            number: The number of Die to add.
            sides: The number of sides on the Die.
        """
        self.extend([Die(sides=sides) for _ in range(0, number)])

    def add_fatedice(self, number):
        """
        Add a number of FateDie to this list.
        All FateDie default to value of 0 until rolled.

        Args:
            number: The number of FateDie to add.
        """
        self.extend([FateDie() for _ in range(0, number)])

    def roll(self):
        """
        Roll all the die in this list.
        """
        for die in self:
            die.roll()
            die.reset_flags()

    def apply_mods(self):
        """
        Apply the modifers to the current roll of die.
        """
        for mod in self.mods:
            mod.modify(self)


class AThrow(list):
    """
    A container that represents an entire throw line.
    Composed of the following elements:
        - DiceLists (made of Die and FateDie + modifiers)
        - Constants
        - Operators

    Attributes:
        spec: The original spec that created the line.
        note: Any comment user wanted attached to roll.
        json: If true, throws return a json output. Otherwise a simple string.
    """
    def __init__(self, *, items=None, spec=None, note=None, json=False):
        super().__init__(items if items else [])
        self.spec = spec
        self.note = note
        self.json = json

    def __repr__(self):
        return f"AThrow(spec={self.spec!r}, note={self.note!r}, json={self.json}, items={self[:]!r})"

    def __str__(self):
        return " ".join([str(x) for x in self])

    def __eq__(self, other):
        if not isinstance(other, AThrow) or len(self) != len(other):
            return False

        for parts, o_parts in zip(self, other):
            if parts != o_parts:
                return False

        return True

    @property
    def value(self):
        """
        Get the numeric value of all rolls summed.

        Returns:
            The total value of the roll.
        """
        value = 0
        next_coeff = 1
        for part in self:
            if part == "-":
                next_coeff *= -1

            elif part == "+":
                next_coeff = 1

            else:
                value = value + next_coeff * int(part)

        return value

    def roll(self):
        """ Ensure all not fixed parts reroll. """
        for part in self:
            if issubclass(type(part), DiceList):
                part.roll()
                part.apply_mods()

    def success_string(self):
        """
        Count and print the total number of successes and fails in the complete throw.

        Returns:
            The formatted string to print to user.
        """
        msg, fcnt, scnt = "", 0, 0
        display_success = False
        for dlist in [d for d in self if issubclass(type(d), DiceList)]:
            for mod in dlist.mods:
                if isinstance(mod, SuccessFail):
                    display_success = True

            for die in dlist:
                if die.is_fail():
                    fcnt += 1
                elif die.is_success():
                    scnt += 1

        if display_success:
            diff = scnt - fcnt
            psign = '+' if diff >= 0 else ''
            msg += f"({psign}{diff}) **{fcnt}** Failure(s), **{scnt}** Success(es)"

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
            If self.json is True, return a json with all information on roll.
            If self.json is False, a string that shows the user how he rolled.
        """
        self.roll()

        result = {
            'note': self.note,
            'spec': self.spec,
            'success': self.success_string(),
            'value': self.value,
            'steps': str(self),
        }
        result['output'] = throw_output(result)

        return result if self.json else result['output']


def throw_output(result):
    """
    Using a result dict from a throw, combine them into expected output format.

    Args:
        result: A dict object with all information required.

    Returns:
        A string formatted to present important information of roll.
    """
    pad = PAD_LEN * " "
    trail = ""
    if result['success']:
        trail += f"\n{pad}{result['success']}"
    if result['note']:
        trail += f"\n{pad}Note: {result['note']}"

    return f"{result['spec']} = {result['steps']} = {result['value']}{trail}"


@functools.total_ordering
class ModifyDice(abc.ABC):
    """
    Standard interface to modify a dice list.
    Class attribute WEIGHT is used in ordering modifiers before applying.
    Consider them like friend functions they modify the dice rolls once settled.
    """
    WEIGHT = 0

    def __eq__(self, other):
        return self.__class__.WEIGHT == other.__class__.WEIGHT

    def __lt__(self, other):
        return self.__class__.WEIGHT < other.__class__.WEIGHT

    @staticmethod
    @abc.abstractmethod
    def should_parse(line):
        """
        Check if this modifier should attempt to parse the upcoming tokens.

        Args:
            line: A substring of the dice spec that conforms to the modifier's spec.

        Returns:
            True iff the modification should parse the next tokens.
        """
        raise NotImplementedError

    @staticmethod
    @abc.abstractmethod
    def parse(line, max_roll):
        """
        A method to parse a line and return the associated ModifyDice subclass
        if and only if enough information is present.
        The max_roll is used to check if any predicates would be invalid that may be required.

        Args:
            line: A substring of the dice spec that conforms to the modifier's spec.
            max_roll: The maximum roll of the dice in the collection. For example, d6 = 6.

        Raises:
            ValueError: Incomplete or impossible spec, abort processing.

        Returns:
            (line, mod)
                line: The remainder of line after processing.
                mod: A ModifyDice object ready to be applied to a DiceList.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def modify(self, dice_list):
        """
        Apply the modifier to the dice and make marks/selections as required.
        Modifies the dice_list directly.

        Args:
            dice_list: A collection of dice.
        """
        raise NotImplementedError


class ExplodeDice(ReprMixin, ModifyDice):
    """
    Explode when the associated predicate is true.
    Support normal explosion criteria and penetrated die.

    Attributes:
        pred: The predicate determining when to explode.
        penetrate: True if the die will penetrate on roll, else false.
    """
    WEIGHT = 2
    _repr_keys = ['pred', 'penetrate']

    def __init__(self, *, pred, penetrate=False):
        self.pred = pred
        self.penetrate = penetrate

    @staticmethod
    def should_parse(line):
        return line.startswith('!')

    @staticmethod
    def parse(line, max_roll):
        if line[0] != '!' or line[1] == '!':
            raise ValueError("Exploding spec is invalid.")

        penetrate = False
        if line[1] == 'p':
            penetrate = True
            line = line[1:]

        line, pred = parse_predicate(line[1:], max_roll)

        return line, ExplodeDice(pred=pred, penetrate=penetrate)

    def modify(self, dice_list):
        parts = []
        for die in [d for d in dice_list if d.flags & (Die.EXPLODE | Die.REROLL) == 0]:
            parts += [die]

            while self.pred(die):
                die = die.explode()
                if self.penetrate:
                    die.set_penetrate()
                parts += [die]

        for die in [d for d in parts if d.is_penetrated()]:
            die.value -= 1

        dice_list[:] = parts


class CompoundDice(ExplodeDice):
    """
    A specialized variant of exploding dice.
    When the predicate is true keep exploding until it is false.
    On each explosion add the new value to the original dice.

    Attributes:
        pred: The predicate determining when to explode.
        penetrate: Always false, inherited.
    """
    WEIGHT = 1

    @staticmethod
    def should_parse(line):
        return line.startswith('!!')

    @staticmethod
    def parse(line, max_roll):
        if line[0:2] != '!!':
            raise ValueError("Compounding spec is invalid.")

        line, pred = parse_predicate(line[2:], max_roll)

        return line, CompoundDice(pred=pred)

    def modify(self, dice_list):
        for die in [d for d in dice_list if d.flags & (Die.EXPLODE | Die.REROLL) == 0]:
            new_explode = die
            while self.pred(new_explode):
                new_explode = die.explode()
                die.value += new_explode.value


class RerollDice(ReprMixin, ModifyDice):
    """
    Define conditions when dice should be rerolled.
    Rerolls will be checked for impossible combinations:
        - Cannot reroll all possible values or no values.
        - Cannot overlap between normal rerolls and reroll once ranges.

    Attributes:
        reroll_always: The list of values that will trigger keep triggering reroll.
        reroll_once: The list of values that will trigger a single reroll.
    """
    WEIGHT = 3
    _repr_keys = ['reroll_always', 'reroll_once']

    def __init__(self, *, reroll_always=None, reroll_once=None):
        self.reroll_always = reroll_always if reroll_always else []
        self.reroll_once = reroll_once if reroll_once else []

    @staticmethod
    def should_parse(line):
        return line.startswith('r')

    @staticmethod
    def parse(line, max_roll):
        if line[0] != 'r':
            raise ValueError("Reroll spec is invalid.")

        reroll_always, reroll_once = [], []
        line_copy = line[:].lower()
        for part in REROLL_MATCH.finditer(line_copy):
            substr = line_copy[part.start():part.end()]
            offset = 2 if substr[1] == 'o' else 1
            _, pred = parse_predicate(substr[offset:], max_roll)

            if substr[1] == 'o':
                reroll_once += [pred]
            else:
                reroll_always += [pred]
            line = line.replace(substr, '', 1)

        possible = list(range(1, max_roll + 1))
        reroll_always = {x for x in possible if any(pred(x) for pred in reroll_always)}
        reroll_once = {x for x in possible if any(pred(x) for pred in reroll_once)}

        if (not reroll_always and not reroll_once) or not set(possible) - reroll_always - reroll_once:
            raise ValueError("Reroll predicates are invalid. Combination Would always or never reroll!")

        if reroll_always & reroll_once:
            raise ValueError("Do not overlap normal reroll and reroll once ranges.")

        return line, RerollDice(reroll_always=sorted(reroll_always),
                                reroll_once=sorted(reroll_once))

    def modify(self, dice_list):
        new_list = []
        for die in dice_list:
            new_list += [die]
            if die.flags & (Die.EXPLODE | Die.REROLL):
                continue

            if die.value in self.reroll_once:
                die.set_reroll()
                die.set_drop()
                die = die.dupe()
                new_list += [die]
                continue

            while die.value in self.reroll_always:
                die.set_reroll()
                die.set_drop()
                die = die.dupe()
                new_list += [die]

        dice_list.clear()
        dice_list += new_list


class KeepDrop(ReprMixin, ModifyDice):
    """
    Keep or drop N high or low rolls.

    Attributes:
        keep: True if we should keep num elements, else will drop num elements.
        high: When True, select from highest values. When False, select from lowest.
        num: The number to keep or drop.
    """
    WEIGHT = 4
    _repr_keys = ['keep', 'high', 'num']

    def __init__(self, *, keep=True, high=True, num=1):
        self.keep = keep
        self.high = high
        self.num = num

    @staticmethod
    def should_parse(line):
        return line and line[0] in ['k', 'd']

    @staticmethod
    def parse(line, _):
        match = re.match(r'(k|d)(h|l)?(\d+)', line, re.ASCII | re.IGNORECASE)
        if not match:
            raise ValueError("Keep or Drop spec is invalid.")

        keep = high = match.group(1) == 'k'
        if match.group(2) == 'h':
            high = True
        elif match.group(2) == 'l':
            high = False

        return line[match.end():], KeepDrop(keep=keep, high=high, num=int(match.group(3)))

    def modify(self, dice_list):
        parts = sorted([d for d in dice_list if d.flags & (Die.DROP | Die.REROLL) == 0])
        if not self.keep:
            parts = list(reversed(parts))

        first, second = ['set_drop', 'NOP'] if self.high else ['NOP', 'set_drop']
        for die in parts[:-self.num]:
            getattr(die, first, lambda: True)()
        for die in parts[-self.num:]:
            getattr(die, second, lambda: True)()


class SuccessFail(ModifyDice):
    """
    Apply a predicate to all dice and either set failure or success.
    Success and failure are independent and no assumption of the other is made when one set.

    Attributes:
        pred: The predicate that determines when to set mark.
        mark: The method to invoke on the die to set state.
    """
    WEIGHT = 5
    _repr_keys = ['pred', 'mark_success']

    def __init__(self, *, pred, mark_success=True):
        self.pred = pred
        self.mark = 'set_success' if mark_success else 'set_fail'

    @staticmethod
    def should_parse(line):
        return line and (line[0] == 'f' or IS_PREDICATE.match(line))

    @staticmethod
    def parse(line, max_roll):
        mark_success = True
        if line[0] == 'f':
            mark_success = False
            line = line[1:]
        elif line[0] not in ['>', '<', '=', '[']:
            raise ValueError("Success or Fail spec is invalid.")

        line, pred = parse_predicate(line, max_roll)

        return line, SuccessFail(pred=pred, mark_success=mark_success)

    def modify(self, dice_list):
        for die in [d for d in dice_list if d.flags & (Die.DROP | Die.REROLL | Die.FAIL | Die.SUCCESS) == 0]:
            if self.pred(die):
                getattr(die, self.mark)()


class SortDice(ModifyDice):
    """
    Sort the final dice in ascending or descending order.

    Attributes:
        ascending: Sort will be in order from smallest to largest rolls.
    """
    WEIGHT = 6
    _repr_keys = ['ascending']

    def __init__(self, *, ascending=True):
        self.ascending = ascending

    @staticmethod
    def should_parse(line):
        return line.startswith('s')

    @staticmethod
    def parse(line, max_roll):
        if line[0] != 's':
            raise ValueError("Sort spec is invalid.")

        ascending = True
        line = line[1:]
        try:
            if line[0] == 'd':
                ascending = False
            if line[0] in ['a', 'd']:
                line = line[1:]
        except IndexError:
            pass

        return line, SortDice(ascending=ascending)

    def modify(self, dice_list):
        ordered = sorted(dice_list)
        if not self.ascending:
            ordered = list(reversed(ordered))

        dice_list[:] = ordered


def main():
    """ Try dice rolls interactively. """
    while True:
        try:
            text = input('> ')
            throw = parse_dice_line(text)
            print(throw.next())
        except ValueError as exc:
            print(exc)


if __name__ == "__main__":
    main()
