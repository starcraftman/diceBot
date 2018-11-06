"""
Tests against the dice.actions module.
These tests act as integration tests, checking almost the whole path.
Importantly, I have stubbed/mocked everything to do with discord.py and the gsheets calls.

Important Note Regarding DB:
    After executing an action ALWAYS make a new Session(). The old one will still be stale.
"""
from __future__ import absolute_import, print_function
import asyncio

import os
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
async def test_cmd_timer_seconds(f_bot):
    msg = fake_msg_gears("!timer 1")

    await action_map(msg, f_bot).execute()
    await asyncio.sleep(2)

    expect = "GearsandCogs: Timer 'GearsandCogs 1' has expired. Do something meatbag!"
    f_bot.send_message.assert_called_with(msg.channel, expect)


@pytest.mark.asyncio
async def test_cmd_timer_with_description(f_bot):
    msg = fake_msg_gears("!timer 1 -d A simple description")

    await action_map(msg, f_bot).execute()
    await asyncio.sleep(2)

    expect = "GearsandCogs: Timer 'A simple description' has expired. Do something meatbag!"
    f_bot.send_message.assert_called_with(msg.channel, expect)


@pytest.mark.asyncio
async def test_cmd_timer_with_warnings(f_bot):
    msg = fake_msg_gears("!timer 3 -w 2")

    await action_map(msg, f_bot).execute()
    await asyncio.sleep(2)
    expect = "GearsandCogs: Timer 'GearsandCogs 3' has 0:00:02 time remaining!"
    f_bot.send_message.assert_called_with(msg.channel, expect)
    await asyncio.sleep(2)


@pytest.mark.asyncio
async def test_cmd_timers(f_bot):
    msg = fake_msg_gears("!timer 4 -w 2")
    msg2 = fake_msg_gears("!timers")

    await action_map(msg, f_bot).execute()
    await action_map(msg, f_bot).execute()
    await action_map(msg2, f_bot).execute()

    capture = str(f_bot.send_message.call_args).replace("\\n", "\n")
    assert "Timer #1 with description: **GearsandCogs 4**" in capture
    assert "Timer #2 with description: **GearsandCogs 4**" in capture
    await asyncio.sleep(2)


@pytest.mark.asyncio
async def test_cmd_timers_clear(f_bot):
    msg = fake_msg_gears("!timer 4 -w 2")
    msg2 = fake_msg_gears("!timers --clear")
    msg3 = fake_msg_gears("!timers")

    await action_map(msg, f_bot).execute()
    await action_map(msg, f_bot).execute()
    await action_map(msg2, f_bot).execute()
    await action_map(msg3, f_bot).execute()

    capture = str(f_bot.send_message.call_args).replace("\\n", "\n")
    assert "None" in capture
    await asyncio.sleep(2)


@pytest.mark.skip("Not sure best way to test")
@pytest.mark.asyncio
async def test_cmd_timers_manage(f_bot):
    # TODO: Unimplemented
    pass


# TODO: dice.actions.Songs
@pytest.mark.asyncio
async def test_cmd_songs_save(f_bot):
    db = {
    }


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


def test_parse_time_spec():
    time_spec = "1:15:30"
    assert dice.actions.parse_time_spec(time_spec) == 3600 + 900 + 30


def test_remove_user_timers():
    parser = dice.parse.make_parser("!")
    msg = fake_msg_gears("!timer 1:00")
    args = parser.parse_args(msg.content.split())
    timer = dice.actions.Timer(args=args, bot=None, msg=msg)
    timers = {timer.key: timer}
    dice.actions.remove_user_timers(timers, msg.author.name)
    assert timers[timer.key].cancel


def test_validate_videos_not_youtube():
    links = ['https://google.com']

    with pytest.raises(dice.exc.InvalidCommandArgs):
        dice.actions.validate_videos(links)


def test_validate_videos_youtube_strip_angles():
    links = ['<https://youtube.com/watch=1234>']

    assert dice.actions.validate_videos(links) == ['https://youtube.com/watch=1234']


def test_validate_videos_local_not_found():
    links = ['notfound.mp3']

    with pytest.raises(dice.exc.InvalidCommandArgs):
        dice.actions.validate_videos(links)


def test_validate_videos_local_found():
    try:
        fname = '/tmp/music/found.mp3'
        try:
            os.makedirs(os.path.dirname(fname))
        except FileExistsError:
            pass
        with open(fname, 'w') as fout:
            fout.write('exist')

        dice.actions.MUSIC_PATH = os.path.dirname(fname)
        links = ['found.mp3']
        dice.actions.validate_videos(links)
    finally:
        dice.actions.MUSIC_PATH = '/tmp/music'
        os.remove(fname)
        os.rmdir(os.path.dirname(fname))


def test_fmt_music_entry():
    ent = {
        'name': 'a_name',
        'tags': [
            'a_tag_1',
            'a_tag_2',
        ],
        'url': 'a_link',
    }
    expect = 'a_name - a_link - a_tag_1, a_tag_2\n'

    assert dice.actions.fmt_music_entry(ent) == expect
