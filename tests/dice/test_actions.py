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

OGN_REASON = 'Skipped to be kind and not spam OGN, to enable set ALL_TESTS=True'
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


@OGN_TEST
@pytest.mark.asyncio
async def test_cmd_d5(f_bot):
    msg = fake_msg_gears('!d5 detect magic')

    await action_map(msg, f_bot).execute()

    expect = """Searching D&D 5e Wiki: **detect magic**
Top 3 Results:

Detect Magic – 5th Edition SRD
      <https://www.5esrd.com/spellcasting/all-spells/d/detect-magic/>
Rods, Staves & Wands – 5th Edition SRD
      <https://www.5esrd.com/gamemastering/magic-items/rods-staves-wands/>
Arcanist's Magic Aura – 5th Edition SRD
      <https://www.5esrd.com/spellcasting/all-spells/a/arcanist-s-magic-aura/>"""
    f_bot.send_message.assert_called_with(msg.channel, expect)


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


@OGN_TEST
@pytest.mark.asyncio
async def test_cmd_pf(f_bot):
    msg = fake_msg_gears('!pf acid dart')

    await action_map(msg, f_bot).execute()

    expect = """Searching Pathfinder Wiki: **acid dart**
Top 3 Results:

Acid Dart – d20PFSRD
      <https://www.d20pfsrd.com/magic/3rd-party-spells/sean-k-reynolds-games/acid-dart/>
Conjuration – d20PFSRD
      <https://www.d20pfsrd.com/classes/core-classes/wizard/arcane-schools/paizo-arcane-schools/classic-arcane-schools/conjuration/>
Earth Domain – d20PFSRD
      <https://www.d20pfsrd.com/classes/core-classes/cleric/domains/paizo-domains/earth-domain/>"""
    f_bot.send_message.assert_called_with(msg.channel, expect)


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
    f_bot.send_message.assert_called_with(msg.channel, expect)


@pytest.mark.asyncio
async def test_cmd_pf_error(f_bot):
    msg = fake_msg_gears('!pf dad2r4@@@)$*@')

    with pytest.raises(dice.exc.InvalidCommandArgs):
        await action_map(msg, f_bot).execute()


@OGN_TEST
@pytest.mark.asyncio
async def test_cmd_star(f_bot):
    msg = fake_msg_gears('!star starship')

    await action_map(msg, f_bot).execute()

    expect = """Searching Starfinder Wiki: **starship**
Top 3 Results:

Starships – Starjammer SRD
      <http://www.starjammersrd.com/equipment/starships/>
Starship Combat – Starjammer SRD
      <http://www.starjammersrd.com/game-mastering/starship-combat/>
Endbringer Devil (Starship Form) Tier 14 – Starjammer SRD
      <http://www.starjammersrd.com/equipment/starships/starships/endbringer-devil-starship-form-tier-14/>"""
    f_bot.send_message.assert_called_with(msg.channel, expect)


@pytest.mark.asyncio
async def test_cmd_poni_no_image(f_bot):
    msg = fake_msg("!poni impossible tag on there")

    await action_map(msg, f_bot).execute()

    f_bot.send_message.assert_called_with(msg.channel, 'No images found!')


@pytest.mark.asyncio
async def test_cmd_poni_one_image(f_bot):
    msg = fake_msg("!poni oc:radieux")

    await action_map(msg, f_bot).execute()

    expect = 'https://derpicdn.net/img/view/2017/2/24/1371687__safe_artist-colon-iluvchedda_'\
             'oc_oc-colon-blue+moon_oc+only_oc-colon-radieux_apple+tree_g2_moon_night_pegasus_'\
             'pony_rock_tree_unshorn+fetlocks.jpeg'
    f_bot.send_message.assert_called_with(msg.channel, expect)


@pytest.mark.asyncio
async def test_cmd_poni_more_images(f_bot):
    msg = fake_msg("!poni book fort, that pony sure does love books, safe, frown")

    await action_map(msg, f_bot).execute()

    assert 'https://' in str(f_bot.send_message.call_args).replace("\\n", "\n")


@pytest.mark.asyncio
async def test_cmd_pun(f_bot, f_puns):
    msg = fake_msg("!pun")

    await action_map(msg, f_bot).execute()

    assert 'Randomly Selected' in str(f_bot.send_message.call_args).replace("\\n", "\n")


