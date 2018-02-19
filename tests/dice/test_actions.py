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
# async def test_template(f_bot):
    # msg = fake_msg_gears("!cmd")

    # await action_map(msg, f_bot).execute()

    # print(str(f_bot.send_message.call_args).replace("\\n", "\n"))


# General Parse Fails
@pytest.mark.asyncio
async def test_cmd_fail(f_bot):
    msg = fake_msg_gears("!cmd")

    with pytest.raises(dice.exc.ArgumentParseError):
        await action_map(msg, f_bot).execute()


@pytest.mark.asyncio
async def test_cmd_req_help(f_bot):
    msg = fake_msg_gears("!m -h")

    with pytest.raises(dice.exc.ArgumentHelpError):
        await action_map(msg, f_bot).execute()


@pytest.mark.asyncio
async def test_cmd_invalid_flag(f_bot):
    msg = fake_msg_gears("!m --not_there")

    with pytest.raises(dice.exc.ArgumentParseError):
        await action_map(msg, f_bot).execute()


@pytest.mark.asyncio
async def test_cmd_help(f_bot):
    msg = fake_msg_gears("!help")

    await action_map(msg, f_bot).execute()

    assert "Here is an overview of my commands." in str(f_bot.send_ttl_message.call_args)


@pytest.mark.asyncio
async def test_cmd_math(f_bot):
    msg = fake_msg_gears("!math (5 * 30) / 10")

    await action_map(msg, f_bot).execute()

    expect = """__Math Calculations__

(5 * 30) / 10 = 15.0"""
    f_bot.send_message.assert_called_with(msg.channel, expect)


@pytest.mark.asyncio
async def test_cmd_math_alias(f_bot):
    msg = fake_msg_gears("!m (5 * 30) / 10")

    await action_map(msg, f_bot).execute()

    expect = """__Math Calculations__

(5 * 30) / 10 = 15.0"""
    f_bot.send_message.assert_called_with(msg.channel, expect)


@pytest.mark.asyncio
async def test_cmd_math_fail(f_bot):
    msg = fake_msg_gears("!math math.cos(suspicious)")

    await action_map(msg, f_bot).execute()

    expect = """__Math Calculations__

'math.cos(suspicious)' looks suspicious. Allowed characters: 0-9 ()+-/*"""
    f_bot.send_message.assert_called_with(msg.channel, expect)


@pytest.mark.asyncio
async def test_cmd_roll(f_bot):
    msg = fake_msg_gears("!roll 3 * (2d6 + 3)")

    await action_map(msg, f_bot).execute()

    actual = str(f_bot.send_message.call_args).replace("\\n", "\n")
    actual = actual[actual.index("__Dice Rolls"):]
    act = actual.split('\n')

    assert len(act) == 5
    assert act[0:2] == ["__Dice Rolls__", ""]
    for line in act[2:]:
        assert line.startswith("2d6 + 3 = (")


@pytest.mark.asyncio
async def test_cmd_roll_alias(f_bot):
    msg = fake_msg_gears("!r 3 * (2d6 + 3)")

    await action_map(msg, f_bot).execute()

    actual = str(f_bot.send_message.call_args).replace("\\n", "\n")
    actual = actual[actual.index("__Dice Rolls"):]
    act = actual.split('\n')

    assert len(act) == 5
    assert act[0:2] == ["__Dice Rolls__", ""]
    for line in act[2:]:
        assert line.startswith("2d6 + 3 = (")


@pytest.mark.asyncio
async def test_cmd_status(f_bot):
    msg = fake_msg_gears("!status")

    await action_map(msg, f_bot).execute()

    expect = dice.tbl.wrap_markdown(dice.tbl.format_table([
        ['Created By', 'GearsandCogs'],
        ['Uptime', '5'],
        ['Version', '{}'.format(dice.__version__)],
    ]))
    f_bot.send_message.assert_called_with(msg.channel, expect)


@pytest.mark.asyncio
async def test_cmd_timer_seconds(monkeypatch, f_bot):
    async def fake_sleep(_):
        return None
    monkeypatch.setattr(dice.actions.asyncio, "sleep", fake_sleep)
    msg = fake_msg_gears("!timer 5")

    await action_map(msg, f_bot).execute()

    expect = "GearsandCogs Timer '5' has expired. Do something meatbag!"
    f_bot.send_message.assert_called_with(msg.channel, expect)


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
    fd1 = dice.actions.FixedRoll('5')
    fd2 = dice.actions.FixedRoll('3')
    assert (fd1 + fd2).num == 8


def test_fixed_sub():
    fd1 = dice.actions.FixedRoll('5')
    fd2 = dice.actions.FixedRoll('3')
    assert (fd1 - fd2).num == 2


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


@pytest.mark.asyncio
async def test_throw_next(event_loop):
    die = dice.actions.DiceRoll('2d6', dice.actions.OP_DICT['+'])
    die2 = dice.actions.FixedRoll('1')
    throw = dice.actions.Throw([die, die2])
    await throw.next(event_loop)

    total = 0
    for die in throw.dice:
        total += die.num
    assert total in list(range(3, 14))


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
