"""
Tests for dice rolling in dice.roll
"""
from __future__ import absolute_import, print_function
import re

import pytest

import dice.exc
import dice.roll


@pytest.fixture
def f_dset():
    dset = dice.roll.DiceSet()
    dset.all_die = [
        dice.roll.Die(sides=6, value=5),
        dice.roll.Die(sides=6, value=2),
        dice.roll.Die(sides=6, value=6),
        dice.roll.Die(sides=6, value=1),
    ]

    yield dset


@pytest.fixture
def f_athrow(f_dset):
    throw = dice.roll.AThrow(spec='4d6 + 4', parts=[f_dset, '+', '4'])

    yield throw


def test_check_parentheses():
    assert dice.roll.check_parentheses('()')
    assert dice.roll.check_parentheses('{}')
    assert dice.roll.check_parentheses('[]')

    with pytest.raises(ValueError):
        dice.roll.check_parentheses('{]')


def test_comp__repr__():
    comp = dice.roll.Comp(left=3, right=5, func='range')
    assert repr(comp) == "Comp(left=3, right=5, func='range')"


def test_parse_predicate_raises():
    with pytest.raises(ValueError):
        dice.roll.parse_predicate('>1', 6)

    with pytest.raises(ValueError):
        dice.roll.parse_predicate('<6', 6)

    with pytest.raises(ValueError):
        dice.roll.parse_predicate('[1,6]', 6)

    with pytest.raises(ValueError):
        dice.roll.parse_predicate('[5,1]', 6)

    with pytest.raises(ValueError):
        dice.roll.parse_predicate('r>2', 6)


def test_parse_predicate_equal():
    rest, pred = dice.roll.parse_predicate('6r>2', 6)
    assert rest == 'r>2'
    assert pred(6)
    assert not pred(1)

    assert pred(dice.roll.Die(value=6))
    assert not pred(dice.roll.Die(value=1))

    rest, pred = dice.roll.parse_predicate('=6r>1', 6)
    assert rest == 'r>1'
    assert pred(6)
    assert not pred(1)


def test_parse_predicate_greater_than():
    rest, pred = dice.roll.parse_predicate('>3f<2', 6)
    assert rest == 'f<2'
    assert pred(6)
    assert pred(3)
    assert not pred(2)

    assert pred(dice.roll.Die(value=6))
    assert pred(dice.roll.Die(value=3))
    assert not pred(dice.roll.Die(value=2))


def test_parse_predicate_less_than():
    rest, pred = dice.roll.parse_predicate('<3>2', 6)
    assert rest == '>2'
    assert not pred(6)
    assert pred(3)
    assert pred(2)

    assert not pred(dice.roll.Die(value=6))
    assert pred(dice.roll.Die(value=3))
    assert pred(dice.roll.Die(value=2))


def test_parse_predicate_range():
    rest, pred = dice.roll.parse_predicate('[2,4]f<3', 6)
    assert rest == 'f<3'
    assert not pred(6)
    assert pred(4)
    assert pred(3)
    assert pred(2)

    assert not pred(dice.roll.Die(value=6))
    assert pred(dice.roll.Die(value=4))
    assert pred(dice.roll.Die(value=3))
    assert pred(dice.roll.Die(value=2))


def test_parse_diceset():
    nspec, dset = dice.roll.parse_diceset('4d20kh1')
    assert nspec == 'kh1'
    assert len(dset.all_die) == 4

    nspec, dset = dice.roll.parse_diceset('20d100!!<6 + 4d10 - 2')
    assert nspec == '!!<6 + 4d10 - 2'
    assert len(dset.all_die) == 20


def test_parse_diceset_raises():
    with pytest.raises(ValueError):
        dice.roll.parse_diceset(' 4d20')

    with pytest.raises(ValueError):
        dice.roll.parse_diceset('4df')

    with pytest.raises(ValueError):
        dice.roll.parse_diceset('>34d8')

    with pytest.raises(dice.exc.InvalidCommandArgs):
        dice.roll.parse_diceset('4000000000d20')

    with pytest.raises(dice.exc.InvalidCommandArgs):
        dice.roll.parse_diceset('4d2000000000000')