@pytest.mark.asyncio
async def test_cmd_pun_add(session, f_bot, f_puns):
    msg = fake_msg("!pun --add A long pun here.")

    await action_map(msg, f_bot).execute()

    last = dicedb.query.all_puns(session)[-1]
    assert last.text == 'A long pun here.'


@pytest.mark.asyncio
async def test_cmd_pun_add_dupe(session, f_bot, f_puns):
    msg = fake_msg("!pun --add {}".format(f_puns[0].text))

    with pytest.raises(dice.exc.InvalidCommandArgs):
        await action_map(msg, f_bot).execute()


@pytest.mark.asyncio
async def test_cmd_roll(f_bot):
    msg = fake_msg_gears("!roll 3: 2d6 + 3")

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
    msg = fake_msg_gears("!r 3: 2d6 + 3")

    await action_map(msg, f_bot).execute()

    actual = str(f_bot.send_message.call_args).replace("\\n", "\n")
    actual = actual[actual.index("__Dice Rolls"):]
    act = actual.split('\n')

    assert len(act) == 5
    assert act[0:2] == ["__Dice Rolls__", ""]
    for line in act[2:]:
        assert line.startswith("2d6 + 3 = (")


@pytest.mark.asyncio
async def test_cmd_roll_recall(f_bot, f_saved_rolls):
    msg = fake_msg("!roll bow")

    await action_map(msg, f_bot).execute()

    capture = str(f_bot.send_message.call_args).replace("\\n", "\n")
    assert '(Crossbow)' in capture
    assert 'd20 + 7' in capture


@pytest.mark.asyncio
async def test_cmd_roll_list(f_bot, f_saved_rolls):
    expect = """__**Saved Rolls**__:

__Crossbow__: d20 + 7, d8
__Staff__: d20 + 2, d6"""

    msg = fake_msg("!roll --list")

    await action_map(msg, f_bot).execute()

    assert expect in str(f_bot.send_message.call_args).replace("\\n", "\n")


@pytest.mark.asyncio
async def test_cmd_roll_remove(f_bot, f_saved_rolls):
    removed = '__Crossbow__: d20 + 7, d8'

    msg_list = fake_msg("!roll --list")
    msg = fake_msg("!roll --remove bow")

    await action_map(msg_list, f_bot).execute()
    assert removed in str(f_bot.send_message.call_args).replace("\\n", "\n")

    await action_map(msg, f_bot).execute()

    await action_map(msg_list, f_bot).execute()
    assert removed not in str(f_bot.send_message.call_args).replace("\\n", "\n")


@pytest.mark.asyncio
async def test_cmd_roll_save(f_bot, f_saved_rolls):
    added = '__Wand__: d20 + 6, 10d6'

    msg_list = fake_msg("!roll --list")
    msg = fake_msg("!roll --save Wand d20 + 6, 10d6")

    await action_map(msg_list, f_bot).execute()
    assert added not in str(f_bot.send_message.call_args).replace("\\n", "\n")

    await action_map(msg, f_bot).execute()

    await action_map(msg_list, f_bot).execute()
    assert added in str(f_bot.send_message.call_args).replace("\\n", "\n")


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
    with mock.patch('dice.actions.CHECK_TIMER_GAP', 1):
        msg = fake_msg_gears("!timer 1")

        await action_map(msg, f_bot).execute()
        await asyncio.sleep(2)

        expect = "GearsandCogs: Timer 'GearsandCogs 1' has expired. Do something meatbag!"
        f_bot.send_message.assert_called_with(msg.channel, expect)


@pytest.mark.asyncio
async def test_cmd_timer_with_description(f_bot):
    with mock.patch('dice.actions.CHECK_TIMER_GAP', 1):
        msg = fake_msg_gears("!timer 1 -d A simple description")

        await action_map(msg, f_bot).execute()
        await asyncio.sleep(2)

        expect = "GearsandCogs: Timer 'A simple description' has expired. Do something meatbag!"
        f_bot.send_message.assert_called_with(msg.channel, expect)


@pytest.mark.asyncio
async def test_cmd_timer_with_warnings(f_bot):
    with mock.patch('dice.actions.CHECK_TIMER_GAP', 1):
        msg = fake_msg_gears("!timer 3 -w 2")

        await action_map(msg, f_bot).execute()
        await asyncio.sleep(2)
        expect = "GearsandCogs: Timer 'GearsandCogs 3' has 0:00:02 time remaining!"
        f_bot.send_message.assert_called_with(msg.channel, expect)
        await asyncio.sleep(2)


