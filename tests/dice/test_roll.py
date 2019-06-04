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


def test_determine_predicate_raises():
    with pytest.raises(ValueError):
        dice.roll.determine_predicate('4d6kh', 6)

    with pytest.raises(ValueError):
        dice.roll.determine_predicate('>1', 6)

    with pytest.raises(ValueError):
        dice.roll.determine_predicate('<6', 6)


def test_determine_predicate_equal():
    pred = dice.roll.determine_predicate('6', 6)
    assert pred(6)
    assert not pred(1)

    assert pred(dice.roll.Die(value=6))
    assert not pred(dice.roll.Die(value=1))


def test_determine_predicate_greater_than():
    pred = dice.roll.determine_predicate('>3', 6)
    assert pred(6)
    assert pred(3)
    assert not pred(2)

    assert pred(dice.roll.Die(value=6))
    assert pred(dice.roll.Die(value=3))
    assert not pred(dice.roll.Die(value=2))


def test_determine_predicate_less_than():
    pred = dice.roll.determine_predicate('<3', 6)
    assert not pred(6)
    assert pred(3)
    assert pred(2)

    assert not pred(dice.roll.Die(value=6))
    assert pred(dice.roll.Die(value=3))
    assert pred(dice.roll.Die(value=2))


def test_die__init__():
    d = dice.roll.Die(sides=6, value=1, flags=(dice.roll.Die.DROP | dice.roll.Die.EXPLODE))
    assert d.value == 1
    assert d.sides == 6
    assert d.is_exploded()
    assert d.is_dropped()


def test_die__repr__():
    d = dice.roll.Die(sides=6, value=1)
    assert repr(d) == "Die(sides=6, value=1, flags=1)"


def test_die__str__():
    d = dice.roll.Die(sides=6, value=1)
    assert str(d) == "1"

    d.set_drop()
    assert str(d) == "~~1~~"

    d.reset_flags()
    d.explode()
    assert str(d) == "__1__"

    d.reset_flags()
    d.set_success()
    assert str(d) == "**S**"


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


def test_die_value_get():
    d = dice.roll.Die(sides=6, value=1)
    assert d.value == 1

    d.value = 5
    assert d.value == 5

    d.set_fail()
    assert d.value == 'F'

    d.set_success()
    assert d.value == 'S'


def test_die_value_set():
    d = dice.roll.Die(sides=6, value=1)
    with pytest.raises(ValueError):
        d.value = -1

    with pytest.raises(ValueError):
        d.value = 0

    d.value = 100
    assert d.value == 100


def test_die_fmt_string():
    d = dice.roll.Die(sides=6, value=1)
    assert d.fmt_string() == '{}'

    d.set_drop()
    assert d.fmt_string() == '~~{}~~'

    d.reset_flags()
    d.explode()
    assert d.fmt_string() == '__{}__'

    d.reset_flags()
    d.set_success()
    assert d.fmt_string() == '**{}**'
    d.set_fail()
    assert d.fmt_string() == '**{}**'


def test_die_fmt_string_combinations():
    d = dice.roll.Die(sides=6, value=1)
    assert d.fmt_string() == '{}'

    d.set_drop()
    d.explode()
    d.set_success()
    assert "~~" in d.fmt_string()
    assert "__" in d.fmt_string()
    assert "**" in d.fmt_string()


def test_die_roll():
    d = dice.roll.Die(sides=6, value=1)
    assert d.roll() in range(1, 7)


def test_die_dupe():
    d = dice.roll.Die(sides=6, value=1)
    dupe = d.dupe()

    assert dupe is not d
    assert isinstance(dupe, dice.roll.Die)


def test_die_reset_flags():
    d = dice.roll.Die(sides=6, value=1)
    d.set_drop()
    d.set_fail()
    d.explode()

    d.reset_flags()
    assert d.is_kept()
    assert not d.is_fail()
    assert not d.is_success()
    assert not d.is_dropped()
    assert not d.is_exploded()


