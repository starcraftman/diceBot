# pylint: disable=redefined-outer-name,missing-function-docstring,unused-argument
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
import mock
import pytest

import dice.actions
import dice.bot
import dice.parse
import dicedb
import dicedb.query

from tests.conftest import fake_msg_gears, fake_msg, fixed_id_fake_msg

try:
    all_tasks = asyncio.all_tasks
except AttributeError:
    all_tasks = asyncio.Task.all_tasks

OGN_REASON = "Skipped to be kind and not spam OGN. To enable set env ALL_TESTS=True"
OGN_TEST = pytest.mark.skipif(not os.environ.get('ALL_TESTS'), reason=OGN_REASON)


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

    # print(str(f_bot.send.call_args).replace("\\n", "\n"))


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

    assert "Here is an overview of my commands." in str(f_bot.send.call_args)


@OGN_TEST
@pytest.mark.asyncio
async def test_cmd_d5(f_bot):
    msg = fake_msg_gears('!d5 detect magic')

    await action_map(msg, f_bot).execute()

    expect = """Searching D&D 5e Wiki: **detect magic**
Top 5 Results:

Detect Magic – 5th Edition SRD
      <https://www.5esrd.com/database/spell/detect-magic/>
Traps – 5th Edition SRD
      <https://www.5esrd.com/gamemastering/traps/>"""

    assert expect in str(f_bot.send.call_args).replace("\\n", "\n")


@pytest.mark.asyncio
async def test_cmd_math(f_bot):
    msg = fake_msg_gears("!math (5 * 30) / 10")

    await action_map(msg, f_bot).execute()

    expect = """__Math Calculations__

(5 * 30) / 10 = 15.0"""
    f_bot.send.assert_called_with(msg.channel, expect)


@pytest.mark.asyncio
async def test_cmd_math_fail(f_bot):
    msg = fake_msg_gears("!math math.cos(suspicious)")

    await action_map(msg, f_bot).execute()

    expect = """__Math Calculations__

'math.cos(suspicious)' looks suspicious. Allowed characters: 0-9 ()+-/*"""
    f_bot.send.assert_called_with(msg.channel, expect)


@OGN_TEST
@pytest.mark.asyncio
async def test_cmd_pf(f_bot):
    msg = fake_msg_gears('!pf acid dart')

    await action_map(msg, f_bot).execute()

    expect = """Searching Pathfinder Wiki: **acid dart**
Top 5 Results:

Acid Dart – d20PFSRD
      <https://www.d20pfsrd.com/magic/3rd-party-spells/sean-k-reynolds-games/acid-dart/>
Conjuration – d20PFSRD
      <https://www.d20pfsrd.com/classes/core-classes/wizard/arcane-schools/paizo-arcane-schools/classic-arcane-schools/conjuration/>
Earth Domain – d20PFSRD
      <https://www.d20pfsrd.com/classes/core-classes/cleric/domains/paizo-domains/earth-domain/>"""
    f_bot.send.assert_called_with(msg.channel, expect)


@OGN_TEST
@pytest.mark.asyncio
async def test_cmd_pf_num(f_bot):
    msg = fake_msg_gears('!pf --num 2 acid dart')

    await action_map(msg, f_bot).execute()

    expect = """Searching Pathfinder Wiki: **acid dart**
Top 2 Results:

Acid Dart – d20PFSRD
      <https://www.d20pfsrd.com/magic/3rd-party-spells/sean-k-reynolds-games/acid-dart/>
Conjuration – d20PFSRD
      <https://www.d20pfsrd.com/classes/core-classes/wizard/arcane-schools/paizo-arcane-schools/classic-arcane-schools/conjuration/>"""
    f_bot.send.assert_called_with(msg.channel, expect)


@pytest.mark.asyncio
async def test_cmd_pf_error(f_bot):
    msg = fake_msg_gears('!pf dad2r4@@@)$*@')

    with pytest.raises(dice.exc.InvalidCommandArgs):
        await action_map(msg, f_bot).execute()