@pytest.mark.asyncio
async def test_cmd_timers(f_bot):
    with mock.patch('dice.actions.CHECK_TIMER_GAP', 1):
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


@pytest.mark.asyncio
async def test_cmd_turn_no_turn_order(f_bot, db_cleanup):
    msg = fake_msg("!turn --next")

    with pytest.raises(dice.exc.InvalidCommandArgs):
        await action_map(msg, f_bot).execute()


@pytest.mark.asyncio
async def test_cmd_turn_no_flags(f_bot, db_cleanup):
    try:
        msg = fixed_id_fake_msg("!turn --add Chris/7/21, Orc/2/10, Dwarf/3/12")
        msg2 = fixed_id_fake_msg("!turn")

        await action_map(msg, f_bot).execute()
        await action_map(msg2, f_bot).execute()

        expect = """__**Turn Order**__

```name  | mod. | init
----- | ---- | -----
Chris | +7   | 21.00
Dwarf | +3   | 12.00
Orc   | +2   | 10.00```"""
        f_bot.send_message.assert_called_with(msg2.channel, expect)
    finally:
        await action_map(fake_msg('!turn --clear'), f_bot).execute()


@pytest.mark.asyncio
async def test_cmd_turn_add(session, f_bot, db_cleanup):
    try:
        msg = fixed_id_fake_msg("!turn --add Chris/7, Orc/2")
        msg2 = fixed_id_fake_msg("!turn --add Dwarf/3/20")

        await action_map(msg, f_bot).execute()
        await action_map(msg2, f_bot).execute()

        assert dicedb.query.get_turn_order(session, '{}_{}'.format(msg.server.id, msg.channel.id))
        capture = str(f_bot.send_message.call_args).replace("\\n", "\n")
        for name in ['Chris', 'Orc', 'Dwarf']:
            assert name in capture
    finally:
        await action_map(fixed_id_fake_msg('!turn --clear'), f_bot).execute()


@pytest.mark.asyncio
async def test_cmd_turn_clear(session, f_bot, db_cleanup):
    msg = fixed_id_fake_msg("!turn --add Chris/7, Orc/2")
    msg2 = fixed_id_fake_msg("!turn --clear")
    key = '{}_{}'.format(msg.server.id, msg.channel.id)

    await action_map(msg, f_bot).execute()
    assert dicedb.query.get_turn_order(dicedb.Session(), key)
    await action_map(msg2, f_bot).execute()

    f_bot.send_message.assert_called_with(msg2.channel, 'Turn order cleared.')
    assert not dicedb.query.get_turn_order(dicedb.Session(), key)


@pytest.mark.asyncio
async def test_cmd_turn_next(f_bot, db_cleanup):
    try:
        msg = fixed_id_fake_msg("!turn --add Chris/7/21, Orc/2/10, Dwarf/3/12")
        msg2 = fixed_id_fake_msg("!turn --next")

        await action_map(msg, f_bot).execute()
        await action_map(msg2, f_bot).execute()
        await action_map(msg2, f_bot).execute()

        f_bot.send_message.assert_called_with(msg2.channel, '**Next User**\nDwarf (3): 12.00')
    finally:
        await action_map(fixed_id_fake_msg('!turn --clear'), f_bot).execute()


@pytest.mark.asyncio
async def test_cmd_turn_next_num(f_bot, db_cleanup):
    try:
        msg = fixed_id_fake_msg("!turn --add Chris/7/21, Orc/2/10, Dwarf/3/12")
        msg2 = fixed_id_fake_msg("!n 3")

        await action_map(msg, f_bot).execute()
        await action_map(msg2, f_bot).execute()

        actual = (str(f_bot.send_message.call_args).replace("\\n", "\n"))
        assert actual.count('Next User') == 3
    finally:
        await action_map(fixed_id_fake_msg('!turn --clear'), f_bot).execute()


@pytest.mark.asyncio
async def test_cmd_turn_next_with_effects(f_bot, db_cleanup):
    try:
        msg = fixed_id_fake_msg("!turn --add Chris/7/21, Orc/2/10, Dwarf/3/12")
        msg2 = fixed_id_fake_msg("!effect --add poison/1, blind/3 -t Chris")
        msg3 = fixed_id_fake_msg("!turn --next")

        await action_map(msg, f_bot).execute()
        await action_map(msg2, f_bot).execute()
        await action_map(msg3, f_bot).execute()
        await action_map(msg3, f_bot).execute()

        expect = """The following effects expired for **Chris**:

        poison

**Next User**
Dwarf (3): 12.00"""
        f_bot.send_message.assert_called_with(msg3.channel, expect)
    finally:
        await action_map(fixed_id_fake_msg('!turn --clear'), f_bot).execute()