def test_die_is_kept():
    d = dice.roll.Die(sides=6, value=1)
    assert d.is_kept()


def test_die_is_dropped():
    d = dice.roll.Die(sides=6, value=1)
    d.set_drop()
    assert not d.is_kept()
    assert d.is_dropped()


def test_die_is_exploded():
    d = dice.roll.Die(sides=6, value=1)
    d.explode()
    assert d.is_kept()
    assert d.is_exploded()


def test_die_is_fail():
    d = dice.roll.Die(sides=6, value=1)
    d.set_fail()
    assert d.is_kept()
    assert not d.is_success()
    assert d.is_fail()


def test_die_is_success():
    d = dice.roll.Die(sides=6, value=1)
    d.set_success()
    assert d.is_kept()
    assert d.is_success()
    assert not d.is_fail()


def test_die_set_drop():
    d = dice.roll.Die(sides=6, value=1)
    d.reset_flags()
    d.set_drop()
    assert not d.is_kept()
    assert d.is_dropped()


def test_die_set_fail():
    d = dice.roll.Die(sides=6, value=1)

    assert not d.is_fail()
    assert not d.is_success()
    d.set_fail()
    assert d.is_fail()
    assert not d.is_success()


def test_die_set_success():
    d = dice.roll.Die(sides=6, value=1)

    assert not d.is_fail()
    assert not d.is_success()
    d.set_success()
    assert d.is_success()
    assert not d.is_fail()


def test_die_explode():
    d = dice.roll.Die(sides=6, value=1)

    assert not d.is_exploded()
    new_die = d.explode()
    assert d.is_exploded()
    assert issubclass(type(new_die), dice.roll.Die)


def test_die_flag_orthogonality():
    d = dice.roll.Die(sides=6, value=1)

    assert not d.is_exploded()
    d.explode()
    assert d.is_exploded()

    d.set_drop()
    assert d.is_exploded()
    assert d.is_dropped()

    d.set_fail()
    assert d.is_exploded()
    assert d.is_dropped()
    assert d.is_fail()

    d.set_success()
    assert d.is_exploded()
    assert d.is_dropped()
    assert d.is_success()


def test_fatedie__init__():
    die = dice.roll.FateDie(sides=10, value=10, flags=1)
    assert die.sides == 3
    assert die.value == 8
    assert die.flags == 1


def test_fatedie__repr__():
    die = dice.roll.FateDie(sides=10, value=10, flags=1)
    assert repr(die) == "FateDie(sides=3, value=8, flags=1)"


def test_fatedie__str__():
    d = dice.roll.FateDie()
    d.value = -1
    assert str(d) == '-'

    d.value = 0
    assert str(d) == '0'

    d.value = 1
    assert str(d) == '+'


def test_fatedie_roll():
    d = dice.roll.FateDie()
    d.roll()
    assert d.value in [-1, 0, 1]


def test_fatedie_dupe():
    die = dice.roll.FateDie(sides=10, value=10, flags=1)
    dupe = die.dupe()

    assert dupe is not die
    assert isinstance(dupe, dice.roll.FateDie)


def test_fatedie_value_get():
    d = dice.roll.FateDie()
    d.value = -1
    assert d.value == -1

    d.value = 0
    assert d.value == 0

    d.value = 1
    assert d.value == 1


def test_fatedie_value_set():
    d = dice.roll.FateDie()
    with pytest.raises(ValueError):
        d.value = -2

    with pytest.raises(ValueError):
        d.value = 2

    d.value = -1
    assert d.value == -1

    d.value = 1
    assert d.value == 1


def test_diceset__init__():
    dset = dice.roll.DiceSet()
    assert str(dset) == ""


def test_diceset__repr__():
    dset = dice.roll.DiceSet()
    dset.add_dice(4, 6)

    expect = "DiceSet(all_die=[Die(sides=6, value=1, flags=1), Die(sides=6, value=1, flags=1), Die(sides=6, value=1, flags=1), Die(sides=6, value=1, flags=1)], mods=[])"
    assert repr(dset) == expect