@OGN_TEST
@pytest.mark.asyncio
async def test_cmd_pf2(f_bot):
    msg = fake_msg_gears('!pf2 monk')

    await action_map(msg, f_bot).execute()

    expect = """Searching Pathfinder 2e Wiki: **monk**
Top 5 Results:

Mad Monkeys
      <https://pf2.d20pfsrd.com/spell/mad-monkeys/>
Stone Giant Monk
      <https://pf2.d20pfsrd.com/npc/stone-giant-monk/>"""
    f_bot.send.assert_called_with(msg.channel, expect)


@OGN_TEST
@pytest.mark.asyncio
async def test_cmd_star(f_bot):
    msg = fake_msg_gears('!star starship')

    await action_map(msg, f_bot).execute()

    expect = """Searching Starfinder Wiki: **starship**
Top 5 Results:

Starship Combat – Starjammer SRD
      <https://www.starjammersrd.com/game-mastering/starship-combat/>"""
    assert expect in str(f_bot.send.call_args).replace("\\n", "\n")


@pytest.mark.asyncio
async def test_cmd_poni_no_image(f_bot):
    msg = fake_msg("!poni impossible tag on there")

    await action_map(msg, f_bot).execute()

    f_bot.send.assert_called_with(msg.channel, 'No images found!')


@pytest.mark.asyncio
async def test_cmd_poni_one_image(f_bot):
    msg = fake_msg("!poni oc:radieux")

    await action_map(msg, f_bot).execute()

    f_bot.send.assert_called_with(msg.channel,
                                  "https://derpicdn.net/img/view/2017/2/24/1371687.jpg")


@pytest.mark.asyncio
async def test_cmd_poni_more_images(f_bot):
    msg = fake_msg("!poni book fort, that pony sure does love books, safe, frown")

    await action_map(msg, f_bot).execute()

    assert 'https://' in str(f_bot.send.call_args).replace("\\n", "\n")


@pytest.mark.asyncio
async def test_cmd_pun(f_bot, f_puns):
    msg = fake_msg("!pun")

    await action_map(msg, f_bot).execute()

    assert 'Randomly Selected' in str(f_bot.send.call_args).replace("\\n", "\n")


@pytest.mark.asyncio
async def test_cmd_pun_add(test_db, f_bot, f_puns):
    msg = fake_msg("!pun --add A long pun here.")

    await action_map(msg, f_bot).execute()

    last = await dicedb.query.get_all_puns(test_db, 1)
    assert last['puns'][-1]['text'] == 'A long pun here.'


@pytest.mark.asyncio
async def test_cmd_pun_add_dupe(test_db, f_bot, f_puns):
    msg = fake_msg("!pun --add Dupe this text")

    await action_map(msg, f_bot).execute()
    await action_map(msg, f_bot).execute()
    # Silently ignores dupes is intended behaviour
    assert True


@pytest.mark.asyncio
async def test_cmd_roll(f_bot, f_saved_rolls):
    msg = fake_msg_gears("!roll 3: 2d6 + 3")

    await action_map(msg, f_bot).execute()

    actual = str(f_bot.send.call_args).replace("\\n", "\n")
    actual = actual[actual.index("__Dice Rolls"):]
    act = actual.split('\n')

    assert len(act) == 5
    assert act[0:2] == ["__Dice Rolls__", ""]
    for line in act[2:]:
        assert line.startswith("2d6 + 3 = ")


@pytest.mark.asyncio
async def test_cmd_roll_alias(f_bot, f_saved_rolls):
    msg = fake_msg_gears("!r 3: 2d6 + 3")

    await action_map(msg, f_bot).execute()

    actual = str(f_bot.send.call_args).replace("\\n", "\n")
    actual = actual[actual.index("__Dice Rolls"):]
    act = actual.split('\n')

    assert len(act) == 5
    assert act[0:2] == ["__Dice Rolls__", ""]
    for line in act[2:]:
        assert line.startswith("2d6 + 3 = ")


@pytest.mark.asyncio
async def test_cmd_roll_recall(f_bot, f_saved_rolls):
    msg = fake_msg("!roll bow")

    await action_map(msg, f_bot).execute()

    capture = str(f_bot.send.call_args).replace("\\n", "\n")
    assert '(Crossbow)' in capture
    assert 'd20 + 7' in capture