def test_parse_fate_diceset():
    nspec, dset = dice.roll.parse_fate_diceset('4df')
    assert nspec == ''
    assert len(dset.all_die) == 4

    nspec, dset = dice.roll.parse_fate_diceset('10dfkh1')
    assert nspec == 'kh1'
    assert len(dset.all_die) == 10


def test_parse_fate_diceset_raises():
    with pytest.raises(ValueError):
        dice.roll.parse_fate_diceset(' 4df')

    with pytest.raises(ValueError):
        dice.roll.parse_fate_diceset('4d6')

    with pytest.raises(ValueError):
        dice.roll.parse_fate_diceset('>34d8')

    with pytest.raises(dice.exc.InvalidCommandArgs):
        dice.roll.parse_fate_diceset('4000000000df')


def test_parse_literal():
    line, lit = dice.roll.parse_literal("+ 42")
    assert line == "42"
    assert lit == "+"

    line, lit = dice.roll.parse_literal("- 42")
    assert line == "42"
    assert lit == "-"

    line, lit = dice.roll.parse_literal("42 + 1")
    assert line == "+ 1"
    assert lit == "42"

    line, lit = dice.roll.parse_literal("42 + 4d6")
    assert line == "+ 4d6"
    assert lit == "42"


def test_parse_trailing_mods():
    line, all_mods = dice.roll.parse_trailing_mods('k1 + 4', 6)
    assert line == ' + 4'

    line, all_mods = dice.roll.parse_trailing_mods('d1 + 4', 6)
    assert line == ' + 4'

    line, all_mods = dice.roll.parse_trailing_mods('kh3dl2 + 4d20 + 20', 6)
    assert line == ' + 4d20 + 20'

    line, all_mods = dice.roll.parse_trailing_mods('kl2dh1', 6)
    assert line == ''

    line, all_mods = dice.roll.parse_trailing_mods('kl2kl1', 6)
    assert line == ''

    line, all_mods = dice.roll.parse_trailing_mods('kl2!>5r4r>4', 6)
    print(all_mods)
    assert line == ''

    line, all_mods = dice.roll.parse_trailing_mods('kl2!>5r4r>4f<2', 6)
    print(all_mods)
    assert line == ''

    line, all_mods = dice.roll.parse_trailing_mods('kl2!>5r4r>4f<2>5', 6)
    print(all_mods)
    assert line == ''

    line, all_mods = dice.roll.parse_trailing_mods('kl2!>5r4r>4f<2>5s', 6)
    print(all_mods)
    assert line == ''


def test_parse_trailing_mods_raises():
    with pytest.raises(ValueError):
        dice.roll.parse_trailing_mods('r4r>5f2r6', 6)

    with pytest.raises(ValueError):
        dice.roll.parse_trailing_mods('khr<dl', 6)


def test_parse_dice_line_fails():
    with pytest.raises(ValueError):
        dice.roll.parse_dice_line('8d10k')

    with pytest.raises(ValueError):
        dice.roll.parse_dice_line('8d10r<aaa')

    with pytest.raises(ValueError):
        dice.roll.parse_dice_line('8d10f[a,3]')

    with pytest.raises(ValueError):
        dice.roll.parse_dice_line('8d10f[1,3] + aaaa')


def test_parse_dice_line_comment():
    throw = dice.roll.parse_dice_line("4 + 4 # a comment here")
    assert throw.next() == "4 + 4 = 4 + 4 = 8\n        Note: a comment here"


def test_parse_dice_line():
    throw = dice.roll.parse_dice_line('4d20kh2r<4 + 6')
    print(throw.next())

    throw = dice.roll.parse_dice_line('4d20f[4,8] + 6')
    print(throw.next())

    throw = dice.roll.parse_dice_line('4d100>30')
    print(throw.next())

    throw = dice.roll.parse_dice_line('4d100f<30>40')
    print(throw.next())

    throw = dice.roll.parse_dice_line('8d10!!>8')
    print(throw.next())

    throw = dice.roll.parse_dice_line('8d10!>8')
    print(throw.next())


def test_die__init__():
    die = dice.roll.Die(sides=6, value=1, flags=(dice.roll.Die.DROP | dice.roll.Die.EXPLODE))
    assert die.value == 1
    assert die.sides == 6
    assert die.is_exploded()
    assert die.is_dropped()


