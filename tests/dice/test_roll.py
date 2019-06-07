"""
Tests for dice rolling in dice.roll
"""
from __future__ import absolute_import, print_function

import pytest

import dice.exc
import dice.roll


def test_check_parenthesis():
    assert dice.roll.check_parenthesis('()')
    assert dice.roll.check_parenthesis('{}')
    assert dice.roll.check_parenthesis('[]')

    with pytest.raises(ValueError):
        dice.roll.check_parenthesis('{]')


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

    with pytest.raises(ValueError):
        dice.roll.parse_diceset(' 4d20')

    with pytest.raises(ValueError):
        dice.roll.parse_diceset('4df')

    with pytest.raises(ValueError):
        dice.roll.parse_diceset('>34d8')


def test_parse_fate_diceset():
    nspec, dset = dice.roll.parse_fate_diceset('4df')
    assert nspec == ''
    assert len(dset.all_die) == 4

    nspec, dset = dice.roll.parse_fate_diceset('10dfkh1')
    assert nspec == 'kh1'
    assert len(dset.all_die) == 10

    with pytest.raises(ValueError):
        dice.roll.parse_fate_diceset(' 4df')

    with pytest.raises(ValueError):
        dice.roll.parse_fate_diceset('4d6')

    with pytest.raises(ValueError):
        dice.roll.parse_fate_diceset('>34d8')


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


def test_parse_trailing_mods_good_combinations():
    line, all_mods = dice.roll.parse_trailing_mods('kh3dl2', 6)
    assert line == ''

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


def test_parse_trailing_mods_bad_combinations():
    with pytest.raises(ValueError):
        dice.roll.parse_trailing_mods('r4r>5f2r6', 6)


def test_parse_dice_line_fails():
    with pytest.raises(ValueError):
        dice.roll.parse_dice_line('8d10k')

    with pytest.raises(ValueError):
        dice.roll.parse_dice_line('8d10r<aaa')

    with pytest.raises(ValueError):
        dice.roll.parse_dice_line('8d10f[a,3]')

    with pytest.raises(ValueError):
        dice.roll.parse_dice_line('8d10f[1,3] + aaaa')


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

    assert str(dset) == "1 + 1 + 1 + 1"


def test_diceset_value():
    dset = dice.roll.DiceSet()
    dset.all_die = [
        dice.roll.Die(sides=6, value=5),
        dice.roll.Die(sides=6, value=2),
        dice.roll.Die(sides=6, value=6),
        dice.roll.Die(sides=6, value=1),
    ]
    assert dset.value == 14


def test_diceset_max_roll():
    dset = dice.roll.DiceSet()
    dset.all_die = [
        dice.roll.Die(sides=6, value=5),
        dice.roll.Die(sides=6, value=2),
        dice.roll.Die(sides=6, value=6),
        dice.roll.Die(sides=6, value=1),
    ]

    assert dset.max_roll == 6


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
    dset.all_die = [
        dice.roll.Die(sides=6, value=5),
        dice.roll.Die(sides=6, value=2),
        dice.roll.Die(sides=6, value=6),
        dice.roll.Die(sides=6, value=1),
    ]

    dset.add_mod(dice.roll.KeepOrDrop())
    dset.apply_mods()
    assert str(dset) == "~~5~~ + ~~2~~ + 6 + ~~1~~"


def test_keep_high__repr__():
    _, keep = dice.roll.KeepOrDrop.parse('kh10', 6)
    assert repr(keep) == "KeepOrDrop(keep=True, high=True, num=10)"


def test_keep_high_parse():
    line, keep = dice.roll.KeepOrDrop.parse('kh10dl1', 6)
    assert keep.keep
    assert keep.high
    assert keep.num == 10

    assert line == 'dl1'


def test_keep_high_parse_default():
    line, keep = dice.roll.KeepOrDrop.parse('k10dl1', 6)
    assert keep.keep
    assert keep.high
    assert keep.num == 10

    assert line == 'dl1'


def test_keep_low_parse():
    line, keep = dice.roll.KeepOrDrop.parse('kl10dl1', 6)
    assert keep.keep
    assert not keep.high
    assert keep.num == 10

    assert line == 'dl1'


def test_drop_high_parse():
    line, keep = dice.roll.KeepOrDrop.parse('dh10kh1', 6)
    assert not keep.keep
    assert keep.high
    assert keep.num == 10

    assert line == 'kh1'


def test_drop_low_parse():
    line, keep = dice.roll.KeepOrDrop.parse('dl10', 6)
    assert not keep.keep
    assert not keep.high
    assert keep.num == 10

    assert line == ''


def test_drop_low_parse_default():
    line, keep = dice.roll.KeepOrDrop.parse('d10kh1', 6)
    assert not keep.keep
    assert not keep.high
    assert keep.num == 10

    assert line == 'kh1'


def test_keep_high_modify():
    dset = dice.roll.DiceSet()
    dset.all_die = [
        dice.roll.Die(sides=6, value=5),
        dice.roll.Die(sides=6, value=2),
        dice.roll.Die(sides=6, value=6),
        dice.roll.Die(sides=6, value=1),
    ]
    dice.roll.KeepOrDrop(keep=True, high=True, num=2).modify(dset)

    assert dset.all_die[0].is_kept()
    assert not dset.all_die[1].is_kept()
    assert dset.all_die[2].is_kept()
    assert not dset.all_die[3].is_kept()