@pytest.mark.asyncio
async def test_cmd_roll_list(f_bot, f_saved_rolls):
    expect = """__**Saved Rolls**__:

__Crossbow__: d20 + 7, d8
__Staff__: d20 + 3, d8 - 2"""

    msg = fake_msg("!roll --list")

    await action_map(msg, f_bot).execute()

    assert expect in str(f_bot.send.call_args).replace("\\n", "\n")


@pytest.mark.asyncio
async def test_cmd_roll_remove(f_bot, f_saved_rolls):
    removed = '__Crossbow__: d20 + 7, d8'

    msg_list = fake_msg("!roll --list")
    msg = fake_msg("!roll --remove Crossbow")

    await action_map(msg_list, f_bot).execute()
    assert removed in str(f_bot.send.call_args).replace("\\n", "\n")

    await action_map(msg, f_bot).execute()

    await action_map(msg_list, f_bot).execute()
    assert removed not in str(f_bot.send.call_args).replace("\\n", "\n")


@pytest.mark.asyncio
async def test_cmd_roll_save(f_bot, f_saved_rolls):
    added = '__Wand__: d20 + 6, 10d6'

    msg_list = fake_msg("!roll --list")
    msg = fake_msg("!roll --save Wand d20 + 6, 10d6")

    await action_map(msg_list, f_bot).execute()
    assert added not in str(f_bot.send.call_args).replace("\\n", "\n")

    await action_map(msg, f_bot).execute()

    await action_map(msg_list, f_bot).execute()
    assert added in str(f_bot.send.call_args).replace("\\n", "\n")


@pytest.mark.asyncio
async def test_cmd_status(f_bot):
    msg = fake_msg_gears("!status")

    await action_map(msg, f_bot).execute()

    expect = dice.tbl.wrap_markdown(dice.tbl.format_table([
        ['Created By', 'GearsandCogs'],
        ['Uptime', '5'],
        ['Version', f'{dice.__version__}'],
    ]))
    f_bot.send.assert_called_with(msg.channel, expect)


@pytest.mark.asyncio
async def test_cmd_timer_seconds(f_bot):
    try:
        msg = fake_msg_gears("!timer 1")

        await action_map(msg, f_bot).execute()
        asyncio.ensure_future(dice.actions.timer_monitor(dice.actions.TIMERS, 0.5))
        await asyncio.sleep(2)

        expect = "GearsandCogs: Timer 'GearsandCogs 1' has expired. Do something meatbag!"
        f_bot.send.assert_called_with(msg.channel, expect)
    finally:
        for task in all_tasks():
            if 'timer_monitor' in str(task):
                task.cancel()


@pytest.mark.asyncio
async def test_cmd_timer_with_description(f_bot):
    try:
        msg = fake_msg_gears("!timer 1 -d A simple description")

        await action_map(msg, f_bot).execute()
        asyncio.ensure_future(dice.actions.timer_monitor(dice.actions.TIMERS, 0.5))
        await asyncio.sleep(2)

        expect = "GearsandCogs: Timer 'A simple description' has expired. Do something meatbag!"
        f_bot.send.assert_called_with(msg.channel, expect)
    finally:
        for task in all_tasks():
            if 'timer_monitor' in str(task):
                task.cancel()


@pytest.mark.asyncio
async def test_cmd_timer_with_warnings(f_bot):
    try:
        msg = fake_msg_gears("!timer 3 -w 2")

        await action_map(msg, f_bot).execute()
        asyncio.ensure_future(dice.actions.timer_monitor(dice.actions.TIMERS, 0.5))
        await asyncio.sleep(2)
        expect = "GearsandCogs: Timer 'GearsandCogs 3' has 0:00:02 time remaining!"
        f_bot.send.assert_called_with(msg.channel, expect)
        await asyncio.sleep(2)
    finally:
        for task in all_tasks():
            if 'timer_monitor' in str(task):
                task.cancel()


