"""
Test dicedb.query module.
"""
from __future__ import absolute_import, print_function
import sqlalchemy.orm.exc
import mock
import pytest

import dice.exc
import dicedb
from dicedb.schema import (DUser, SavedRoll)
import dicedb.query

from tests.conftest import Member


def test_get_duser(session, f_dusers):
    assert dicedb.query.get_duser(session, '1') == f_dusers[0]
    with pytest.raises(dice.exc.NoMatch):
        dicedb.query.get_duser(session, '1000')


def test_add_duser(session, f_dusers):
    member = Member('10000', 'NotThere')
    dicedb.query.add_duser(session, member)

    duser = dicedb.query.get_duser(session, member.id)
    assert duser.display_name == member.display_name
    assert duser.id == member.id


def test_ensure_duser_exists(session, f_dusers):
    duser = f_dusers[0]
    member = Member(duser.id, 'NewName')
    returned = dicedb.query.ensure_duser(session, member)
    assert returned.display_name == member.display_name


def test_ensure_duser_not_exists(session, f_dusers):
    member = Member('99999', 'NotThereEver')
    returned = dicedb.query.ensure_duser(session, member)
    assert returned.display_name == member.display_name
    assert returned.id == member.id


def test_find_saved_roll(session, f_saved_rolls):
    roll = f_saved_rolls[0]

    assert dicedb.query.find_saved_roll(session, roll.user_id, roll.name) == roll
    assert dicedb.query.find_saved_roll(session, roll.user_id, 'bow') == roll
    with pytest.raises(dice.exc.NoMatch):
        assert dicedb.query.find_saved_roll(session, roll.user_id, 'Longsword')


def test_find_all_saved_rolls(session, f_saved_rolls):
    rolls = sorted(f_saved_rolls[:2])

    assert sorted(dicedb.query.find_all_saved_rolls(session, rolls[0].user_id)) == rolls


def test_remove_saved_roll(session, f_saved_rolls):
    roll = f_saved_rolls[0]

    assert dicedb.query.find_saved_roll(session, roll.user_id, roll.name)
    dicedb.query.remove_saved_roll(session, roll.user_id, roll.name)
    with pytest.raises(dice.exc.NoMatch):
        dicedb.query.find_saved_roll(session, roll.user_id, roll.name)


def test_update_saved_roll(session, f_saved_rolls):
    roll = f_saved_rolls[0]

    dicedb.query.update_saved_roll(session, roll.user_id, roll.name, 'NewString')
    new_roll = dicedb.query.find_saved_roll(session, roll.user_id, roll.name)
    assert new_roll.name == roll.name
    assert new_roll.user_id == roll.user_id
    assert new_roll.roll_str == 'NewString'
