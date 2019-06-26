"""
Tests for dice rolling in dice.roll
"""
from __future__ import absolute_import, print_function
import re

import pytest

import dice.exc
import dice.roll
from dice.roll import (Comparison, CompareEqual, CompareRange, CompareLessEqual, CompareGreaterEqual,
                       RerollDice, ExplodeDice, CompoundDice, KeepDrop,
                       SuccessFail, SortDice, AThrow, DiceList, Die, FateDie)


@pytest.fixture
def f_dlist():
    dlist = dice.roll.DiceList()
    dlist += [
        dice.roll.Die(sides=6, value=5),
        dice.roll.Die(sides=6, value=2),
        dice.roll.Die(sides=6, value=6),
        dice.roll.Die(sides=6, value=1),
    ]

    yield dlist


@pytest.fixture
def f_athrow(f_dlist):
    throw = dice.roll.AThrow(spec='4d6 + 4', note='note', items=[f_dlist, '+', '4'])

    yield throw


def test_regex_is_die():
    assert dice.roll.IS_DIE.match("d20").groups() == (None, '20')
    assert dice.roll.IS_DIE.match("40d20").groups() == ('40', '20')
    assert dice.roll.IS_DIE.match("40D20").groups() == ('40', '20')
    assert not dice.roll.IS_DIE.match("4df")
    assert not dice.roll.IS_DIE.match("kh1")


def test_regex_is_fatedie():
    assert dice.roll.IS_FATEDIE.match("df").groups() == (None,)
    assert dice.roll.IS_FATEDIE.match("40df").groups() == ('40',)
    assert dice.roll.IS_FATEDIE.match("40Df").groups() == ('40',)
    assert not dice.roll.IS_FATEDIE.match("d20")
    assert not dice.roll.IS_FATEDIE.match("kh1")


def test_regex_is_literal():
    assert dice.roll.IS_LITERAL.match('+').groups() == ('+', None)
    assert dice.roll.IS_LITERAL.match('-').groups() == ('-', None)
    assert dice.roll.IS_LITERAL.match('+ ').groups() == ('+', None)
    assert dice.roll.IS_LITERAL.match('- ').groups() == ('-', None)
    assert not dice.roll.IS_LITERAL.match('*')
    assert not dice.roll.IS_LITERAL.match('/')

    assert dice.roll.IS_LITERAL.match('42').groups() == (None, '42')
    assert not dice.roll.IS_LITERAL.match('aaa')
    assert not dice.roll.IS_LITERAL.match('4d20kh1')
    assert not dice.roll.IS_LITERAL.match('4df')


def test_regex_reroll_match():
    assert dice.roll.REROLL_MATCH.match('r4')
    assert dice.roll.REROLL_MATCH.match('r=4')
    assert dice.roll.REROLL_MATCH.match('r<4')
    assert dice.roll.REROLL_MATCH.match('r>4')
    assert dice.roll.REROLL_MATCH.match('r[3,5]')
    assert dice.roll.REROLL_MATCH.match('ro[3,5]')
    assert dice.roll.REROLL_MATCH.findall('r4kl2!>5ro>4') == [('', '', 'r4'), ('', 'ro>4', '')]


def test_check_parentheses():
    assert dice.roll.check_parentheses('()')
    assert dice.roll.check_parentheses('{}')
    assert dice.roll.check_parentheses('[]')

    with pytest.raises(ValueError):
        dice.roll.check_parentheses('{]')


def test_comparison__init__():
    comp = CompareRange(left=3, right=5)
    assert comp(3)


def test_comparison__repr__():
    comp = CompareRange(left=3, right=5)
    assert repr(comp) == "CompareRange(left=3, right=5)"


def test_comparison__call__():
    with pytest.raises(TypeError):
        Comparison(left=3)


def test_comp_range():
    comp = CompareRange(left=3, right=5)
    assert comp(3)
    assert not comp(1)
    assert comp(5)
    assert not comp(6)


def test_comp_less_equal():
    comp = CompareLessEqual(left=3)
    assert comp(3)
    assert comp(1)
    assert not comp(6)


def test_comp_greater_equal():
    comp = CompareGreaterEqual(left=3)
    assert comp(3)
    assert not comp(1)
    assert comp(6)