@pytest.mark.asyncio
async def test_cmd_timers(f_bot):
    try:
        msg = fake_msg_gears("!timer 4:00 -w 2")
        msg2 = fake_msg_gears("!timers")

        await action_map(msg, f_bot).execute()
        await action_map(msg, f_bot).execute()
        capture = str(f_bot.send.call_args).replace("\\n", "\n")
        assert "Starting timer for: 4:00" in capture

        await action_map(msg2, f_bot).execute()
        capture = str(f_bot.send.call_args).replace("\\n", "\n")
        assert "Active timers for" in capture
    finally:
        dice.actions.TIMERS.clear()


@pytest.mark.asyncio
async def test_cmd_timers_clear(f_bot):
    try:
        msg = fake_msg_gears("!timer 4 -w 2")
        msg2 = fake_msg_gears("!timers --clear")

        await action_map(msg, f_bot).execute()
        await action_map(msg, f_bot).execute()
        await action_map(msg2, f_bot).execute()
        f_bot.send.assert_called_with(msg2.channel, "Your timers have been cancelled.")
    finally:
        dice.actions.TIMERS.clear()


@pytest.mark.asyncio
async def test_cmd_turn_no_turn_order(f_bot):
    msg = fake_msg("!turn next")

    with pytest.raises(dice.exc.InvalidCommandArgs):
        await action_map(msg, f_bot).execute()


@pytest.mark.asyncio
async def test_cmd_turn_no_flags(f_bot):
    try:
        msg = fixed_id_fake_msg("!turn add Chris/7/21, Orc/2/10, Dwarf/3/12")
        msg2 = fixed_id_fake_msg("!turn")

        await action_map(msg, f_bot).execute()
        await action_map(msg2, f_bot).execute()

        expect = """```Name  | Init | Roll
----- | ---- | ----
Chris | 7    | 21.0
Dwarf | 3    | 12.0
Orc   | 2    | 10.0```"""
        f_bot.send.assert_called_with(msg2.channel, expect)
    finally:
        await action_map(fake_msg('!turn clear'), f_bot).execute()


@pytest.mark.asyncio
async def test_cmd_turn_add(test_db, f_bot):
    try:
        msg = fixed_id_fake_msg("!turn add Chris/7, Orc/2")
        msg2 = fixed_id_fake_msg("!turn add Dwarf/3/20")

        await action_map(msg, f_bot).execute()
        capture = str(f_bot.send.call_args).replace("\\n", "\n")
        assert 'Chris, Orc' in capture

        await action_map(msg2, f_bot).execute()
        capture = str(f_bot.send.call_args).replace("\\n", "\n")
        assert 'Dwarf' in capture
    finally:
        await action_map(fixed_id_fake_msg('!turn clear'), f_bot).execute()


@pytest.mark.asyncio
async def test_cmd_turn_clear(test_db, f_bot):
    msg = fixed_id_fake_msg("!turn add Chris/7, Orc/2")
    msg2 = fixed_id_fake_msg("!turn clear")

    await action_map(msg, f_bot).execute()
    assert await dicedb.query.get_turn_order(test_db, discord_id=1, channel_id=1)
    await action_map(msg2, f_bot).execute()

    f_bot.send.assert_called_with(msg2.channel, 'Combat tracker cleared.')
    assert not await dicedb.query.get_turn_order(test_db, discord_id=1, channel_id=1)


@pytest.mark.asyncio
async def test_cmd_turn_next(f_bot):
    try:
        msg = fixed_id_fake_msg("!turn add Chris/7/21, Orc/2/10, Dwarf/3/12")
        msg2 = fixed_id_fake_msg("!turn next")

        await action_map(msg, f_bot).execute()
        await action_map(msg2, f_bot).execute()

        '**Next User**\nDwarf (3): 12.' in str(f_bot.send.call_args).replace("\\n", "\n")
    finally:
        await action_map(fixed_id_fake_msg('!turn clear'), f_bot).execute()