@pytest.mark.asyncio
async def test_cmd_turn_remove_exists(f_bot, db_cleanup):
    try:
        msg = fixed_id_fake_msg("!turn --add Chris/7/21, Orc/2/10, Dwarf/3/12")
        msg2 = fixed_id_fake_msg("!turn --remove Orc")
        msg3 = fixed_id_fake_msg("!turn")

        await action_map(msg, f_bot).execute()
        await action_map(msg2, f_bot).execute()
        await action_map(msg3, f_bot).execute()

        capture = str(f_bot.send_message.call_args).replace("\\n", "\n")
        assert 'Orc' not in capture
    finally:
        await action_map(fixed_id_fake_msg('!turn --clear'), f_bot).execute()


@pytest.mark.asyncio
async def test_cmd_turn_remove_not_exists(f_bot, db_cleanup):
    try:
        msg = fixed_id_fake_msg("!turn --add Chris/7/21, Orc/2/10, Dwarf/3/12")
        msg2 = fixed_id_fake_msg("!turn --remove Cedric")

        await action_map(msg, f_bot).execute()
        with pytest.raises(dice.exc.InvalidCommandArgs):
            await action_map(msg2, f_bot).execute()
    finally:
        await action_map(fixed_id_fake_msg('!turn --clear'), f_bot).execute()


@pytest.mark.asyncio
async def test_cmd_turn_set_init(session, f_bot, f_dusers):
    try:
        msg = fixed_id_fake_msg("!turn --init 8")

        await action_map(msg, f_bot).execute()
        assert dicedb.query.get_duser(session, msg.author.id).init == 8
    finally:
        await action_map(fixed_id_fake_msg('!turn --clear'), f_bot).execute()


@pytest.mark.asyncio
async def test_cmd_turn_set_character(session, f_bot, f_dusers):
    try:
        msg = fixed_id_fake_msg("!turn --name Jack")

        await action_map(msg, f_bot).execute()
        assert dicedb.query.get_duser(session, msg.author.id).character == 'Jack'
    finally:
        await action_map(fixed_id_fake_msg('!turn --clear'), f_bot).execute()


@pytest.mark.asyncio
async def test_cmd_turn_update_user(f_bot, f_dusers):
    try:
        msg = fixed_id_fake_msg("!turn --add Chris/7/21, Orc/2/10, Dwarf/3/12")
        msg2 = fixed_id_fake_msg("!turn --update hris/1")
        msg3 = fixed_id_fake_msg("!turn")

        await action_map(msg, f_bot).execute()
        await action_map(msg2, f_bot).execute()
        await action_map(msg3, f_bot).execute()

        assert 'Chris   | +7   | 1.00' in str(f_bot.send_message.call_args).replace("\\n", "\n")
    finally:
        await action_map(fixed_id_fake_msg('!turn --clear'), f_bot).execute()


@pytest.mark.asyncio
async def test_cmd_effect_add(f_bot, db_cleanup):
    try:
        msg = fixed_id_fake_msg("!turn --add Chris/7/21, Orc/2/10, Dwarf/3/12")
        msg2 = fixed_id_fake_msg("!effect --add poison/2, blind/3 -t Chris")
        msg3 = fixed_id_fake_msg("!effect")

        await action_map(msg, f_bot).execute()
        await action_map(msg2, f_bot).execute()
        await action_map(msg3, f_bot).execute()

        expect = """__Characters With Effects__

Chris (7): 21.00
        poison: 2
        blind: 3

"""
        f_bot.send_message.assert_called_with(msg3.channel, expect)
    finally:
        await action_map(fixed_id_fake_msg('!turn --clear'), f_bot).execute()


@pytest.mark.asyncio
async def test_cmd_effect_update(f_bot, db_cleanup):
    try:
        msg = fixed_id_fake_msg("!turn --add Chris/7/21, Orc/2/10, Dwarf/3/12")
        msg2 = fixed_id_fake_msg("!effect --add poison/2, blind/3 -t Chris")
        msg3 = fixed_id_fake_msg("!effect --update poison/1, blind/1 -t Chris")
        msg4 = fixed_id_fake_msg("!effect")

        await action_map(msg, f_bot).execute()
        await action_map(msg2, f_bot).execute()
        await action_map(msg3, f_bot).execute()
        await action_map(msg4, f_bot).execute()

        expect = """__Characters With Effects__

Chris (7): 21.00
        poison: 1
        blind: 1

"""
        f_bot.send_message.assert_called_with(msg4.channel, expect)
    finally:
        await action_map(fixed_id_fake_msg('!turn --clear'), f_bot).execute()