def test_die__repr__():
    die = dice.roll.Die(sides=6, value=1)
    assert repr(die) == "Die(sides=6, value=1, flags=1)"


def test_die__str__():
    die = dice.roll.Die(sides=6, value=1)
    assert str(die) == "1"

    die.set_drop()
    assert str(die) == "~~1~~"

    die.reset_flags()
    die.explode()
    assert str(die) == "__1__"

    die.reset_flags()
    die.set_fail()
    assert str(die) == "1"

    die.set_success()
    assert str(die) == "**1**"


def test_die__hash__():
    die = dice.roll.Die(sides=6, value=1)
    assert hash(die) == hash("6_1")


def test_die__eq__():
    die = dice.roll.Die(sides=6, value=1)
    assert die == dice.roll.Die(sides=6, value=1)
    assert die == dice.roll.Die(sides=10, value=1)


def test_die__lt__():
    die = dice.roll.Die(sides=6, value=1)
    assert die < dice.roll.Die(sides=6, value=2)
    assert die >= dice.roll.Die(sides=6, value=1)


def test_die__add__():
    die = dice.roll.Die(sides=6, value=1)
    assert die + 4 == 5
    assert die + dice.roll.Die(sides=4, value=1) == 2


def test_die__sub__():
    die = dice.roll.Die(sides=6, value=5)
    assert die - 4 == 1
    assert die - dice.roll.Die(sides=4, value=4) == 1


def test_die__mul__():
    die = dice.roll.Die(sides=6, value=2)
    assert die * 4 == 8
    assert die * dice.roll.Die(sides=4, value=4) == 8


def test_die__floordiv__():
    die = dice.roll.Die(sides=6, value=8)
    assert die // 4 == 2
    assert die // dice.roll.Die(sides=4, value=4) == 2


def test_die__radd__():
    die = dice.roll.Die(sides=6, value=1)
    assert 4 + die == 5
    assert dice.roll.Die(sides=4, value=1) + die == 2


def test_die__rsub__():
    die = dice.roll.Die(sides=6, value=5)
    assert 4 - die == -1
    assert dice.roll.Die(sides=4, value=4) - die == -1


def test_die__rmul__():
    die = dice.roll.Die(sides=6, value=2)
    assert 4 * die == 8
    assert dice.roll.Die(sides=4, value=4) * die == 8


def test_die__rfloordiv__():
    die = dice.roll.Die(sides=6, value=4)
    assert 8 // die == 2
    assert dice.roll.Die(sides=4, value=8) // die == 2


def test_die__iadd__():
    die = dice.roll.Die(sides=6, value=1)
    die += 4
    assert die.value == 5


def test_die__isub__():
    die = dice.roll.Die(sides=6, value=5)
    die -= 4
    assert die.value == 1


def test_die__imul__():
    die = dice.roll.Die(sides=6, value=2)
    die *= 4
    assert die.value == 8


def test_die__ifloordiv__():
    die = dice.roll.Die(sides=6, value=8)
    die //= 4
    assert die.value == 2


def test_die_value_get():
    die = dice.roll.Die(sides=6, value=1)
    assert die.value == 1

    die.value = 5
    assert die.value == 5

    die.set_fail()
    assert die.value == 5

    die.set_success()
    assert die.value == 5


def test_die_value_set():
    die = dice.roll.Die(sides=6, value=1)
    with pytest.raises(ValueError):
        die.value = -1

    with pytest.raises(ValueError):
        die.value = 0

    die.value = 100
    assert die.value == 100


def test_die_fmt_string():
    die = dice.roll.Die(sides=6, value=1)
    assert die.fmt_string() == '{}'

    die.set_drop()
    assert die.fmt_string() == '~~{}~~'

    die.reset_flags()
    die.set_reroll()
    assert die.fmt_string() == '{}r'

    die.reset_flags()
    die.explode()
    assert die.fmt_string() == '__{}__'

    die.reset_flags()
    die.set_success()
    assert die.fmt_string() == '**{}**'

    die.set_fail()
    assert die.fmt_string() == '{}'