@pytest.mark.asyncio
async def test_cmd_turn_next_num(f_bot):
    try:
        msg = fixed_id_fake_msg("!turn add Chris/7/21, Orc/2/10, Dwarf/3/12")
        msg2 = fixed_id_fake_msg("!n 4")

        await action_map(msg, f_bot).execute()
        await action_map(msg2, f_bot).execute()

        actual = (str(f_bot.send.call_args).replace("\\n", "\n"))
        assert "Dwarf" in actual
    finally:
        await action_map(fixed_id_fake_msg('!turn clear'), f_bot).execute()


@pytest.mark.asyncio
async def test_cmd_turn_remove_exists(f_bot):
    try:
        msg = fixed_id_fake_msg("!turn add Chris/7/21, Orc/2/10, Dwarf/3/12")
        msg2 = fixed_id_fake_msg("!turn remove Orc")
        msg3 = fixed_id_fake_msg("!turn")

        await action_map(msg, f_bot).execute()
        await action_map(msg2, f_bot).execute()
        await action_map(msg3, f_bot).execute()

        capture = str(f_bot.send.call_args).replace("\\n", "\n")
        assert 'Orc' not in capture
    finally:
        await action_map(fixed_id_fake_msg('!turn clear'), f_bot).execute()


@pytest.mark.asyncio
async def test_cmd_turn_remove_not_exists(f_bot):
    try:
        msg = fixed_id_fake_msg("!turn add Chris/7/21, Orc/2/10, Dwarf/3/12")
        msg2 = fixed_id_fake_msg("!turn remove Cedric")

        await action_map(msg, f_bot).execute()
        await action_map(msg2, f_bot).execute()  # Expected silently ignored
        assert True
    finally:
        await action_map(fixed_id_fake_msg('!turn clear'), f_bot).execute()


@pytest.mark.asyncio
async def test_cmd_turn_update_user(f_bot, f_dusers):
    try:
        msg = fixed_id_fake_msg("!turn add Chris/7/21, Orc/2/10, Dwarf/3/12")
        msg2 = fixed_id_fake_msg("!turn update Chris/1")
        msg3 = fixed_id_fake_msg("!turn")

        expect = "Chris | 7    | 1.0"
        await action_map(msg, f_bot).execute()
        assert expect not in str(f_bot.send.call_args).replace("\\n", "\n")

        await action_map(msg2, f_bot).execute()
        await action_map(msg3, f_bot).execute()
        assert expect in str(f_bot.send.call_args).replace("\\n", "\n")
    finally:
        await action_map(fixed_id_fake_msg('!turn clear'), f_bot).execute()


#  @pytest.mark.asyncio
#  async def test_cmd_turn_next_with_effects(f_bot):
    #  try:
        #  msg = fixed_id_fake_msg("!turn --add Chris/7/21, Orc/2/10, Dwarf/3/12")
        #  msg2 = fixed_id_fake_msg("!effect Chris --add poison/1, blind/3")
        #  msg3 = fixed_id_fake_msg("!turn --next")

        #  await action_map(msg, f_bot).execute()
        #  await action_map(msg2, f_bot).execute()
        #  await action_map(msg3, f_bot).execute()

        #  expect = """The following effects expired for **Chris**:

        #  poison

#  **Next User**
#  Dwarf (3): 12.00"""
        #  f_bot.send.assert_called_with(msg3.channel, expect)
    #  finally:
        #  await action_map(fixed_id_fake_msg('!turn --clear'), f_bot).execute()


#  @pytest.mark.asyncio
#  async def test_cmd_effect_add(f_bot):
    #  try:
        #  msg = fixed_id_fake_msg("!turn --add Chris/7/21, Orc/2/10, Dwarf/3/12")
        #  msg2 = fixed_id_fake_msg("!effect Chris --add poison/2, blind/3")
        #  msg3 = fixed_id_fake_msg("!effect")

        #  await action_map(msg, f_bot).execute()
        #  await action_map(msg2, f_bot).execute()
        #  await action_map(msg3, f_bot).execute()

        #  expect = """__Characters With Effects__

#  Chris (7): 21.00
        #  poison: 2
        #  blind: 3

#  """
        #  f_bot.send.assert_called_with(msg3.channel, expect)
    #  finally:
        #  await action_map(fixed_id_fake_msg('!turn --clear'), f_bot).execute()