def test_diceset__str__():
    dset = dice.roll.DiceSet()
    dset.add_dice(4, 6)

    assert str(dset) == "1 + 1 + 1 + 1"


def test_diceset_add_die():
    dset = dice.roll.DiceSet()
    dset.add_dice(4, 6)
    assert len(dset.all_die) == 4
    assert issubclass(type(dset.all_die[0]), dice.roll.Die)


def test_diceset_add_fatedie():
    dset = dice.roll.DiceSet()
    dset.add_fatedice(4)
    assert len(dset.all_die) == 4
    assert issubclass(type(dset.all_die[0]), dice.roll.FateDie)


def test_diceset_roll_no_mod():
    dset = dice.roll.DiceSet()
    dset.add_dice(4, 6)

    assert str(dset) == "1 + 1 + 1 + 1"
    dset.roll()
    assert str(dset) != "1 + 1 + 1 + 1"


def test_diceset_apply_mods():
    dset = dice.roll.DiceSet()
    dset.add_dice(4, 6)
    dset.add_mod(dice.roll.KeepOrDrop())

    assert str(dset) == "1 + 1 + 1 + 1"
    dset.roll()
    assert str(dset) != "1 + 1 + 1 + 1"

    dset.apply_mods()
    assert str(dset).count("~~") == 6


def test_keep_high_parse():
    keep = dice.roll.KeepOrDrop.parse('kh10', 6)
    assert keep.keep
    assert keep.high
    assert keep.num == 10


def test_keep_low_parse():
    keep = dice.roll.KeepOrDrop.parse('kl10', 6)
    assert keep.keep
    assert not keep.high
    assert keep.num == 10


def test_drop_high_parse():
    keep = dice.roll.KeepOrDrop.parse('dh10', 6)
    assert not keep.keep
    assert keep.high
    assert keep.num == 10


def test_drop_low_parse():
    keep = dice.roll.KeepOrDrop.parse('dl10', 6)
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

    assert dset.all_die[0].is_kept()
    assert not dset.all_die[1].is_kept()
    assert dset.all_die[2].is_kept()
    assert not dset.all_die[3].is_kept()


def test_keep_low():
    dset = dice.roll.DiceSet()
    dset.all_die = [
        dice.roll.Die(sides=6, value=5),
        dice.roll.Die(sides=6, value=2),
        dice.roll.Die(sides=6, value=6),
        dice.roll.Die(sides=6, value=1),
    ]
    dice.roll.KeepOrDrop(keep=True, high=False, num=2).modify_dice(dset)

    assert not dset.all_die[0].is_kept()
    assert dset.all_die[1].is_kept()
    assert not dset.all_die[2].is_kept()
    assert dset.all_die[3].is_kept()


def test_drop_low():
    dset = dice.roll.DiceSet()
    dset.all_die = [
        dice.roll.Die(sides=6, value=5),
        dice.roll.Die(sides=6, value=2),
        dice.roll.Die(sides=6, value=6),
        dice.roll.Die(sides=6, value=1),
    ]
    dice.roll.KeepOrDrop(keep=False, high=False, num=2).modify_dice(dset)

    assert dset.all_die[0].is_kept()
    assert not dset.all_die[1].is_kept()
    assert dset.all_die[2].is_kept()
    assert not dset.all_die[3].is_kept()


def test_drop_high():
    dset = dice.roll.DiceSet()
    dset.all_die = [
        dice.roll.Die(sides=6, value=5),
        dice.roll.Die(sides=6, value=2),
        dice.roll.Die(sides=6, value=6),
        dice.roll.Die(sides=6, value=1),
    ]
    dice.roll.KeepOrDrop(keep=False, high=True, num=2).modify_dice(dset)

    assert not dset.all_die[0].is_kept()
    assert dset.all_die[1].is_kept()
    assert not dset.all_die[2].is_kept()
    assert dset.all_die[3].is_kept()


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