def test_die_fmt_string_combinations():
    die = dice.roll.Die(sides=6, value=1)
    assert die.fmt_string() == '{}'

    die.set_drop()
    die.explode()
    die.set_success()
    assert "~~" in die.fmt_string()
    assert "__" in die.fmt_string()
    assert "**" in die.fmt_string()


def test_die_roll():
    die = dice.roll.Die(sides=6, value=1)
    assert die.roll() in range(1, 7)


def test_die_dupe():
    die = dice.roll.Die(sides=6, value=1)
    dupe = die.dupe()

    assert dupe is not die
    assert isinstance(dupe, dice.roll.Die)


def test_die_reset_flags():
    die = dice.roll.Die(sides=6, value=1)
    die.set_drop()
    die.set_fail()
    die.explode()

    die.reset_flags()
    assert die.is_kept()
    assert not die.is_fail()
    assert not die.is_success()
    assert not die.is_dropped()
    assert not die.is_exploded()


def test_die_is_kept():
    die = dice.roll.Die(sides=6, value=1)
    assert die.is_kept()


def test_die_is_dropped():
    die = dice.roll.Die(sides=6, value=1)
    die.set_drop()
    assert not die.is_kept()
    assert die.is_dropped()


def test_die_is_exploded():
    die = dice.roll.Die(sides=6, value=1)
    die.explode()
    assert die.is_kept()
    assert die.is_exploded()


def test_die_is_penetrated():
    die = dice.roll.Die(sides=6, value=1)
    die.explode()
    die.set_penetrate()
    assert die.is_kept()
    assert die.is_exploded()
    assert die.is_penetrated()


def test_die_is_fail():
    die = dice.roll.Die(sides=6, value=1)
    die.set_fail()
    assert die.is_kept()
    assert not die.is_success()
    assert die.is_fail()


def test_die_is_success():
    die = dice.roll.Die(sides=6, value=1)
    die.set_success()
    assert die.is_kept()
    assert die.is_success()
    assert not die.is_fail()


def test_die_set_drop():
    die = dice.roll.Die(sides=6, value=1)
    die.reset_flags()
    die.set_drop()
    assert not die.is_kept()
    assert die.is_dropped()


def test_die_set_fail():
    die = dice.roll.Die(sides=6, value=1)

    assert not die.is_fail()
    assert not die.is_success()
    die.set_fail()
    assert die.is_fail()
    assert not die.is_success()


def test_die_set_success():
    die = dice.roll.Die(sides=6, value=1)

    assert not die.is_fail()
    assert not die.is_success()
    die.set_success()
    assert die.is_success()
    assert not die.is_fail()


def test_die_explode():
    die = dice.roll.Die(sides=6, value=1)

    assert not die.is_exploded()
    new_die = die.explode()
    assert die.is_exploded()
    assert issubclass(type(new_die), dice.roll.Die)


def test_die_set_penetrate():
    die = dice.roll.Die(sides=6, value=1)
    die.set_penetrate()
    assert die.is_kept()
    assert not die.is_exploded()
    assert die.is_penetrated()


def test_die_flag_orthogonality():
    die = dice.roll.Die(sides=6, value=1)

    assert not die.is_exploded()
    die.explode()
    assert die.is_exploded()

    die.set_drop()
    assert die.is_exploded()
    assert die.is_dropped()

    die.set_fail()
    assert die.is_exploded()
    assert die.is_dropped()
    assert die.is_fail()

    die.set_success()
    assert die.is_exploded()
    assert die.is_dropped()
    assert die.is_success()


def test_fatedie__init__():
    die = dice.roll.FateDie(sides=10, value=10, flags=1)
    assert die.sides == 3
    assert die.value == 8
    assert die.flags == 1


def test_fatedie__repr__():
    die = dice.roll.FateDie(sides=10, value=10, flags=1)
    assert repr(die) == "FateDie(sides=3, value=8, flags=1)"


def test_fatedie__str__():
    die = dice.roll.FateDie()
    die.value = -1
    assert str(die) == '-'

    die.value = 0
    assert str(die) == '0'

    die.value = 1
    assert str(die) == '+'


def test_fatedie_roll():
    die = dice.roll.FateDie()
    die.roll()
    assert die.value in [-1, 0, 1]