#  @pytest.mark.asyncio
#  async def test_cmd_effect_update(f_bot):
    #  try:
        #  msg = fixed_id_fake_msg("!turn --add Chris/7/21, Orc/2/10, Dwarf/3/12")
        #  msg2 = fixed_id_fake_msg("!effect Chris --add poison/2, blind/3")
        #  msg3 = fixed_id_fake_msg("!effect Chris --update poison/1, blind/1")
        #  msg4 = fixed_id_fake_msg("!effect")

        #  await action_map(msg, f_bot).execute()
        #  await action_map(msg2, f_bot).execute()
        #  await action_map(msg3, f_bot).execute()
        #  await action_map(msg4, f_bot).execute()

        #  expect = """__Characters With Effects__

#  Chris (7): 21.00
        #  poison: 1
        #  blind: 1

#  """
        #  f_bot.send.assert_called_with(msg4.channel, expect)
    #  finally:
        #  await action_map(fixed_id_fake_msg('!turn --clear'), f_bot).execute()


#  @pytest.mark.asyncio
#  async def test_cmd_effect_remove(f_bot):
    #  try:
        #  msg = fixed_id_fake_msg("!turn --add Chris/7/21, Orc/2/10, Dwarf/3/12")
        #  msg2 = fixed_id_fake_msg("!effect Chris --add poison/2, blind/3")
        #  msg3 = fixed_id_fake_msg("!effect Chris --remove poison")
        #  msg4 = fixed_id_fake_msg("!effect")

        #  await action_map(msg, f_bot).execute()
        #  await action_map(msg2, f_bot).execute()
        #  await action_map(msg3, f_bot).execute()
        #  await action_map(msg4, f_bot).execute()

        #  expect = """__Characters With Effects__

#  Chris (7): 21.00
        #  blind: 3

#  """
        #  f_bot.send.assert_called_with(msg4.channel, expect)
    #  finally:
        #  await action_map(fixed_id_fake_msg('!turn --clear'), f_bot).execute()


#  @pytest.mark.asyncio
#  async def test_cmd_effect_no_action(f_bot):
    #  try:
        #  msg = fixed_id_fake_msg("!turn --add Chris/7/21, Orc/2/10, Dwarf/3/12")
        #  msg2 = fixed_id_fake_msg("!effect Chris poison/2, blind/3")

        #  await action_map(msg, f_bot).execute()
        #  await action_map(msg2, f_bot).execute()

        #  expect = 'No action selected for targets [--add|--remove|--update].'
        #  f_bot.send.assert_called_with(msg2.channel, expect)
    #  finally:
        #  await action_map(fixed_id_fake_msg('!turn --clear'), f_bot).execute()


#  @pytest.mark.asyncio
#  async def test_cmd_effect_default_status(f_bot):
    #  try:
        #  msg = fixed_id_fake_msg("!turn --add Chris/7/21, Orc/2/10, Dwarf/3/12")
        #  msg2 = fixed_id_fake_msg("!effect Chris --add poison/2, blind/3")
        #  msg3 = fixed_id_fake_msg("!effect")

        #  await action_map(msg, f_bot).execute()
        #  await action_map(msg2, f_bot).execute()
        #  await action_map(msg3, f_bot).execute()

        #  expect = """__Characters With Effects__

#  Chris (7): 21.00
        #  poison: 2
        #  blind: 3

#  """
        #  f_bot.send.assert_called_with(msg3.channel, expect)
    #  finally:
        #  await action_map(fixed_id_fake_msg('!turn --clear'), f_bot).execute()


#  @pytest.mark.asyncio
#  async def test_cmd_effect_turn_order_none(f_bot):
    #  try:
        #  msg = fixed_id_fake_msg("!effect Chris --add poison/2, blind/3")

        #  with pytest.raises(dice.exc.InvalidCommandArgs):
            #  await action_map(msg, f_bot).execute()
    #  finally:
        #  await action_map(fixed_id_fake_msg('!turn --clear'), f_bot).execute()


