"""
Tests for dice.exc
"""
from __future__ import absolute_import, print_function

import mock

import dice.exc

from tests.conftest import fake_msg_gears, Channel


def test_dice_exception_reply():
    error = dice.exc.DiceException("An exception happened :(", lvl='info')
    assert str(error) == "An exception happened :("


def test_dice_exception_write_log():
    error = dice.exc.DiceException("An exception happened :(", lvl='info')

    log = mock.Mock()
    log.info.return_value = None
    msg = fake_msg_gears("I don't like exceptions")
    error.write_log(log, content=msg.content, author=msg.author, channel=msg.channel)
    expect = """
DiceException: An exception happened :(
====================
GearsandCogs sent I don't like exceptions from Channel: live_hudson/Server: Gears' Hideout
    Discord ID: 1000
    Username: GearsandCogs#12345
    Cookie Lord on Gears' Hideout"""
    log.info.assert_called_with(expect)


def test_more_one_match():
    error = dice.exc.MoreThanOneMatch('LHS', ['LHS 1', 'LHS 2', 'LHS 3'])
    expect = """Resubmit query with more specific criteria.
Too many matches for 'LHS' in strings:
    - __LHS__ 1
    - __LHS__ 2
    - __LHS__ 3"""
    assert str(error) == expect

    error = dice.exc.MoreThanOneMatch('Channel',
                                      [Channel('Channel 1'), Channel('Channel 2'), Channel('Channel 3')],
                                      'name')
    expect = """Resubmit query with more specific criteria.
Too many matches for 'Channel' in Channels:
    - __Channel__ 1
    - __Channel__ 2
    - __Channel__ 3"""
    assert str(error) == expect


def test_no_match():
    error = dice.exc.NoMatch('Cubeo', 'System')
    assert str(error) == "No matches for 'Cubeo' in Systems."
    error = dice.exc.NoMatch('Person1', 'person')
    assert str(error) == "No matches for 'Person1' in persons."


def test_name_collision_error():
    expect = """**Critical Error**
----------------
CMDR "Gears" found in rows [20, 33] of the Cattle Sheet

To Resolve:
    Delete or rename the cmdr in one of these rows
    Then execute `admin scan` to reload the db"""
    error = dice.exc.NameCollisionError('Cattle', 'Gears', [20, 33])
    assert error.reply() == expect


def test_log_format():
    msg = fake_msg_gears('Hello world!')
    expect = """GearsandCogs sent Hello world! from Channel: live_hudson/Server: Gears' Hideout
    Discord ID: 1000
    Username: GearsandCogs#12345
    Cookie Lord on Gears' Hideout"""

    log_msg = dice.exc.log_format(content=msg.content, author=msg.author, channel=msg.channel)
    assert log_msg == expect