def test_comp_equal():
    comp = CompareEqual(left=3)
    assert comp(3)
    assert not comp(1)
    assert not comp(6)


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


def test_parse_dicelist():
    nspec, dlist = dice.roll.parse_dicelist('4d20kh1')
    assert nspec == ''
    assert len(dlist) == 4
    assert dlist.mods == [KeepDrop(num=1)]

    nspec, dlist = dice.roll.parse_dicelist('20d100!!<6 + 4d10 - 2')
    assert nspec == ' + 4d10 - 2'
    assert len(dlist) == 20
    assert dlist.mods == [CompoundDice(pred=CompareLessEqual(left=5))]


def test_parse_dicelist_raises():
    with pytest.raises(ValueError):
        dice.roll.parse_dicelist(' 4d20')

    with pytest.raises(ValueError):
        dice.roll.parse_dicelist('4df')

    with pytest.raises(ValueError):
        dice.roll.parse_dicelist('>34d8')

    with pytest.raises(dice.exc.InvalidCommandArgs):
        dice.roll.parse_dicelist('4000000000d20')

    with pytest.raises(dice.exc.InvalidCommandArgs):
        dice.roll.parse_dicelist('4d2000000000000')


def test_parse_fate_dicelist():
    nspec, dlist = dice.roll.parse_fate_dicelist('4df')
    assert nspec == ''
    assert len(dlist) == 4

    nspec, dlist = dice.roll.parse_fate_dicelist('10dfkh1')
    assert nspec == ''
    assert len(dlist) == 10
    assert dlist.mods == [KeepDrop(num=1)]


def test_parse_fate_dicelist_raises():
    with pytest.raises(ValueError):
        dice.roll.parse_fate_dicelist(' 4df')

    with pytest.raises(ValueError):
        dice.roll.parse_fate_dicelist('4d6')

    with pytest.raises(ValueError):
        dice.roll.parse_fate_dicelist('>34d8')

    with pytest.raises(dice.exc.InvalidCommandArgs):
        dice.roll.parse_fate_dicelist('4000000000df')


def test_parse_trailing_mods():
    line, all_mods = dice.roll.parse_trailing_mods('k1 + 4', 6)
    assert all_mods == [KeepDrop(keep=True, high=True, num=1)]
    assert line == ' + 4'

    line, all_mods = dice.roll.parse_trailing_mods('d1 + 4', 6)
    assert all_mods == [KeepDrop(keep=False, high=False, num=1)]
    assert line == ' + 4'

    line, all_mods = dice.roll.parse_trailing_mods('kh3dl2 + 4d20 + 20', 6)
    assert all_mods == [KeepDrop(keep=True, high=True, num=3),
                        KeepDrop(keep=False, high=False, num=2)]
    assert line == ' + 4d20 + 20'

    line, all_mods = dice.roll.parse_trailing_mods('kl2dh1', 6)
    assert all_mods == [KeepDrop(keep=True, high=False, num=2),
                        KeepDrop(keep=False, high=True, num=1)]
    assert line == ''

    line, all_mods = dice.roll.parse_trailing_mods('kl2!>5r4r>4', 6)
    assert all_mods == [KeepDrop(keep=True, high=False, num=2),
                        ExplodeDice(pred=CompareGreaterEqual(left=5), penetrate=False),
                        RerollDice(reroll_always=[4, 5, 6])]
    assert line == ''

    line, all_mods = dice.roll.parse_trailing_mods('kl2!p>5r4r>4', 6)
    assert all_mods == [KeepDrop(keep=True, high=False, num=2),
                        ExplodeDice(pred=CompareGreaterEqual(left=5), penetrate=True),
                        RerollDice(reroll_always=[4, 5, 6])]
    assert line == ''

    line, all_mods = dice.roll.parse_trailing_mods('kl2!!>5r4r>4', 6)
    assert all_mods == [KeepDrop(keep=True, high=False, num=2),
                        CompoundDice(pred=CompareGreaterEqual(left=5), penetrate=False),
                        RerollDice(reroll_always=[4, 5, 6])]
    assert line == ''

    line, all_mods = dice.roll.parse_trailing_mods('kl2!>5r4r>4f<2', 6)
    assert all_mods == [KeepDrop(keep=True, high=False, num=2),
                        ExplodeDice(pred=CompareGreaterEqual(left=5), penetrate=False),
                        RerollDice(reroll_always=[4, 5, 6]),
                        SuccessFail(pred=CompareLessEqual(left=2), mark_success='set_fail')]
    assert line == ''

    line, all_mods = dice.roll.parse_trailing_mods('kl2!>5r4r>4f<2>5', 6)
    assert all_mods == [KeepDrop(keep=True, high=False, num=2),
                        ExplodeDice(pred=CompareGreaterEqual(left=5), penetrate=False),
                        RerollDice(reroll_always=[4, 5, 6]),
                        SuccessFail(pred=CompareLessEqual(left=2), mark_success='set_fail'),
                        SuccessFail(pred=CompareGreaterEqual(left=5), mark_success='set_success')]
    assert line == ''

    line, all_mods = dice.roll.parse_trailing_mods('kl2!>5r4r>4f<2>5s', 6)
    assert all_mods == [KeepDrop(keep=True, high=False, num=2),
                        ExplodeDice(pred=CompareGreaterEqual(left=5), penetrate=False),
                        RerollDice(reroll_always=[4, 5, 6]),
                        SuccessFail(pred=CompareLessEqual(left=2), mark_success='set_fail'),
                        SuccessFail(pred=CompareGreaterEqual(left=5), mark_success='set_success'),
                        SortDice()]
    assert line == ''