def test_fatedie_dupe():
    die = dice.roll.FateDie(sides=10, value=10, flags=1)
    dupe = die.dupe()

    assert dupe is not die
    assert isinstance(dupe, dice.roll.FateDie)


def test_fatedie_value_get():
    die = dice.roll.FateDie()
    die.value = -1
    assert die.value == -1

    die.value = 0
    assert die.value == 0

    die.value = 1
    assert die.value == 1


def test_fatedie_value_set():
    die = dice.roll.FateDie()
    with pytest.raises(ValueError):
        die.value = -2

    with pytest.raises(ValueError):
        die.value = 2

    die.value = -1
    assert die.value == -1

    die.value = 1
    assert die.value == 1


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

    assert str(dset) == "(1 + 1 + 1 + 1)"


def test_diceset__str__truncate():
    dset = dice.roll.DiceSet()
    dset.add_dice(200, 100)

    assert str(dset) == "(1 + 1 + ... 1)"


def test_diceset_value(f_dset):
    assert f_dset.value == 14


def test_diceset_max_roll(f_dset):
    assert f_dset.max_roll == 6


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
    assert str(dset) == "(1 + 1 + 1 + 1)"
    dset.roll()
    assert str(dset) != "(1 + 1 + 1 + 1)"


def test_athrow__repr__(f_athrow):
    expect = "AThrow(spec='4d6 + 4', parts=[DiceSet(all_die=[Die(sides=6, value=5, flags=1), Die(sides=6, value=2, flags=1), Die(sides=6, value=6, flags=1), Die(sides=6, value=1, flags=1)], mods=[]), '+', '4'])"
    assert repr(f_athrow) == expect


def test_athrow__str__(f_athrow):
    assert str(f_athrow) == "(5 + 2 + 6 + 1) + 4"


def test_athrow_add(f_athrow):
    f_athrow.add('+')
    assert str(f_athrow) == "(5 + 2 + 6 + 1) + 4 +"


def test_athrow_roll(f_athrow):
    f_athrow.roll()
    assert str(f_athrow) != "(5 + 2 + 6 + 1) + 4"


def test_athrow_numeric_value(f_athrow):
    assert f_athrow.numeric_value() == 18


def test_athrow_string_success(f_athrow):
    f_dset = f_athrow.parts[0]
    pred = dice.roll.Comp(left=5, func='greater_equal')
    f_dset.mods = [dice.roll.SuccessFail(mark_success=True, pred=pred)]
    f_athrow.parts[0].apply_mods()
    assert f_athrow.success_string() == "(+2) **0** Failure(s), **2** Success(es)"


def test_athrow_string_fail(f_athrow):
    f_dset = f_athrow.parts[0]
    pred = dice.roll.Comp(left=2, func='less_equal')
    f_dset.mods = [dice.roll.SuccessFail(mark_success=False, pred=pred)]
    f_athrow.parts[0].apply_mods()
    assert f_athrow.success_string() == "(-2) **2** Failure(s), **0** Success(es)"


def test_athrow_string_success_and_fail(f_athrow):
    f_dset = f_athrow.parts[0]
    pred = dice.roll.Comp(left=5, func='greater_equal')
    pred2 = dice.roll.Comp(left=2, func='less_equal')
    f_dset.mods = [dice.roll.SuccessFail(mark_success=True, pred=pred),
                   dice.roll.SuccessFail(mark_success=False, pred=pred2)]

    f_athrow.parts[0].apply_mods()
    assert f_athrow.success_string() == "(+0) **2** Failure(s), **2** Success(es)"


def test_athrow_next(f_athrow):
    assert re.match(r'4d6 \+ 4 = [ 0-9\+=()]+', f_athrow.next())


def test_keep_high__repr__():
    keep = dice.roll.KeepDrop(num=10)
    assert repr(keep) == "KeepDrop(keep=True, high=True, num=10)"


def test_keep_high_parse():
    line, keep = dice.roll.KeepDrop.parse('kh10dl1', 6)
    assert keep.keep
    assert keep.high
    assert keep.num == 10
    assert line == 'dl1'


def test_keep_high_parse_default():
    line, keep = dice.roll.KeepDrop.parse('k10dl1', 6)
    assert keep.keep
    assert keep.high
    assert keep.num == 10
    assert line == 'dl1'


