"""
Tests for dice rolling in dice.roll
"""
from __future__ import absolute_import, print_function

import pytest

import dice.roll


def test_fixed__str__():
    die = dice.roll.FixedRoll('5')
    assert str(die) == '(5)'
    die.next_op = '__add__'
    assert str(die) == '(5) + '
    die.next_op = '__sub__'
    assert str(die) == '(5) - '


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


def test_fixed_sub():
    fd1 = dice.roll.FixedRoll('5')
    fd2 = dice.roll.FixedRoll('3')
    assert (fd1 - fd2).num == 2


def test_dice__init__():
    die = dice.roll.DiceRoll('2d6')
    assert die.rolls == 2
    assert die.dice == 6


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
    assert die.dice == 6

    die = dice.roll.DiceRollKeepHigh('3d6k2')
    assert die.keep == 2
    assert die.rolls == 3
    assert die.dice == 6


def test_dicekeephigh__str__():
    die = dice.roll.DiceRollKeepHigh('3d6kh2')
    die.values = [3, 2, 5]
    assert str(die) == '(3 + ~~2~~ + 5)'


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
    assert die.dice == 6


def test_dicekeeplow__str__():
    die = dice.roll.DiceRollKeepLow('3d6kl2')
    die.values = [3, 2, 5]
    assert str(die) == '(3 + 2 + ~~5~~)'


def test_dicekeeplow_num():
    die = dice.roll.DiceRollKeepLow('3d6kl2')
    die.values = [3, 2, 5]
    assert die.num == 5


def test_dicekeeplow_spec():
    die = dice.roll.DiceRollKeepLow('3d6kl2')
    assert die.spec == '(3d6kl2)'


def test_throw__init__():
    die = dice.roll.DiceRoll('2d6', dice.roll.OP_DICT['-'])
    die2 = dice.roll.FixedRoll('4')
    throw = dice.roll.Throw([die, die2])
    assert throw.dice == [die, die2]


def test_throw_add_dice():
    die = dice.roll.FixedRoll('4')
    throw = dice.roll.Throw()
    throw.add_dice([die])
    assert throw.dice == [die]


@pytest.mark.asyncio
async def test_throw_next(event_loop):
    die = dice.roll.DiceRoll('2d6', dice.roll.OP_DICT['+'])
    die2 = dice.roll.FixedRoll('1')
    throw = dice.roll.Throw([die, die2])
    await throw.next(event_loop)

    total = 0
    for die in throw.dice:
        total += die.num
    assert total in list(range(3, 14))


def test_parse_dice_spec():
    assert dice.roll.parse_dice_spec('2d6') == (2, 6)
    assert dice.roll.parse_dice_spec('2D6') == (2, 6)


def test_tokenize_dice_spec():
    spec = '4D6KH3 + 2D6 - 4'

    dies = dice.roll.tokenize_dice_spec(spec)
    assert isinstance(dies[0], dice.roll.DiceRollKeepHigh)
    assert dies[0].next_op == dice.roll.OP_DICT['+']
    assert isinstance(dies[1], dice.roll.DiceRoll)
    assert dies[1].next_op == dice.roll.OP_DICT['-']
    assert isinstance(dies[2], dice.roll.FixedRoll)
    assert len(dies) == 3