@pytest.mark.asyncio
async def test_cmd_effect_remove(f_bot, db_cleanup):
    try:
        msg = fixed_id_fake_msg("!turn --add Chris/7/21, Orc/2/10, Dwarf/3/12")
        msg2 = fixed_id_fake_msg("!effect --add poison/2, blind/3 -t Chris")
        msg3 = fixed_id_fake_msg("!effect --remove poison -t Chris")
        msg4 = fixed_id_fake_msg("!effect")

        await action_map(msg, f_bot).execute()
        await action_map(msg2, f_bot).execute()
        await action_map(msg3, f_bot).execute()
        await action_map(msg4, f_bot).execute()

        expect = """__Characters With Effects__

Chris (7): 21.00
        blind: 3

"""
        f_bot.send_message.assert_called_with(msg4.channel, expect)
    finally:
        await action_map(fixed_id_fake_msg('!turn --clear'), f_bot).execute()


@pytest.mark.asyncio
async def test_cmd_effect_no_action(f_bot, db_cleanup):
    try:
        msg = fixed_id_fake_msg("!turn --add Chris/7/21, Orc/2/10, Dwarf/3/12")
        msg2 = fixed_id_fake_msg("!effect poison/2, blind/3 -t Chris")

        await action_map(msg, f_bot).execute()
        await action_map(msg2, f_bot).execute()

        expect = 'No action selected for targets [--add|remove|update].'
        f_bot.send_message.assert_called_with(msg2.channel, expect)
    finally:
        await action_map(fixed_id_fake_msg('!turn --clear'), f_bot).execute()


@pytest.mark.asyncio
async def test_cmd_effect_default_status(f_bot, db_cleanup):
    try:
        msg = fixed_id_fake_msg("!turn --add Chris/7/21, Orc/2/10, Dwarf/3/12")
        msg2 = fixed_id_fake_msg("!effect --add poison/2, blind/3 -t Chris")
        msg3 = fixed_id_fake_msg("!effect")

        await action_map(msg, f_bot).execute()
        await action_map(msg2, f_bot).execute()
        await action_map(msg3, f_bot).execute()

        expect = """__Characters With Effects__

Chris (7): 21.00
        poison: 2
        blind: 3

"""
        f_bot.send_message.assert_called_with(msg3.channel, expect)
    finally:
        await action_map(fixed_id_fake_msg('!turn --clear'), f_bot).execute()


@pytest.mark.asyncio
async def test_cmd_effect_turn_order_none(f_bot, db_cleanup):
    try:
        msg = fixed_id_fake_msg("!effect --add poison/2, blind/3 -t Chris")

        with pytest.raises(dice.exc.InvalidCommandArgs):
            await action_map(msg, f_bot).execute()
    finally:
        await action_map(fixed_id_fake_msg('!turn --clear'), f_bot).execute()


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
    links = ['<https://youtube.com/watch?v=1234>']

    assert dice.actions.validate_videos(links) == ['https://youtube.com/watch?v=1234']


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


def test_format_pun_list(session, f_puns):
    header = 'A header\n\n'
    footer = '\n\nA footer'

    expect = """A header

1) First pun
    Hits:    2

2) Second pun
    Hits:    0

3) Third pun
    Hits:    1

4) Fourth pun
    Hits:    0

A footer"""

    assert dice.actions.format_pun_list(header, f_puns, footer) == expect


@OGN_TEST
def test_get_results_in_background():
    full_url = 'https://cse.google.com/cse?cx=006680642033474972217%3A6zo0hx_wle8&q=acid%20dart'

    result = dice.actions.get_results_in_background(full_url, 3)
    expect = """Acid Dart – d20PFSRD
      <https://www.d20pfsrd.com/magic/3rd-party-spells/sean-k-reynolds-games/acid-dart/>
Conjuration – d20PFSRD
      <https://www.d20pfsrd.com/classes/core-classes/wizard/arcane-schools/paizo-arcane-schools/classic-arcane-schools/conjuration/>
Earth Domain – d20PFSRD
      <https://www.d20pfsrd.com/classes/core-classes/cleric/domains/paizo-domains/earth-domain/>"""
    assert result == expect