#  @pytest.mark.asyncio
#  async def test_cmd_googly_status(f_bot, f_googly):
    #  msg = fixed_id_fake_msg("!o.o")
    #  msg.author.id = '1'

    #  await action_map(msg, f_bot).execute()

    #  expect = """__**Googly Counter**__

    #  Total: 100
    #  Used: 0"""

    #  f_bot.send.assert_called_with(msg.channel, expect)


#  @pytest.mark.asyncio
#  async def test_cmd_googly_set(f_bot, f_googly):
    #  msg = fixed_id_fake_msg("!o.o --set 5")
    #  msg.author.id = '1'

    #  await action_map(msg, f_bot).execute()

    #  expect = """__**Googly Counter**__

    #  Total: 5
    #  Used: 0"""
    #  f_bot.send.assert_called_with(msg.channel, expect)


#  @pytest.mark.asyncio
#  async def test_cmd_googly_used(f_bot, f_googly):
    #  msg = fixed_id_fake_msg("!o.o --used 5")
    #  msg.author.id = '1'

    #  await action_map(msg, f_bot).execute()

    #  expect = """__**Googly Counter**__

    #  Total: 100
    #  Used: 5"""
    #  f_bot.send.assert_called_with(msg.channel, expect)


#  @pytest.mark.asyncio
#  async def test_cmd_googly_add(f_bot, f_googly):
    #  msg = fixed_id_fake_msg("!o.o 5")
    #  msg.author.id = '1'

    #  await action_map(msg, f_bot).execute()

    #  expect = """__**Googly Counter**__

    #  Total: 105
    #  Used: 0"""
    #  f_bot.send.assert_called_with(msg.channel, expect)


#  @pytest.mark.asyncio
#  async def test_cmd_googly_sub(f_bot, f_googly):
    #  msg = fixed_id_fake_msg("!o.o -5")
    #  msg.author.id = '1'

    #  await action_map(msg, f_bot).execute()

    #  expect = """__**Googly Counter**__

    #  Total: 95
    #  Used: 5"""
    #  f_bot.send.assert_called_with(msg.channel, expect)


#  @pytest.mark.asyncio
#  async def test_cmd_reroll_none(f_bot, f_lastrolls):
    #  msg = fixed_id_fake_msg("!reroll")
    #  msg.author.id = '1111'

    #  with pytest.raises(dice.exc.InvalidCommandArgs):
        #  await action_map(msg, f_bot).execute()


#  @pytest.mark.asyncio
#  async def test_cmd_reroll_last(f_bot, f_lastrolls):
    #  msg = fixed_id_fake_msg("!reroll")
    #  msg.author.id = '1'

    #  await action_map(msg, f_bot).execute()
    #  assert "**Reroll Result**\n\n4d6 + 3" in str(f_bot.send.call_args).replace("\\n", "\n")


#  @pytest.mark.asyncio
#  async def test_cmd_reroll_offset(f_bot, f_lastrolls):
    #  msg = fixed_id_fake_msg("!reroll -3")
    #  msg.author.id = '1'

    #  await action_map(msg, f_bot).execute()
    #  assert "**Reroll Result**\n\n4d6 + 1" in str(f_bot.send.call_args).replace("\\n", "\n")


#  @pytest.mark.asyncio
#  async def test_cmd_reroll_offset_invalid(f_bot, f_lastrolls):
    #  msg = fixed_id_fake_msg("!reroll -10")
    #  msg.author.id = '1'

    #  with pytest.raises(dice.exc.InvalidCommandArgs):
        #  await action_map(msg, f_bot).execute()


#  @pytest.mark.asyncio
#  async def test_cmd_movies_show(f_bot, f_movies):
    #  msg = fixed_id_fake_msg("!movies show")
    #  msg.author.id = '1'

    #  expect = """__Movies__

#  1) Toy Story
#  2) Forest Gump
#  3) A New Hope"""
    #  await action_map(msg, f_bot).execute()
    #  assert expect in str(f_bot.send.call_args).replace("\\n", "\n")


