"""
Module should handle logic related to querying/manipulating tables from a high level.
"""
from __future__ import absolute_import, print_function
import logging
import os
import sys
import tempfile

import sqlalchemy.exc as sqla_exc
import sqlalchemy.orm.exc as sqla_oexc

import dice.exc
import dicedb
from dicedb.schema import (DUser, SavedRoll)


def dump_db():  # pragma: no cover
    """
    Purely debug function, shunts db contents into file for examination.
    """
    session = dicedb.Session()
    fname = os.path.join(tempfile.gettempdir(), 'dbdump_' + os.environ.get('COG_TOKEN', 'dev'))
    print("Dumping db contents to:", fname)
    with open(fname, 'w') as fout:
        for cls in [DUser, SavedRoll]:
            fout.write('---- ' + str(cls) + ' ----\n')
            fout.writelines([str(obj) + "\n" for obj in session.query(cls)])


def get_duser(session, discord_id):
    """
    Return the DUser that has the same discord_id.

    Raises:
        NoMatch - No possible match found.
    """
    try:
        return session.query(DUser).filter_by(id=discord_id).one()
    except sqla_oexc.NoResultFound:
        raise dice.exc.NoMatch(discord_id, 'DUser')


def ensure_duser(session, member):
    """
    Ensure a member has an entry in the dusers table. A DUser is required by all users.

    Returns: The DUser
    """
    try:
        duser = get_duser(session, member.id)
        duser.display_name = member.display_name
    except dice.exc.NoMatch:
        duser = add_duser(session, member)

    return duser


def add_duser(session, member):
    """
    Add a discord user to the database.
    """
    new_duser = DUser(id=member.id, display_name=member.display_name)
    session.add(new_duser)
    session.commit()

    return new_duser


def find_saved_roll(session, user_id, name):
    """
    Find a loosely matching SavedRoll IFF there is exactly one match.

    Raises: dice.exc.NoMatch

    Returns: SavedRoll
    """
    try:
        return session.query(SavedRoll).filter(SavedRoll.user_id == user_id).\
            filter(SavedRoll.name.like('%{}%'.format(name))).one()
    except sqla_oexc.NoResultFound:
        raise dice.exc.NoMatch(user_id, 'SavedRoll')


def find_all_saved_rolls(session, user_id):
    """
    Find all SavedRolls for a given user_id. Empty list if none set.

    Returns: [SavedRoll, SavedRoll, ...]
    """
    return session.query(SavedRoll).filter(SavedRoll.user_id == user_id).all()


def update_saved_roll(session, user_id, name, roll_str):
    try:
        new_roll = find_saved_roll(session, user_id, name)
        new_roll.roll_str = roll_str
    except dice.exc.NoMatch:
        new_roll = SavedRoll(user_id=user_id, name=name, roll_str=roll_str)
    session.add(new_roll)
    session.commit()

    return new_roll


def remove_saved_roll(session, user_id, name):
    roll = None
    try:
        roll = find_saved_roll(session, user_id, name)
        session.delete(roll)
        session.commit()
    except dice.exc.NoMatch:
        pass

    return roll
