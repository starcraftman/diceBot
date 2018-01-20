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


def test_fixedroll():
    assert dice.actions.FixedRoll('5').roll() == 5
    assert str(dice.actions.FixedRoll('5')) == '(5)'


def test_diceroll():
    dado = dice.actions.DiceRoll('d6')
    assert str(dado) == '()'
    last = dado.roll()
    assert last in list(range(1, 7))
    assert str(dado) == '({})'.format(last)


def test_diceroll_multi():
    dado = dice.actions.DiceRoll('2d6')
    assert str(dado) == '()'
    last = dado.roll()
    assert last in list(range(1, 13))


def test_diceroll_add():
    dado = dice.actions.DiceRoll('2d6', dice.actions.OP_DICT['+'])
    dado2 = dice.actions.FixedRoll('3')
    dado.roll()
    print(dado + dado2)
    print(str(dado) + str(dado2))


def test_diceroll_sub():
    dado = dice.actions.DiceRoll('2d6', dice.actions.OP_DICT['-'])
    dado2 = dice.actions.FixedRoll('4')
    dado.roll()
    print(dado - dado2)
    print(str(dado) + str(dado2))


def test_tokenize_dice_spec():
    spec = '2d6 + d4 + 4'

    dados = dice.actions.tokenize_dice_spec(spec)

    print(dados[0].next_op)
    throw = dice.actions.Throw()
    throw.add_dice(dados)
    print(throw.throw())


def test_throw():
    dado = dice.actions.DiceRoll('2d6', dice.actions.OP_DICT['-'])
    dado2 = dice.actions.FixedRoll('4')
    throw = dice.actions.Throw([dado, dado2])
    print(throw.throw())


def test_rolldice_keephigh():
    dado = dice.actions.DiceRollKeepHigh('4d6kh3')
    print(dado.roll())
    print(dado.num, dado.values, str(dado))
    print(dado.spec)


def test_rolldice_keeplow():
    dado = dice.actions.DiceRollKeepLow('4d6kl3')
    print(dado.roll())
    print(dado.num, dado.values, str(dado))
    print(dado.spec)
