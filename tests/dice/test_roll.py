"""
Tests for dice rolling in dice.roll
"""
from __future__ import absolute_import, print_function

import pytest

import dice.roll


def test_fixed__str__():
    die = dice.roll.FixedRoll('5')
    assert str(die) == '(5)'
    die.next_op = '+'
    assert str(die) == '(5) + '
    die.next_op = '-'
    assert str(die) == '(5) - '


def test_fixed__str__many_die():
    die = dice.roll.FixedRoll('5')
    die.values = [1 for x in range(dice.roll.MAX_DIE_STR * 2)]
    assert str(die) == '(1, ..., 1)'


def test_fixed_spec():
    assert dice.roll.FixedRoll('5').spec == '(5)'


def test_fixed_roll():
    assert dice.roll.FixedRoll('5').roll() == 5


def test_fixed_num():
    assert dice.roll.FixedRoll('5').num == 5


def test_fixed_add():
    fd1 = dice.roll.FixedRoll('5')
    fd2 = dice.roll.FixedRoll('3')
    assert (fd1 + fd2).num == 8


def test_fixed_add_raise():
    die = dice.roll.FixedRoll('4')
    with pytest.raises(TypeError):
        assert die + 4


def test_fixed_sub():
    fd1 = dice.roll.FixedRoll('5')
    fd2 = dice.roll.FixedRoll('3')
    assert (fd1 - fd2).num == 2


def test_fixed_sub_raise():
    die = dice.roll.FixedRoll('4')
    with pytest.raises(TypeError):
        assert die - 4


def test_dice__init__():
    die = dice.roll.DiceRoll('2d6')
    assert die.rolls == 2
    assert die.sides == 6


def test_dice__repr__():
    die = dice.roll.DiceRoll('2d6')
    die.values = [2, 3]
    assert repr(die) == "DiceRoll(rolls=2, sides=6, next_op='', values=[2, 3], acu='')"


def test_dice__str__():
    die = dice.roll.DiceRoll('2d6')
    die.values = [2, 3]
    assert str(die) == '(2 + 3)'


def test_dice_num():
    die = dice.roll.DiceRoll('2d6')
    die.values = [2, 3]
    assert die.num == 5


def test_dice_roll():
    die = dice.roll.DiceRoll('2d6')
    die.roll()
    assert die.num in list(range(2, 13))
    for val in die.values:
        assert val in list(range(1, 7))


def test_dice_spec():
    die = dice.roll.DiceRoll('2d6')
    assert die.spec == '(2d6)'


def test_dicekeephigh__init__():
    die = dice.roll.DiceRollKeepHigh('3d6kh2')
    assert die.keep == 2
    assert die.rolls == 3
    assert die.sides == 6

    die = dice.roll.DiceRollKeepHigh('3d6k2')
    assert die.keep == 2
    assert die.rolls == 3
    assert die.sides == 6


def test_dicekeephigh__repr__():
    die = dice.roll.DiceRollKeepHigh('3d6kh2')
    die.values = [3, 2, 5]
    assert repr(die) == "DiceRollKeepHigh(rolls=3, sides=6, keep=2, next_op='', values=[3, 2, 5], acu='')"


def test_dicekeephigh__str__():
    die = dice.roll.DiceRollKeepHigh('3d6kh2')
    die.values = [3, 2, 5]
    assert str(die) == '(3 + ~~2~~ + 5)'


def test_dicekeephigh__str__many():
    die = dice.roll.DiceRollKeepHigh('3d6kh2')
    die.values = [3, 2, 5] + [1 for x in range(dice.roll.MAX_DIE_STR * 2)]
    assert str(die) == '(3, ..., 1)'


def test_dicekeephigh_num():
    die = dice.roll.DiceRollKeepHigh('3d6kh2')
    die.values = [3, 2, 5]
    assert die.num == 8


def test_dicekeephigh_spec():
    die = dice.roll.DiceRollKeepHigh('3d6kh2')
    assert die.spec == '(3d6kh2)'


def test_dicekeeplow__init__():
    die = dice.roll.DiceRollKeepLow('3d6kl2')
    assert die.keep == 2
    assert die.rolls == 3
    assert die.sides == 6


def test_dicekeeplow__str__():
    die = dice.roll.DiceRollKeepLow('3d6kl2')
    die.values = [3, 2, 5]
    assert str(die) == '(3 + 2 + ~~5~~)'


def test_dicekeeplow__str__many():
    die = dice.roll.DiceRollKeepLow('3d6kl2')
    die.values = [3, 2, 5] + [1 for x in range(dice.roll.MAX_DIE_STR * 2)]
    assert str(die) == '(3, ..., 1)'


