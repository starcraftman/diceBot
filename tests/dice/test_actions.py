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


def test_format_song_list():
    header = 'A header\n\n'
    footer = '\n\nA footer'
    entries = [
        {
            'name': 'entry1',
            'tags': ['tag1', 'tag2'],
            'url': 'url1',
        },
        {
            'name': 'entry2',
            'tags': ['tag2'],
            'url': 'url1',
        },
        {
            'name': 'entry3',
            'tags': ['tag2', 'tag3'],
            'url': 'url1',
        },
    ]
    expect = """A header

        __Song 1__: entry1
        __URL__: <url1>
        __Tags__: ['tag1', 'tag2']

        __Song 2__: entry2
        __URL__: <url1>
        __Tags__: ['tag2']

        __Song 3__: entry3
        __URL__: <url1>
        __Tags__: ['tag2', 'tag3']

A footer"""

    assert dice.actions.format_song_list(header, entries, footer) == expect