def test_parse_trailing_mods_raises():
    with pytest.raises(ValueError):
        dice.roll.parse_trailing_mods('khr<dl', 6)


def test_parse_literal():
    line, lit = dice.roll.parse_literal("+ 42")
    assert line == " 42"
    assert lit == "+"

    line, lit = dice.roll.parse_literal("- 42")
    assert line == " 42"
    assert lit == "-"

    line, lit = dice.roll.parse_literal("42 + 1")
    assert line == " + 1"
    assert lit == "42"

    line, lit = dice.roll.parse_literal("42 + 4d6")
    assert line == " + 4d6"
    assert lit == "42"

    line, lit = dice.roll.parse_literal("+42")
    assert line == "42"
    assert lit == "+"


def test_parse_literal_raises():
    with pytest.raises(ValueError):
        dice.roll.parse_literal("* 42")

    with pytest.raises(ValueError):
        dice.roll.parse_literal("/ 42")

    with pytest.raises(ValueError):
        dice.roll.parse_literal("% 42")


def test_parse_comments_from_line():
    assert dice.roll.parse_comments_from_back('4d6 + 10 This is a comment.   ') == ('4d6 + 10', 'This is a comment.')
    assert dice.roll.parse_comments_from_back('4d6 + 10') == ('4d6 + 10', '')
    assert dice.roll.parse_comments_from_back('') == ('', '')
    assert dice.roll.parse_comments_from_back('This is a comment.') == ('', 'This is a comment.')
    assert dice.roll.parse_comments_from_back('4d6 + 10 This is a comment. + 2d10') == ('4d6 + 10 This is a comment. + 2d10', '')


def test_parse_dice_line():
    expect = AThrow(spec='4d8 + 2df + 6', items=[DiceList(items=[Die(sides=8, value=1, flags=1), Die(sides=8, value=1, flags=1), Die(sides=8, value=1, flags=1), Die(sides=8, value=1, flags=1)], mods=[]), '+', DiceList(items=[FateDie(sides=3, value=2, flags=1), FateDie(sides=3, value=2, flags=1)], mods=[]), '+', '6'])
    throw = dice.roll.parse_dice_line('4d8 + 2df + 6')
    assert throw == expect


def test_parse_dice_line_comment():
    throw = dice.roll.parse_dice_line("4 + 4 a comment here")
    assert throw.next() == "4 + 4 = 4 + 4 = 8\n        Note: a comment here"


def test_parse_dice_line_raises():
    with pytest.raises(ValueError):
        dice.roll.parse_dice_line('8d10k')

    with pytest.raises(ValueError):
        dice.roll.parse_dice_line('8d10r<aaa')

    with pytest.raises(ValueError):
        dice.roll.parse_dice_line('8d10f[a,3]')

    with pytest.raises(ValueError):
        dice.roll.parse_dice_line('Just a comment.')


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