def test_keep_low_parse():
    line, keep = dice.roll.KeepDrop.parse('kl10dl1', 6)
    assert keep.keep
    assert not keep.high
    assert keep.num == 10
    assert line == 'dl1'


def test_drop_high_parse():
    line, keep = dice.roll.KeepDrop.parse('dh10kh1', 6)
    assert not keep.keep
    assert keep.high
    assert keep.num == 10
    assert line == 'kh1'


def test_drop_low_parse():
    line, keep = dice.roll.KeepDrop.parse('dl10', 6)
    assert not keep.keep
    assert not keep.high
    assert keep.num == 10
    assert line == ''


def test_drop_low_parse_default():
    line, keep = dice.roll.KeepDrop.parse('d10kh1', 6)
    assert not keep.keep
    assert not keep.high
    assert keep.num == 10
    assert line == 'kh1'


def test_keep_high_modify(f_dset):
    dice.roll.KeepDrop(keep=True, high=True, num=2).modify(f_dset)

    assert f_dset.all_die[0].is_kept()
    assert not f_dset.all_die[1].is_kept()
    assert f_dset.all_die[2].is_kept()
    assert not f_dset.all_die[3].is_kept()


def test_keep_low_modify(f_dset):
    dice.roll.KeepDrop(keep=True, high=False, num=2).modify(f_dset)

    assert not f_dset.all_die[0].is_kept()
    assert f_dset.all_die[1].is_kept()
    assert not f_dset.all_die[2].is_kept()
    assert f_dset.all_die[3].is_kept()


def test_drop_low_modify(f_dset):
    dice.roll.KeepDrop(keep=False, high=False, num=2).modify(f_dset)

    assert not f_dset.all_die[0].is_dropped()
    assert f_dset.all_die[1].is_dropped()
    assert not f_dset.all_die[2].is_dropped()
    assert f_dset.all_die[3].is_dropped()


def test_drop_high_modify(f_dset):
    dice.roll.KeepDrop(keep=False, high=True, num=2).modify(f_dset)

    assert f_dset.all_die[0].is_dropped()
    assert not f_dset.all_die[1].is_dropped()
    assert f_dset.all_die[2].is_dropped()
    assert not f_dset.all_die[3].is_dropped()


def test_explode_dice_parse():
    assert dice.roll.ExplodeDice.parse('!>4', 6)
    assert dice.roll.ExplodeDice.parse('!<4', 6)
    assert dice.roll.ExplodeDice.parse('!4', 6)
    assert dice.roll.ExplodeDice.parse('![4,6]', 6)


def test_explode_dice_parse_raises():
    with pytest.raises(ValueError):
        assert dice.roll.ExplodeDice.parse('4d6', 6)

    with pytest.raises(ValueError):
        assert dice.roll.ExplodeDice.parse('!!>1', 6)

    with pytest.raises(ValueError):
        assert dice.roll.ExplodeDice.parse('!>1', 6)

    with pytest.raises(ValueError):
        assert dice.roll.ExplodeDice.parse('!<6', 6)


def test_explode_dice_modify(f_dset):
    mod = dice.roll.ExplodeDice(pred=dice.roll.Comp(left=6, func='equal'))
    mod.modify(f_dset)
    assert [x for x in f_dset.all_die if x.is_exploded()]
    assert len(f_dset.all_die) >= 5


def test_penetrate_dice_parse():
    assert dice.roll.ExplodeDice.parse('!p>4', 6)[1].penetrate


def test_penetrate_dice_parse_raises():
    with pytest.raises(ValueError):
        dice.roll.ExplodeDice.parse('!p', 6)

    with pytest.raises(ValueError):
        dice.roll.ExplodeDice.parse('!p>', 6)


def test_penetrate_dice_modify(f_dset):
    mod = dice.roll.ExplodeDice(pred=dice.roll.Comp(left=6, func='equal'), penetrate=True)
    mod.modify(f_dset)
    assert [x for x in f_dset.all_die if x.is_penetrated()]
    assert len(f_dset.all_die) >= 5


