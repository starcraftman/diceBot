"""
Module should handle logic related to querying/manipulating tables from a high level.
"""
from __future__ import absolute_import, print_function
import os
import tempfile

import numpy.random
import sqlalchemy.orm.exc as sqla_oexc
from sqlalchemy import func

import dice.exc
import dicedb
from dicedb.schema import (DUser, Pun, SavedRoll, DEFAULT_INIT)


def dump_db():  # pragma: no cover
    """
    Purely debug function, shunts db contents into file for examination.
    """
    session = dicedb.Session()
    fname = os.path.join(tempfile.gettempdir(), 'dbdump_' + os.environ.get('COG_TOKEN', 'dev'))
    print("Dumping db contents to:", fname)
    with open(fname, 'w') as fout:
        for cls in [DUser, Pun, SavedRoll]:
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
    new_duser = DUser(id=member.id, display_name=member.display_name,
                      character=member.display_name)
    session.add(new_duser)
    session.commit()

    return new_duser


def update_duser_character(session, member, new_character):
    """
    Update a users turn order character.
    """
    duser = get_duser(session, member.id)
    duser.character = new_character
    session.add(duser)
    session.commit()


def update_duser_init(session, member, new_init):
    """
    Update a users turn order initiative.
    """
    duser = get_duser(session, member.id)
    duser.init = new_init
    session.add(duser)
    session.commit()


def generate_inital_turn_users(session):
    """
    Find all potential turn order users.
    """
    dusers = session.query(DUser).filter(DUser.init != DEFAULT_INIT).all()
    return ['{}/{}'.format(duser.character, duser.init) for duser in dusers]


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


def add_pun(session, new_pun):
    """
    Add a pun to the pun database.
    """
    session.add(Pun(text=new_pun))
    session.commit()


def all_puns(session):
    """
    Get a complete list of puns.
    """
    return session.query(Pun).all()


def remove_pun(session, pun):
    """
    Remove a pun from the database.
    """
    session.delete(pun)
    session.commit()


def randomly_select_pun(session):
    """
    Get a random pun from the database.
    While selection is random, will evenly visit all puns before repeats.

    Raises:
        dice.exc.InvalidCommandArgs - No puns exist to choose.
    """
    try:
        lowest_hits = session.query(func.min(Pun.hits)).scalar()
        pun = numpy.random.choice(session.query(Pun).filter(Pun.hits == lowest_hits).all())

        pun.hits += 1
        session.add(pun)
        session.commit()

        return pun.text
    except (IndexError, ValueError):
        raise dice.exc.InvalidCommandArgs('You must add puns first!')


def check_for_pun_dupe(session, text):
    """
    Returns true if the text already contained in a Pun.
    """
    return session.query(Pun).filter(Pun.text == text).all()
