"""
Test the schema for the database.
"""
from __future__ import absolute_import, print_function

import dicedb
import dicedb.schema
from dicedb.schema import (DUser, Pun, SavedRoll, TurnOrder)


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


def test_storedturn__repr__(f_storedturns):
    turn = f_storedturns[0]
    assert repr(turn) == "TurnOrder(id='server1-chan1', text='TurnOrder')"


def test_storedturn__str__(f_storedturns):
    turn = f_storedturns[0]
    assert repr(turn) == "TurnOrder(id='server1-chan1', text='TurnOrder')"


def test_storedturn__eq__(f_storedturns):
    assert f_storedturns[0] == TurnOrder(id='server1-chan1', text='TurnOrder')


def test_parse_int():
    assert dicedb.schema.parse_int('') == 0
    assert dicedb.schema.parse_int('2') == 2
    assert dicedb.schema.parse_int(5) == 5


def test_parse_float():
    assert dicedb.schema.parse_float('') == 0.0
    assert dicedb.schema.parse_float('2') == 2.0
    assert dicedb.schema.parse_float(0.5) == 0.5