def test_dicekeeplow_num():
    die = dice.roll.DiceRollKeepLow('3d6kl2')
    die.values = [3, 2, 5]
    assert die.num == 5


def test_dicekeeplow_spec():
    die = dice.roll.DiceRollKeepLow('3d6kl2')
    assert die.spec == '(3d6kl2)'


def test_throw__init__():
    die = dice.roll.DiceRoll('2d6', next_op='-')
    die2 = dice.roll.FixedRoll('4')
    throw = dice.roll.Throw([die, die2])
    assert throw.all_dice == [die, die2]


def test_throw_add_all():
    die = dice.roll.FixedRoll('4')
    throw = dice.roll.Throw()
    throw.add_all([die])
    assert throw.all_dice == [die]


def test_throw_add_all_raise():
    die = dice.roll.FixedRoll('4')
    throw = dice.roll.Throw()
    with pytest.raises(TypeError):
        throw.add_all([die, 2])


def test_throw_next():
    die = dice.roll.DiceRoll('2d6', next_op='+')
    die2 = dice.roll.FixedRoll('1')
    throw = dice.roll.Throw([die, die2])
    throw.next()

    total = 0
    for die in throw.all_dice:
        total += die.num
    assert total in list(range(3, 14))


def test_throw_next_excessive():
    die = dice.roll.DiceRoll('2d6', next_op='+')
    die.rolls = dice.roll.DICE_ROLL_LIMIT + 1
    die2 = dice.roll.FixedRoll('1')
    throw = dice.roll.Throw([die, die2])
    with pytest.raises(dice.exc.InvalidCommandArgs):
        throw.next()


def test_parse_dice_spec():
    assert dice.roll.parse_dice_spec('2d6') == {'rolls': 2, 'sides': 6}
    assert dice.roll.parse_dice_spec('2D6') == {'rolls': 2, 'sides': 6}
    assert dice.roll.parse_dice_spec('6') == {'rolls': 1, 'sides': 6}


def test_parse_dice_spec_raise():
    with pytest.raises(dice.exc.InvalidCommandArgs):
        assert dice.roll.parse_dice_spec('-1d6')
    with pytest.raises(dice.exc.InvalidCommandArgs):
        assert dice.roll.parse_dice_spec('2d-1')
    with pytest.raises(dice.exc.InvalidCommandArgs):
        assert dice.roll.parse_dice_spec('2dworks')
    with pytest.raises(dice.exc.InvalidCommandArgs):
        assert dice.roll.parse_dice_spec('')


def test_tokenize_dice_spec():
    spec = '4D6KH3 + 2D6 - 4 + 2d6kl1'

    dies = dice.roll.tokenize_dice_spec(spec)
    assert isinstance(dies[0], dice.roll.DiceRollKeepHigh)
    assert dies[0].next_op == '+'
    assert isinstance(dies[1], dice.roll.DiceRoll)
    assert dies[1].next_op == '-'
    assert isinstance(dies[2], dice.roll.FixedRoll)
    assert dies[2].next_op == '+'
    assert isinstance(dies[3], dice.roll.DiceRollKeepLow)
    assert len(dies) == 4


def test_tokenize_dice_spec_raises():
    spec = '4D6KH3kl1'
    with pytest.raises(dice.exc.InvalidCommandArgs):
        dice.roll.tokenize_dice_spec(spec)


def test_die__init__():
    d = dice.roll.Die(sides=6, value=1)
    assert d.value == 1


def test_die__repr__():
    d = dice.roll.Die(sides=6, value=1)
    assert repr(d) == "Die(sides=6, value=1, kept=True, exploded=False)"


def test_die__str__():
    d = dice.roll.Die(sides=6, value=1)
    assert str(d) == "1"

    d.set_drop()
    assert str(d) == "~~1~~"

    d.explode()
    assert str(d) == "__1__"


def test_die__hash__():
    d = dice.roll.Die(sides=6, value=1)
    assert hash(d) == hash("6_1")


def test_die__eq__():
    d = dice.roll.Die(sides=6, value=1)
    assert d == dice.roll.Die(sides=6, value=1)
    assert d == dice.roll.Die(sides=10, value=1)


def test_die__lt__():
    d = dice.roll.Die(sides=6, value=1)
    assert d < dice.roll.Die(sides=6, value=2)
    assert not d < dice.roll.Die(sides=6, value=1)


def test_die_roll():
    d = dice.roll.Die(sides=6, value=1)
    assert d.roll() in range(1, 7)