# Implicitly test FlaggableMixin interface
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
    die = dice.roll.FateDie(sides=10, value=1, flags=1)
    assert die.sides == 3
    assert die._value == 1
    assert die.flags == 1


def test_fatedie__repr__():
    die = dice.roll.FateDie(sides=10, value=1, flags=1)
    assert repr(die) == "FateDie(sides=3, value=1, flags=1)"


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
    die._value = 1
    assert die.value == -1

    die._value = 2
    assert die.value == 0

    die._value = 3
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


def test_dicelist__init__():
    dlist = dice.roll.DiceList()
    assert str(dlist) == ""


def test_dicelist__repr__():
    dlist = dice.roll.DiceList()
    dlist.add_dice(4, 6)

    expect = "DiceList(items=[Die(sides=6, value=1, flags=1), Die(sides=6, value=1, flags=1), Die(sides=6, value=1, flags=1), Die(sides=6, value=1, flags=1)], mods=[])"
    assert repr(dlist) == expect


def test_dicelist__str__():
    dlist = dice.roll.DiceList()
    dlist.add_dice(4, 6)

    assert str(dlist) == "(1 + 1 + 1 + 1)"


def test_dicelist__str__fatedie():
    dlist = dice.roll.DiceList()
    dlist.add_fatedice(3)

    assert str(dlist) == "(0 0 0)"


def test_dicelist__str__empty():
    dlist = dice.roll.DiceList()

    assert str(dlist) == ""


def test_dicelist__str__truncate():
    dlist = dice.roll.DiceList()
    dlist.add_dice(200, 100)

    assert str(dlist) == "(1 + 1 + ... 1)"


def test_dicelist_value(f_dlist):
    assert f_dlist.value == 14


def test_dicelist_max_roll(f_dlist):
    assert f_dlist.max_roll == 6


def test_dicelist_add_die():
    dlist = dice.roll.DiceList()
    dlist.add_dice(4, 6)
    assert len(dlist) == 4
    assert issubclass(type(dlist[0]), dice.roll.Die)


def test_dicelist_add_fatedie():
    dlist = dice.roll.DiceList()
    dlist.add_fatedice(4)
    assert len(dlist) == 4
    assert issubclass(type(dlist[0]), dice.roll.FateDie)


def test_dicelist_roll_no_mod():
    dlist = dice.roll.DiceList()
    dlist.add_dice(4, 6)
    assert str(dlist) == "(1 + 1 + 1 + 1)"
    dlist.roll()
    assert str(dlist) != "(1 + 1 + 1 + 1)"


def test_dicelist_roll_mods():
    dlist = dice.roll.DiceList()
    dlist.add_dice(4, 6)
    dlist.mods += [dice.roll.KeepDrop(num=2)]
    dlist.roll()
    dlist.apply_mods()

    assert str(dlist).count("~~") == 4


def test_athrow__repr__(f_athrow):
    expect = "AThrow(spec='4d6 + 4', note='note', items=[DiceList(items=[Die(sides=6, value=5, flags=1), Die(sides=6, value=2, flags=1), Die(sides=6, value=6, flags=1), Die(sides=6, value=1, flags=1)], mods=[]), '+', '4'])"
    assert repr(f_athrow) == expect


def test_athrow__str__(f_athrow):
    assert str(f_athrow) == "(5 + 2 + 6 + 1) + 4"


def test_athrow__eq__(f_athrow):
    assert AThrow(items=['4']) == AThrow(items=['4'])
    dlist = DiceList(items=[Die(sides=6, value=5, flags=1), Die(sides=6, value=2, flags=1), Die(sides=6, value=6, flags=1), Die(sides=6, value=1, flags=1)], mods=[])
    assert dlist == DiceList(items=[Die(sides=6, value=5, flags=1), Die(sides=6, value=2, flags=1), Die(sides=6, value=6, flags=1), Die(sides=6, value=1, flags=1)], mods=[])
    assert dlist != AThrow(items=['4'])


def test_athrow_value(f_athrow):
    assert f_athrow.value == 18


def test_athrow_add(f_athrow):
    f_athrow += ['+']
    assert str(f_athrow) == "(5 + 2 + 6 + 1) + 4 +"


def test_athrow_roll(f_athrow):
    f_athrow.roll()
    assert str(f_athrow) != "(5 + 2 + 6 + 1) + 4"