def test_compound_dice_parse():
    assert dice.roll.CompoundDice.parse('!!>4', 6)
    assert dice.roll.CompoundDice.parse('!!<4', 6)
    assert dice.roll.CompoundDice.parse('!!4', 6)
    assert dice.roll.CompoundDice.parse('!![4,6]', 6)


def test_compound_dice_parse_raises():
    with pytest.raises(ValueError):
        assert dice.roll.ExplodeDice.parse('r', 6)

    with pytest.raises(ValueError):
        assert dice.roll.ExplodeDice.parse('4d6', 6)

    with pytest.raises(ValueError):
        assert dice.roll.ExplodeDice.parse('!>1', 6)

    with pytest.raises(ValueError):
        assert dice.roll.ExplodeDice.parse('!!>1', 6)

    with pytest.raises(ValueError):
        assert dice.roll.ExplodeDice.parse('!!<6', 6)


def test_compound_dice_modify(f_dset):
    mod = dice.roll.CompoundDice(pred=lambda x: x.value == 6)
    mod.modify(f_dset)
    assert [x for x in f_dset.all_die if x.is_exploded()]
    assert len(f_dset.all_die) >= 4


def test_reroll_dice_parse():
    line, mod = dice.roll.RerollDice.parse('r>5r2>2', 6)
    assert mod.invalid_rolls == [2, 5, 6]
    assert line == '>2'

    line, mod = dice.roll.RerollDice.parse('r>5r2f<5', 6)
    assert mod.invalid_rolls == [2, 5, 6]
    assert line == 'f<5'


def test_reroll_dice_parse_raises():
    with pytest.raises(ValueError):
        dice.roll.RerollDice.parse('s', 6)

    with pytest.raises(ValueError):
        dice.roll.RerollDice.parse('r>1', 6)

    with pytest.raises(ValueError):
        dice.roll.RerollDice.parse('r<6', 6)

    with pytest.raises(ValueError):
        dice.roll.RerollDice.parse('r<5r6', 6)

    with pytest.raises(ValueError):
        dice.roll.RerollDice.parse('r1r2r3r4r5r6', 6)


def test_reroll_dice_modify(f_dset):
    mod = dice.roll.RerollDice(invalid_rolls=[1, 2, 3])
    mod.modify(f_dset)
    assert len(f_dset.all_die) >= 6


def test_success_fail_parse():
    line, mod = dice.roll.SuccessFail.parse('>4f<2', 6)
    assert mod.mark == 'set_success'
    assert line == 'f<2'

    line, mod = dice.roll.SuccessFail.parse('f>4<2', 6)
    assert mod.mark == 'set_fail'
    assert line == '<2'


def test_success_fail_parse_raises():
    with pytest.raises(ValueError):
        dice.roll.SuccessFail.parse('r', 6)

    with pytest.raises(ValueError):
        dice.roll.SuccessFail.parse('kh2', 6)

    with pytest.raises(ValueError):
        dice.roll.SuccessFail.parse('>f', 6)


def test_success_fail_modify(f_dset):
    mod = dice.roll.SuccessFail(pred=lambda x: x.value >= 4)
    mod.modify(f_dset)

    assert f_dset.all_die[0].is_success()
    assert not f_dset.all_die[1].is_success()
    assert f_dset.all_die[2].is_success()
    assert not f_dset.all_die[3].is_success()


def test_sort_dice_parse():
    line, mod = dice.roll.SortDice.parse('s', 6)
    assert mod.ascending
    assert line == ''

    line, mod = dice.roll.SortDice.parse('sa + 42', 6)
    assert mod.ascending
    assert line == ' + 42'

    line, mod = dice.roll.SortDice.parse('sd', 6)
    assert not mod.ascending
    assert line == ''


def test_sort_dice_parse_raises():
    with pytest.raises(ValueError):
        dice.roll.SortDice.parse('rrr', 6)


def test_sort_dice_modify(f_dset):
    mod = dice.roll.SortDice(ascending=True)
    mod.modify(f_dset)

    assert [int(x) for x in f_dset.all_die] == [1, 2, 5, 6]


def test_sort_dice_modify_descending(f_dset):
    mod = dice.roll.SortDice(ascending=False)
    mod.modify(f_dset)

    assert [int(x) for x in f_dset.all_die] == [6, 5, 2, 1]