def test_die_set_drop():
    d = dice.roll.Die(sides=6, value=1)
    d.set_drop()
    assert not d.kept


def test_die_set_keep():
    d = dice.roll.Die(sides=6, value=1)
    d.set_keep()
    assert d.kept


def test_fatedie_roll():
    d = dice.roll.FateDie()
    d.roll()
    assert d.value in [-1, 0, 1]


def test_diceset__init__():
    dset = dice.roll.DiceSet()
    assert str(dset) == ""


def test_diceset_add_die():
    dset = dice.roll.DiceSet()
    dset.add_dice(4, 6)
    assert len(dset.all_die) == 4
    assert issubclass(type(dset.all_die[0]), dice.roll.Die)


def test_diceset_roll_no_mod():
    dset = dice.roll.DiceSet()
    dset.add_dice(4, 6)
    dset.roll()
    assert str(dset) != " 1 + 1 + 1 + 1 "


def test_keep_high_parse():
    keep = dice.roll.KeepOrDrop.parse('kh10')
    assert keep.keep
    assert keep.high
    assert keep.num == 10


def test_keep_low_parse():
    keep = dice.roll.KeepOrDrop.parse('kl10')
    assert keep.keep
    assert not keep.high
    assert keep.num == 10


def test_drop_high_parse():
    keep = dice.roll.KeepOrDrop.parse('dh10')
    assert not keep.keep
    assert keep.high
    assert keep.num == 10


def test_drop_low_parse():
    keep = dice.roll.KeepOrDrop.parse('dl10')
    assert not keep.keep
    assert not keep.high
    assert keep.num == 10


def test_keep_high():
    dset = dice.roll.DiceSet()
    dset.all_die = [
        dice.roll.Die(sides=6, value=5),
        dice.roll.Die(sides=6, value=2),
        dice.roll.Die(sides=6, value=6),
        dice.roll.Die(sides=6, value=1),
    ]
    dice.roll.KeepOrDrop(keep=True, high=True, num=2).modify_dice(dset)

    assert dset.all_die[0].kept
    assert not dset.all_die[1].kept
    assert dset.all_die[2].kept
    assert not dset.all_die[3].kept


def test_keep_low():
    dset = dice.roll.DiceSet()
    dset.all_die = [
        dice.roll.Die(sides=6, value=5),
        dice.roll.Die(sides=6, value=2),
        dice.roll.Die(sides=6, value=6),
        dice.roll.Die(sides=6, value=1),
    ]
    dice.roll.KeepOrDrop(keep=True, high=False, num=2).modify_dice(dset)

    assert not dset.all_die[0].kept
    assert dset.all_die[1].kept
    assert not dset.all_die[2].kept
    assert dset.all_die[3].kept


def test_drop_low():
    dset = dice.roll.DiceSet()
    dset.all_die = [
        dice.roll.Die(sides=6, value=5),
        dice.roll.Die(sides=6, value=2),
        dice.roll.Die(sides=6, value=6),
        dice.roll.Die(sides=6, value=1),
    ]
    dice.roll.KeepOrDrop(keep=False, high=False, num=2).modify_dice(dset)

    assert dset.all_die[0].kept
    assert not dset.all_die[1].kept
    assert dset.all_die[2].kept
    assert not dset.all_die[3].kept


def test_drop_high():
    dset = dice.roll.DiceSet()
    dset.all_die = [
        dice.roll.Die(sides=6, value=5),
        dice.roll.Die(sides=6, value=2),
        dice.roll.Die(sides=6, value=6),
        dice.roll.Die(sides=6, value=1),
    ]
    dice.roll.KeepOrDrop(keep=False, high=True, num=2).modify_dice(dset)

    assert not dset.all_die[0].kept
    assert dset.all_die[1].kept
    assert not dset.all_die[2].kept
    assert dset.all_die[3].kept


def test_exploding_dice():
    dset = dice.roll.DiceSet()
    dset.all_die = [
        dice.roll.Die(sides=6, value=5),
        dice.roll.Die(sides=6, value=2),
        dice.roll.Die(sides=6, value=6),
        dice.roll.Die(sides=6, value=1),
    ]
    dice.roll.ExplodingDice(lambda x: x.value == 6).modify_dice(dset)

    print(dset)


def test_compounding_dice():
    dset = dice.roll.DiceSet()
    dset.all_die = [
        dice.roll.Die(sides=6, value=5),
        dice.roll.Die(sides=6, value=2),
        dice.roll.Die(sides=6, value=6),
        dice.roll.Die(sides=6, value=1),
    ]
    dice.roll.CompoundingDice(lambda x: x.value == 6).modify_dice(dset)

    print(dset)