def test_keep_low_modify():
    dset = dice.roll.DiceSet()
    dset.all_die = [
        dice.roll.Die(sides=6, value=5),
        dice.roll.Die(sides=6, value=2),
        dice.roll.Die(sides=6, value=6),
        dice.roll.Die(sides=6, value=1),
    ]
    dice.roll.KeepOrDrop(keep=True, high=False, num=2).modify(dset)

    assert not dset.all_die[0].is_kept()
    assert dset.all_die[1].is_kept()
    assert not dset.all_die[2].is_kept()
    assert dset.all_die[3].is_kept()


def test_drop_low_modify():
    dset = dice.roll.DiceSet()
    dset.all_die = [
        dice.roll.Die(sides=6, value=5),
        dice.roll.Die(sides=6, value=2),
        dice.roll.Die(sides=6, value=6),
        dice.roll.Die(sides=6, value=1),
    ]
    dice.roll.KeepOrDrop(keep=False, high=False, num=2).modify(dset)

    assert dset.all_die[0].is_kept()
    assert not dset.all_die[1].is_kept()
    assert dset.all_die[2].is_kept()
    assert not dset.all_die[3].is_kept()


def test_drop_high_modify():
    dset = dice.roll.DiceSet()
    dset.all_die = [
        dice.roll.Die(sides=6, value=5),
        dice.roll.Die(sides=6, value=2),
        dice.roll.Die(sides=6, value=6),
        dice.roll.Die(sides=6, value=1),
    ]
    dice.roll.KeepOrDrop(keep=False, high=True, num=2).modify(dset)

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

    mod = dice.roll.ExplodingDice(pred=lambda x: x.value == 6)

    cnt = 10
    while cnt:
        cnt -= 1

        try:
            mod.modify(dset)
            assert [x for x in dset.all_die if x.is_exploded()]
            break
        except AssertionError:
            pass


def test_exploding_dice_parse():
    assert dice.roll.ExplodingDice.parse('!>4', 6)
    assert dice.roll.ExplodingDice.parse('!<4', 6)
    assert dice.roll.ExplodingDice.parse('!4', 6)
    assert dice.roll.ExplodingDice.parse('![4,6]', 6)


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
    mod = dice.roll.CompoundingDice(pred=lambda x: x.value == 6)

    cnt = 10
    while cnt:
        cnt -= 1

        try:
            mod.modify(dset)
            assert [x for x in dset.all_die if x.is_exploded()]
            break
        except AssertionError:
            pass


def test_compounding_dice_parse():
    assert dice.roll.CompoundingDice.parse('!!>4', 6)
    assert dice.roll.CompoundingDice.parse('!!<4', 6)
    assert dice.roll.CompoundingDice.parse('!!4', 6)
    assert dice.roll.CompoundingDice.parse('!![4,6]', 6)


def test_compounding_dice_parse_impossible():
    with pytest.raises(ValueError):
        assert dice.roll.ExplodingDice.parse('4d6', 6)

    with pytest.raises(ValueError):
        assert dice.roll.ExplodingDice.parse('!>1', 6)

    with pytest.raises(ValueError):
        assert dice.roll.ExplodingDice.parse('!!>1', 6)

    with pytest.raises(ValueError):
        assert dice.roll.ExplodingDice.parse('!!<6', 6)


def test_reroll_dice_modify():
    dset = dice.roll.DiceSet()
    dset.all_die = [
        dice.roll.Die(sides=6, value=5),
        dice.roll.Die(sides=6, value=2),
        dice.roll.Die(sides=6, value=6),
        dice.roll.Die(sides=6, value=1),
    ]
    mod = dice.roll.RerollDice(invalid_rolls=[1, 2, 3])

    cnt = 10
    while cnt:
        cnt -= 1

        try:
            mod.modify(dset)
            assert len(dset.all_die) != 4
            break
        except AssertionError:
            pass


def test_reroll_dice_parse():
    line, mod = dice.roll.RerollDice.parse('r>5r2>2', 6)
    assert mod.invalid_rolls == [2, 5, 6]

    assert line == '>2'

    line, mod = dice.roll.RerollDice.parse('r>5r2f<5', 6)
    assert mod.invalid_rolls == [2, 5, 6]

    assert line == 'f<5'


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
    line, mod = dice.roll.SuccessFail.parse('>4f<2', 6)
    assert mod.mark == 'set_success'

    assert line == 'f<2'

    line, mod = dice.roll.SuccessFail.parse('f>4<2', 6)
    assert mod.mark == 'set_fail'

    assert line == '<2'


def test_success_fail_modify():
    dset = dice.roll.DiceSet()
    dset.all_die = [
        dice.roll.Die(sides=6, value=5),
        dice.roll.Die(sides=6, value=2),
        dice.roll.Die(sides=6, value=6),
        dice.roll.Die(sides=6, value=1),
    ]
    mod = dice.roll.SuccessFail(pred=lambda x: x.value >= 4)
    mod.modify(dset)

    assert dset.all_die[0].is_success()
    assert dset.all_die[1].flags == 1
    assert dset.all_die[2].is_success()
    assert dset.all_die[3].flags == 1
