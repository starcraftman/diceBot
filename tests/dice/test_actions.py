"""
Tests against the dice.actions module.
These tests act as integration tests, checking almost the whole path.
Importantly, I have stubbed/mocked everything to do with discord.py and the gsheets calls.

Important Note Regarding DB:
    After executing an action ALWAYS make a new Session(). The old one will still be stale.
"""
from __future__ import absolute_import, print_function
import pytest

import dice.actions
import dice.bot
import dice.parse

from tests.conftest import fake_msg_gears


def action_map(fake_message, fake_bot):
    """
    Test stub of part of DiceBot.on_message dispatch.
    Notably, parses commands and returns Action based on parser cmd/subcmd.

    Exceute with Action.execute() coro or schedule on loop
    """
    parser = dice.parse.make_parser("!")
    args = parser.parse_args(fake_message.content.split(" "))
    cls = getattr(dice.actions, args.cmd)

    return cls(args=args, bot=fake_bot, msg=fake_message)


##################################################################
# Actual Tests


# @pytest.mark.asyncio
# async def test_template(event_loop, f_bot):
    # msg = fake_msg_gears("!cmd")

    # await action_map(msg, f_bot).execute()

    # print(str(f_bot.send_message.call_args).replace("\\n", "\n"))


# General Parse Fails
@pytest.mark.asyncio
async def test_cmd_fail(event_loop, f_bot):
    msg = fake_msg_gears("!cmd")

    with pytest.raises(dice.exc.ArgumentParseError):
        await action_map(msg, f_bot).execute()


@pytest.mark.asyncio
async def test_cmd_req_help(event_loop, f_bot):
    msg = fake_msg_gears("!m -h")

    with pytest.raises(dice.exc.ArgumentHelpError):
        await action_map(msg, f_bot).execute()


@pytest.mark.asyncio
async def test_cmd_invalid_flag(event_loop, f_bot):
    msg = fake_msg_gears("!m --not_there")

    with pytest.raises(dice.exc.ArgumentParseError):
        await action_map(msg, f_bot).execute()


def test_fixed__str__():
    die = dice.actions.FixedRoll('5')
    assert str(die) == '(5)'
    die.next_op = '__add__'
    assert str(die) == '(5) + '
    die.next_op = '__sub__'
    assert str(die) == '(5) - '


def test_fixed_spec():
    assert dice.actions.FixedRoll('5').spec == '(5)'


def test_fixed_roll():
    assert dice.actions.FixedRoll('5').roll() == 5


def test_fixed_num():
    assert dice.actions.FixedRoll('5').num == 5


def test_fixed_add():
    f1 = dice.actions.FixedRoll('5')
    f2 = dice.actions.FixedRoll('3')
    assert (f1 + f2).num == 8


def test_fixed_sub():
    f1 = dice.actions.FixedRoll('5')
    f2 = dice.actions.FixedRoll('3')
    assert (f1 - f2).num == 2


def test_dice__init__():
    die = dice.actions.DiceRoll('2d6')
    assert die.rolls == 2
    assert die.dice == 6


def test_dice__str__():
    die = dice.actions.DiceRoll('2d6')
    die.values = [2, 3]
    assert str(die) == '(2 + 3)'


def test_dice_num():
    die = dice.actions.DiceRoll('2d6')
    die.values = [2, 3]
    assert die.num == 5


def test_dice_roll():
    die = dice.actions.DiceRoll('2d6')
    die.roll()
    assert die.num in list(range(2, 13))
    for val in die.values:
        assert val in list(range(1, 7))


def test_dice_spec():
    die = dice.actions.DiceRoll('2d6')
    assert die.spec == '(2d6)'


def test_dicekeephigh__init__():
    die = dice.actions.DiceRollKeepHigh('3d6kh2')
    assert die.keep == 2
    assert die.rolls == 3
    assert die.dice == 6

    die = dice.actions.DiceRollKeepHigh('3d6k2')
    assert die.keep == 2
    assert die.rolls == 3
    assert die.dice == 6


def test_dicekeephigh__str__():
    die = dice.actions.DiceRollKeepHigh('3d6kh2')
    die.values = [3, 2, 5]
    assert str(die) == '(3 + ~~2~~ + 5)'


def test_dicekeephigh_num():
    die = dice.actions.DiceRollKeepHigh('3d6kh2')
    die.values = [3, 2, 5]
    assert die.num == 8


def test_dicekeephigh_spec():
    die = dice.actions.DiceRollKeepHigh('3d6kh2')
    assert die.spec == '(3d6kh2)'


def test_dicekeeplow__init__():
    die = dice.actions.DiceRollKeepLow('3d6kl2')
    assert die.keep == 2
    assert die.rolls == 3
    assert die.dice == 6


def test_dicekeeplow__str__():
    die = dice.actions.DiceRollKeepLow('3d6kl2')
    die.values = [3, 2, 5]
    assert str(die) == '(3 + 2 + ~~5~~)'


def test_dicekeeplow_num():
    die = dice.actions.DiceRollKeepLow('3d6kl2')
    die.values = [3, 2, 5]
    assert die.num == 5


def test_dicekeeplow_spec():
    die = dice.actions.DiceRollKeepLow('3d6kl2')
    assert die.spec == '(3d6kl2)'


def test_throw__init__():
    die = dice.actions.DiceRoll('2d6', dice.actions.OP_DICT['-'])
    die2 = dice.actions.FixedRoll('4')
    throw = dice.actions.Throw([die, die2])
    assert throw.dice == [die, die2]


def test_throw_add_dice():
    die = dice.actions.FixedRoll('4')
    throw = dice.actions.Throw()
    throw.add_dice([die])
    assert throw.dice == [die]


def test_throw_next():
    die = dice.actions.DiceRoll('2d6', dice.actions.OP_DICT['+'])
    die2 = dice.actions.FixedRoll('1')
    throw = dice.actions.Throw([die, die2])
    throw.next()

    sum = 0
    for die in throw.dice:
        sum += die.num
    assert sum in list(range(3, 14))


def test_parse_dice_spec():
    assert dice.actions.parse_dice_spec('2d6') == (2, 6)
    assert dice.actions.parse_dice_spec('2D6') == (2, 6)


def test_tokenize_dice_spec():
    spec = '4D6KH3 + 2D6 - 4'

    dies = dice.actions.tokenize_dice_spec(spec)
    assert isinstance(dies[0], dice.actions.DiceRollKeepHigh)
    assert dies[0].next_op == dice.actions.OP_DICT['+']
    assert isinstance(dies[1], dice.actions.DiceRoll)
    assert dies[1].next_op == dice.actions.OP_DICT['-']
    assert isinstance(dies[2], dice.actions.FixedRoll)
    assert len(dies) == 3