def test_athrow_string_success(f_athrow):
    f_dlist = f_athrow[0]
    pred = CompareGreaterEqual(left=5)
    f_dlist.mods = [dice.roll.SuccessFail(mark_success=True, pred=pred)]
    f_dlist.apply_mods()
    assert f_athrow.success_string() == "(+2) **0** Failure(s), **2** Success(es)"


def test_athrow_string_fail(f_athrow):
    f_dlist = f_athrow[0]
    pred = CompareLessEqual(left=2)
    f_dlist.mods = [dice.roll.SuccessFail(mark_success=False, pred=pred)]
    f_dlist.apply_mods()
    assert f_athrow.success_string() == "(-2) **2** Failure(s), **0** Success(es)"


def test_athrow_string_success_and_fail(f_athrow):
    f_dlist = f_athrow[0]
    pred = CompareGreaterEqual(left=5)
    pred2 = CompareLessEqual(left=2)
    f_dlist.mods = [dice.roll.SuccessFail(mark_success=True, pred=pred),
                    dice.roll.SuccessFail(mark_success=False, pred=pred2)]

    f_dlist.apply_mods()
    assert f_athrow.success_string() == "(+0) **2** Failure(s), **2** Success(es)"


def test_athrow_next(f_athrow):
    assert re.match(r'4d6 \+ 4 = [ 0-9\+=()]+', f_athrow.next())


def test_athrow_next_note(f_athrow):
    f_athrow.note = "A note"
    first, second = f_athrow.next().split('\n')
    assert re.match(r'4d6 \+ 4 = [ 0-9\+=()]+', first)
    assert second.lstrip() == "Note: A note"


def test_explode_dice_should_parse():
    assert dice.roll.ExplodeDice.should_parse('!>5')
    assert dice.roll.ExplodeDice.should_parse('!p>5')
    assert not dice.roll.ExplodeDice.should_parse('ro<2')
    assert not dice.roll.ExplodeDice.should_parse('')


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


def test_explode_dice_modify(f_dlist):
    mod = dice.roll.ExplodeDice(pred=CompareEqual(left=6))
    mod.modify(f_dlist)
    assert [d for d in f_dlist if d.is_exploded()]
    assert len(f_dlist) >= 5


def test_penetrate_dice_parse():
    assert dice.roll.ExplodeDice.parse('!p>4', 6)[1].penetrate


def test_penetrate_dice_parse_raises():
    with pytest.raises(ValueError):
        dice.roll.ExplodeDice.parse('!p', 6)

    with pytest.raises(ValueError):
        dice.roll.ExplodeDice.parse('!p>', 6)


def test_penetrate_dice_modify(f_dlist):
    mod = dice.roll.ExplodeDice(pred=CompareEqual(left=6), penetrate=True)
    mod.modify(f_dlist)
    assert [d for d in f_dlist if d.is_penetrated()]
    assert len(f_dlist) >= 5


def test_compound_dice_should_parse():
    assert dice.roll.CompoundDice.should_parse('!!>4kh2')
    assert not dice.roll.CompoundDice.should_parse('ro<2')
    assert not dice.roll.CompoundDice.should_parse('')


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


def test_compound_dice_modify(f_dlist):
    mod = dice.roll.CompoundDice(pred=lambda x: x.value == 6)
    mod.modify(f_dlist)
    assert [d for d in f_dlist if d.is_exploded()]
    assert len(f_dlist) >= 4


def test_reroll_dice_should_parse():
    assert dice.roll.RerollDice.should_parse('r>6')
    assert dice.roll.RerollDice.should_parse('ro<2')
    assert not dice.roll.RerollDice.should_parse('!!>6')
    assert not dice.roll.RerollDice.should_parse('')


def test_reroll_dice_parse():
    line, mod = dice.roll.RerollDice.parse('r>5r2>2', 6)
    assert mod.reroll_always == [2, 5, 6]
    assert not mod.reroll_once
    assert line == '>2'

    line, mod = dice.roll.RerollDice.parse('r>5r2f<5', 6)
    assert mod.reroll_always == [2, 5, 6]
    assert not mod.reroll_once
    assert line == 'f<5'


