"""
Test the schema for the database.
"""
from __future__ import absolute_import, print_function

import dicedb
import dicedb.schema
from dicedb.schema import (DUser, Pun, SavedRoll, TurnOrder, TurnChar, Song)


def test_duser__eq__(f_dusers):
    duser = f_dusers[0]
    assert duser != DUser(id='2', display_name='User1')
    assert duser == DUser(id=duser.id, display_name=duser.display_name)


def test_duser__repr__(f_dusers):
    duser = f_dusers[0]
    assert repr(duser) == "DUser(id='{}', display_name='{}')".format(
        duser.id, duser.display_name)
    assert duser == eval(repr(duser))


def test_duser__str__(f_dusers):
    duser = f_dusers[0]
    assert str(duser) == "DUser(id='{}', display_name='{}')".format(
        duser.id, duser.display_name)


def test_duser_mention(f_dusers):
    duser = f_dusers[0]
    assert duser.mention == '<@{}>'.format(duser.id)


def test_savedrolls__eq__(f_saved_rolls):
    roll = f_saved_rolls[0]
    assert roll != SavedRoll(user_id='2', name=roll.name, roll_str=roll.roll_str)
    assert roll == SavedRoll(user_id=roll.user_id, name=roll.name, roll_str=roll.roll_str)


def test_savedrolls__repr__(f_saved_rolls):
    roll = f_saved_rolls[0]
    assert repr(roll) == "SavedRoll(id={}, user_id='1', name='Crossbow', roll_str='d20 + 7, d8')".format(roll.id)
    assert roll == eval(repr(roll))


def test_savedrolls__str__(f_saved_rolls):
    roll = f_saved_rolls[0]
    assert str(roll) == "SavedRoll(id={}, user_id='1', name='Crossbow', roll_str='d20 + 7, d8')".format(roll.id)


def test_pun__repr__(f_puns):
    pun = f_puns[0]
    assert repr(pun) == "Pun(id={}, text='First pun', hits=2)".format(pun.id)


def test_pun__str__(f_puns):
    pun = f_puns[0]
    assert str(pun) == "Pun(id={}, text='First pun', hits=2)".format(pun.id)


def test_pun__eq__(f_puns):
    assert f_puns[0] == Pun(id=9, text='First pun', hits=0)
    assert f_puns[0] == Pun(id=3, text='First pun', hits=0)
    assert f_puns[0] != Pun(id=3, text='Second pun', hits=0)


def test_pun__hash__(f_puns):
    assert f_puns[0] in f_puns


def test_pun__lt__(f_puns):
    assert f_puns[0] < f_puns[1]


def test_turnchar__init__(f_turnchars):
    char = TurnChar(user_key='1', turn_key='turn', name='Wizard', init=7)
    assert isinstance(char, TurnChar)
    assert char.name == 'Wizard'


def test_turnchar__repr__(f_turnchars):
    char = f_turnchars[0]
    assert repr(char) == "TurnChar(user_key='1', turn_key='turn', name='Wizard', init=7)"


def test_turnchar__str__(f_turnchars):
    char = f_turnchars[0]
    assert str(char) == "Wizard/7"


def test_turnchar__eq__(f_turnchars):
    char = TurnChar(user_key='1', turn_key='turn', name='Wizard', init=7)
    assert not char == TurnChar(user_key='2', turn_key='turn', name='Wizard', init=7)
    assert char == TurnChar(user_key='1', turn_key='turn', name='Guy', init=1)


def test_turnorder__init__(f_turnorders):
    turn = TurnOrder(id='guild1-chan1', text='TurnOrder')
    assert isinstance(turn, TurnOrder)
    assert turn.text == 'TurnOrder'


def test_turnorder__repr__(f_turnorders):
    turn = f_turnorders[0]
    assert repr(turn) == "TurnOrder(id='guild1-chan1', text='TurnOrder')"


def test_turnorder__str__(f_turnorders):
    turn = f_turnorders[0]
    assert repr(turn) == "TurnOrder(id='guild1-chan1', text='TurnOrder')"


def test_turnorder__eq__(f_turnorders):
    assert f_turnorders[0] == TurnOrder(id='guild1-chan1', text='TurnOrder')


def test_song__init__(f_songs):
    yt_id = '1234'
    yt_song = Song(id=9, name='youtube_{}'.format(yt_id), folder='/tmp/videos',
                   url='https://youtu.be/' + yt_id, repeat=False, volume_int=50)
    assert isinstance(yt_song, Song)


def test_parse_int():
    assert dicedb.schema.parse_int('') == 0
    assert dicedb.schema.parse_int('2') == 2
    assert dicedb.schema.parse_int(5) == 5


def test_parse_float():
    assert dicedb.schema.parse_float('') == 0.0
    assert dicedb.schema.parse_float('2') == 2.0
    assert dicedb.schema.parse_float(0.5) == 0.5
