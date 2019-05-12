"""
Module should handle logic related to querying/manipulating tables from a high level.
"""
from __future__ import absolute_import, print_function
import os
import pathlib
import re
import tempfile

import numpy.random
import sqlalchemy.orm.exc as sqla_oexc
from sqlalchemy import func

import dice.exc
import dicedb
from dicedb.schema import (DUser, Pun, SavedRoll, TurnChar, TurnOrder, Song, SongTag)

DEFAULT_VOLUME = dice.util.get_config('music', 'default_volume', default=20)


def dump_db():  # pragma: no cover
    """
    Purely debug function, shunts db contents into file for examination.
    """
    session = dicedb.Session()
    fname = os.path.join(tempfile.gettempdir(), 'dbdump_' + os.environ.get('COG_TOKEN', 'dev'))
    print("Dumping db contents to:", fname)
    with open(fname, 'w') as fout:
        for cls in [DUser, Pun, SavedRoll, TurnChar, TurnOrder, Song, SongTag]:
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
        duser = get_duser(session, str(member.id))
        duser.display_name = member.display_name
    except dice.exc.NoMatch:
        duser = add_duser(session, member)

    return duser


def add_duser(session, member):
    """
    Add a discord user to the database.
    """
    new_duser = DUser(id=str(member.id), display_name=member.display_name)
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


def update_turn_order(session, key, turnorder):
    """
    Add an existing turn order for a given server/channel combination.
    """
    try:
        stored = session.query(TurnOrder).filter(TurnOrder.id == key).one()
        stored.text = repr(turnorder)
        session.add(stored)
    except sqla_oexc.NoResultFound:
        session.add(TurnOrder(id=key, text=repr(turnorder)))
    session.commit()


def get_turn_order(session, key):
    """
    Fetch an existing turn order for a given server/channel combination.
    """
    try:
        return session.query(TurnOrder).filter(TurnOrder.id == key).one().text
    except sqla_oexc.NoResultFound:
        return None


def rem_turn_order(session, key):
    """
    Remove the turn order from the db.
    """
    try:
        stored = session.query(TurnOrder).filter(TurnOrder.id == key).one()
        session.delete(stored)
        session.commit()
    except sqla_oexc.NoResultFound:
        pass


def get_turn_char(session, user_key, turn_key):
    """
    Fetch the character identified by the combination user_key & turn_key.
    """
    try:
        return session.query(TurnChar).filter(TurnChar.user_key == user_key and
                                              TurnChar.turn_order_key == turn_key).one()
    except sqla_oexc.NoResultFound:
        return None


def update_turn_char(session, user_key, turn_key, *, name=None, init=None):
    """
    Given user and turn ids, set a character and/or init value.
    """
    try:
        char = session.query(TurnChar).filter(TurnChar.user_key == user_key and
                                              TurnChar.turn_key == turn_key).one()
        if name:
            char.name = name
        if init:
            char.init = init

    except sqla_oexc.NoResultFound:
        if not name:
            name = ''
        if not init:
            init = ''
        char = TurnChar(user_key=user_key, turn_key=turn_key, name=name, init=init)

    session.add(char)
    session.commit()


def generate_inital_turn_users(session, turn_key):
    """
    Find all potential turn order users for that turn_key.
    """
    chars = session.query(TurnChar).filter(TurnChar.turn_key == turn_key and
                                           TurnChar.init != '' and TurnChar.name != '').all()
    return ['{}/{}'.format(char.name, char.init) for char in chars]


def add_song_with_tags(session, name, url, tags=None):
    """
    Add a song with many possible tags. If the song exists, delete it and overwrite.
    """
    try:
        existing = session.query(Song).filter(Song.name == name).one()
        remove_song_with_tags(session, existing.name)
    except sqla_oexc.NoResultFound:
        pass

    song = Song(name=name, folder=dice.util.get_config('paths', 'music'),
                url=None, repeat=False, volume_int=DEFAULT_VOLUME)
    if dice.util.is_valid_yt(url):
        song_url = 'https://youtu.be/' + dice.util.is_valid_yt(url)
        song = Song(name=name, folder=dice.util.get_config('paths', 'youtube'),
                    url=song_url, repeat=False, volume_int=DEFAULT_VOLUME)
    session.add(song)
    session.commit()

    song_tags = []
    for tag in tags:
        song_tags += [SongTag(name=tag, song_key=song.id)]
    session.add_all(song_tags)
    session.commit()

    return song


def remove_song_with_tags(session, name):
    """
    Remove a song and any tags.
    """
    song = session.query(Song).filter(Song.name.ilike(name)).one()
    for tag in song.tags:
        session.delete(tag)
    session.delete(song)
    session.commit()


def search_songs_by_name(session, name):
    """
    Get the possible song by name.
    """
    try:
        return [session.query(Song).filter(Song.name == name).one()]
    except sqla_oexc.NoResultFound:
        return session.query(Song).filter(Song.name.ilike('%{}%'.format(name))).all()


def get_song_by_id(session, id):
    """
    Get a song that you want by id.
    """
    return session.query(Song).filter(Song.id == id).one()


def get_songs_with_tag(session, tag_name):
    """
    Get the possible song by name.
    """
    subq = session.query(SongTag.song_key).filter(SongTag.name == tag_name).subquery()
    return session.query(Song).filter(Song.id.in_(subq)).all()


def get_song_choices(session):
    """
    Get all possible choices for song names.

    args:
        session: session to the database.
    """
    return session.query(Song).order_by(Song.name).all()


def get_tag_choices(session, similar_to=None):
    """
    Get all possible choices for tag names and their counts.

    args:
        session: session to the database.
        similar_to: Only return tags similar to this.
    """
    query = session.query(SongTag.name).distinct()
    if similar_to:
        query = query.filter(SongTag.name.ilike('%{}%'.format(similar_to)))

    return [x[0] for x in query.order_by(SongTag.name).all()]


def validate_videos(list_vids, session=None):
    """
    Validate the videos asked to play. Accepted formats:
        - youtube links
        - names of songs in the song db
        - names of files on the local HDD

    Raises:
        InvalidCommandArgs - A video link or name failed validation.
        ValueError - Did not pass a list of videos.
    """
    if not isinstance(list_vids, type([])):
        raise ValueError("Did not pass a list of videos.")

    if not session:
        session = dicedb.Session()

    new_vids = []
    for vid in list_vids:
        match = re.match(r'\s*<\s*(\S+)\s*>\s*', vid)
        if match:
            vid = match.group(1)

        matches = dicedb.query.search_songs_by_name(session, vid)
        if matches and len(matches) == 1:
            new_vids.append(matches[0])

        elif dice.util.is_valid_yt(vid):
            yt_id = dice.util.is_valid_yt(vid)
            new_vids.append(Song(id=None, name='youtube_{}'.format(yt_id), folder='/tmp/videos',
                                 url='https://youtu.be/' + yt_id, repeat=False, volume_int=DEFAULT_VOLUME))

        elif dice.util.is_valid_url(vid):
            raise dice.exc.InvalidCommandArgs("Only youtube links supported: " + vid)

        else:
            pat = pathlib.Path(dice.util.get_config('paths', 'music'))
            globbed = list(pat.glob(vid + "*"))
            if len(globbed) != 1:
                raise dice.exc.InvalidCommandArgs("Cannot find local video: " + vid)

            name = os.path.basename(globbed[0]).replace('.opus', '')
            new_vids.append(Song(id=None, name=name, folder=pat, url=None, repeat=False,
                                 volume_int=DEFAULT_VOLUME))

    return new_vids