def test_reroll__once_dice_parse():
    line, mod = dice.roll.RerollDice.parse('ro>5ro2>2', 6)
    assert not mod.reroll_always
    assert mod.reroll_once == [2, 5, 6]
    assert line == '>2'

    line, mod = dice.roll.RerollDice.parse('ro>5ro2f<5', 6)
    assert not mod.reroll_always
    assert mod.reroll_once == [2, 5, 6]
    assert line == 'f<5'


def test_reroll__both_dice_parse():
    line, mod = dice.roll.RerollDice.parse('ro>5r2r[1,2]>2', 6)
    assert mod.reroll_always == [1, 2]
    assert mod.reroll_once == [5, 6]
    assert line == '>2'


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

    with pytest.raises(ValueError):
        dice.roll.RerollDice.parse('r1ro1', 6)


def test_reroll_dice_modify(f_dlist):
    mod = dice.roll.RerollDice(reroll_always=[1, 2, 3])
    mod.modify(f_dlist)
    assert len(f_dlist) >= 6


def test_reroll_once_dice_modify(f_dlist):
    mod = dice.roll.RerollDice(reroll_once=[1, 2, 3])
    mod.modify(f_dlist)
    assert len(f_dlist) == 6


def test_keep_high__repr__():
    keep = dice.roll.KeepDrop(num=10)
    assert repr(keep) == "KeepDrop(keep=True, high=True, num=10)"


def test_keep_drop_should_parse():
    assert dice.roll.KeepDrop.should_parse('kh2')
    assert dice.roll.KeepDrop.should_parse('d1')
    assert not dice.roll.KeepDrop.should_parse('!!>6')
    assert not dice.roll.KeepDrop.should_parse('')


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


def test_keep_high_modify(f_dlist):
    dice.roll.KeepDrop(keep=True, high=True, num=2).modify(f_dlist)

    assert f_dlist[0].is_kept()
    assert not f_dlist[1].is_kept()
    assert f_dlist[2].is_kept()
    assert not f_dlist[3].is_kept()


def test_keep_low_modify(f_dlist):
    dice.roll.KeepDrop(keep=True, high=False, num=2).modify(f_dlist)

    assert not f_dlist[0].is_kept()
    assert f_dlist[1].is_kept()
    assert not f_dlist[2].is_kept()
    assert f_dlist[3].is_kept()


def test_drop_low_modify(f_dlist):
    dice.roll.KeepDrop(keep=False, high=False, num=2).modify(f_dlist)

    assert not f_dlist[0].is_dropped()
    assert f_dlist[1].is_dropped()
    assert not f_dlist[2].is_dropped()
    assert f_dlist[3].is_dropped()


def test_drop_high_modify(f_dlist):
    dice.roll.KeepDrop(keep=False, high=True, num=2).modify(f_dlist)

    assert f_dlist[0].is_dropped()
    assert not f_dlist[1].is_dropped()
    assert f_dlist[2].is_dropped()
    assert not f_dlist[3].is_dropped()


def test_success_fail_should_parse():
    assert dice.roll.SuccessFail.should_parse('f<2')
    assert dice.roll.SuccessFail.should_parse('<2')
    assert dice.roll.SuccessFail.should_parse('[4,5]kh2')
    assert not dice.roll.SuccessFail.should_parse('!!>6')
    assert not dice.roll.SuccessFail.should_parse('')


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


def test_success_fail_modify(f_dlist):
    mod = dice.roll.SuccessFail(pred=lambda x: x.value >= 4)
    mod.modify(f_dlist)

    assert f_dlist[0].is_success()
    assert not f_dlist[1].is_success()
    assert f_dlist[2].is_success()
    assert not f_dlist[3].is_success()


def test_sort_dice_should_parse():
    assert dice.roll.SortDice.should_parse('sd')
    assert not dice.roll.SortDice.should_parse('!!>6')
    assert not dice.roll.SortDice.should_parse('')


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


def test_sort_dice_modify(f_dlist):
    mod = dice.roll.SortDice(ascending=True)
    mod.modify(f_dlist)

    assert [int(x) for x in f_dlist] == [1, 2, 5, 6]


def test_sort_dice_modify_descending(f_dlist):
    mod = dice.roll.SortDice(ascending=False)
    mod.modify(f_dlist)

    assert [int(x) for x in f_dlist] == [6, 5, 2, 1]