def test_exploding_dice_parse():
    assert dice.roll.ExplodingDice.parse('!>4', 6)
    assert dice.roll.ExplodingDice.parse('!<4', 6)
    assert dice.roll.ExplodingDice.parse('!4', 6)


def test_exploding_dice_parse_impossible():
    with pytest.raises(ValueError):
        assert dice.roll.ExplodingDice.parse('4d6', 6)

    with pytest.raises(ValueError):
        assert dice.roll.ExplodingDice.parse('!!>1', 6)

    with pytest.raises(ValueError):
        assert dice.roll.ExplodingDice.parse('!>1', 6)

    with pytest.raises(ValueError):
        assert dice.roll.ExplodingDice.parse('!<6', 6)


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


def test_compounding_dice_parse():
    assert dice.roll.CompoundingDice.parse('!!>4', 6)
    assert dice.roll.CompoundingDice.parse('!!<4', 6)
    assert dice.roll.CompoundingDice.parse('!!4', 6)


def test_compounding_dice_parse_impossible():
    with pytest.raises(ValueError):
        assert dice.roll.ExplodingDice.parse('4d6', 6)

    with pytest.raises(ValueError):
        assert dice.roll.ExplodingDice.parse('!>1', 6)

    with pytest.raises(ValueError):
        assert dice.roll.ExplodingDice.parse('!!>1', 6)

    with pytest.raises(ValueError):
        assert dice.roll.ExplodingDice.parse('!!<6', 6)


def test_reroll_dice():
    dset = dice.roll.DiceSet()
    dset.all_die = [
        dice.roll.Die(sides=6, value=5),
        dice.roll.Die(sides=6, value=2),
        dice.roll.Die(sides=6, value=6),
        dice.roll.Die(sides=6, value=1),
    ]
    dice.roll.RerollDice([1, 2]).modify_dice(dset)

    print(dset)


def test_reroll_dice_parse():
    dset = dice.roll.DiceSet()
    dset.all_die = [
        dice.roll.Die(sides=6, value=5),
        dice.roll.Die(sides=6, value=2),
        dice.roll.Die(sides=6, value=6),
        dice.roll.Die(sides=6, value=1),
    ]
    rdice = dice.roll.RerollDice.parse('r>5r2', 6)
    assert rdice.invalid_rolls == [2, 5, 6]


def test_reroll_dice_parse_impossible():
    with pytest.raises(ValueError):
        dice.roll.RerollDice.parse('r>1', 6)

    with pytest.raises(ValueError):
        dice.roll.RerollDice.parse('r<6', 6)

    with pytest.raises(ValueError):
        dice.roll.RerollDice.parse('r<5r6', 6)

    with pytest.raises(ValueError):
        dice.roll.RerollDice.parse('r1r2r3r4r5r6', 6)


def test_success_fail_parse():
    dset = dice.roll.DiceSet()
    dset.all_die = [
        dice.roll.Die(sides=6, value=5),
        dice.roll.Die(sides=6, value=2),
        dice.roll.Die(sides=6, value=6),
        dice.roll.Die(sides=6, value=1),
    ]
    mod = dice.roll.SuccessFail.parse('>4', 6)
    mod.modify_dice(dset)

    assert dset.all_die[0].is_success()
    assert dset.all_die[1].is_fail()
    assert dset.all_die[2].is_success()
    assert dset.all_die[3].is_fail()


def test_success_fail_modify_dice():
    dset = dice.roll.DiceSet()
    dset.all_die = [
        dice.roll.Die(sides=6, value=5),
        dice.roll.Die(sides=6, value=2),
        dice.roll.Die(sides=6, value=6),
        dice.roll.Die(sides=6, value=1),
    ]
    mod = dice.roll.SuccessFail(lambda x: x.value >= 4)
    mod.modify_dice(dset)

    assert dset.all_die[0].is_success()
    assert dset.all_die[1].is_fail()
    assert dset.all_die[2].is_success()
    assert dset.all_die[3].is_fail()