#  @pytest.mark.asyncio
#  async def test_cmd_movies_show_short(f_bot, f_movies):
    #  msg = fixed_id_fake_msg("!movies show -s")
    #  msg.author.id = '1'

    #  expect = """__Movies__

#  Toy Story, Forest Gump, A New Hope"""
    #  await action_map(msg, f_bot).execute()
    #  assert expect in str(f_bot.send.call_args).replace("\\n", "\n")


#  @pytest.mark.asyncio
#  async def test_cmd_movies_add(f_bot, f_movies):
    #  msg = fixed_id_fake_msg("!movies add Babylon 5, Power Rangers")
    #  msg.author.id = '1'
    #  msg2 = fixed_id_fake_msg("!movies show")
    #  msg2.author.id = '1'

    #  await action_map(msg, f_bot).execute()
    #  await action_map(msg2, f_bot).execute()

    #  expect = """__Movies__

#  1) Toy Story
#  2) Forest Gump
#  3) A New Hope
#  4) Babylon 5
#  5) Power Rangers"""
    #  assert expect in str(f_bot.send.call_args).replace("\\n", "\n")


#  @pytest.mark.asyncio
#  async def test_cmd_movies_update(f_bot, f_movies):
    #  msg = fixed_id_fake_msg("!movies update Babylon 5, Power Rangers")
    #  msg.author.id = '1'
    #  msg2 = fixed_id_fake_msg("!movies show")
    #  msg2.author.id = '1'

    #  await action_map(msg, f_bot).execute()
    #  await action_map(msg2, f_bot).execute()

    #  expect = """__Movies__

#  1) Babylon 5
#  2) Power Rangers"""
    #  assert expect in str(f_bot.send.call_args).replace("\\n", "\n")


#  @pytest.mark.asyncio
#  async def test_cmd_movies_roll(f_bot, f_movies):
    #  msg = fixed_id_fake_msg("!movies roll 1")
    #  msg.author.id = '1'

    #  await action_map(msg, f_bot).execute()

    #  expect = """__Movies__

#  Rolled: 1
#  Selected: Toy Story"""
    #  assert expect in str(f_bot.send.call_args).replace("\\n", "\n")


#  def test_parse_time_spec():
    #  time_spec = "1:15:30"
    #  assert dice.actions.parse_time_spec(time_spec) == 3600 + 900 + 30


#  def test_format_song_list(f_songs):
    #  header = 'A header\n\n'
    #  footer = '\n\nA footer'
    #  expect = """A header

     #  **1**)  __crit__
            #  URL:     __<https://youtu.be/IrbCrwtDIUA>__
            #  Tags: action, exciting

     #  **2**)  __pop__
            #  URL:     __<https://youtu.be/7jgnv0xCv-k>__
            #  Tags: pop, public

     #  **3**)  __late__
            #  URL:
            #  Tags: late, lotr

#  A footer"""
    #  assert dice.actions.format_song_list(header, f_songs, footer) == expect


#  def test_format_pun_list(session, f_puns):
    #  header = 'A header\n\n'
    #  footer = '\n\nA footer'

    #  expect = """A header

#  1) First pun
    #  Hits:    2

#  2) Second pun
    #  Hits:    0

#  3) Third pun
    #  Hits:    1

#  4) Fourth pun
    #  Hits:    0

#  A footer"""

    #  assert dice.actions.format_pun_list(header, f_puns, footer) == expect


#  def test_timers_summary():
    #  try:
        #  margs = mock.Mock()
        #  margs.time = '4:00'
        #  margs.author.name = 'gears'
        #  margs.offsets = []
        #  timer = dice.actions.Timer(args=margs, bot=None, msg=margs)
        #  capture = dice.actions.timer_summary({'gears 4:00': timer}, 'gears')
        #  assert "gears 4:00" in capture
        #  assert "Ends at" in capture
    #  finally:
        #  dice.actions.TIMERS.clear()


#  @pytest.mark.asyncio
#  async def test_make_rolls():
    #  pass
    #  #  capture = await dice.actions.make_rolls('3: 4d6')
    #  #  assert '4d6 = ' in capture[0]
    #  #  assert len(capture) == 3
