"""
Define the database schema and some helpers.

N.B. Schema defaults only applied once object commited.
"""
from __future__ import absolute_import, print_function
from functools import total_ordering

import sqlalchemy as sqla
import sqlalchemy.orm as sqla_orm
import sqlalchemy.ext.declarative

import dice.exc
import dice.tbl
import dicedb


LEN_DID = 30
LEN_NAME = 100
LEN_PUN = 600
LEN_ROLLSTR = 200
LEN_SONG_NAME = 100
LEN_SONG_URL = 100
LEN_SONG_TAG = 100
LEN_TURN_KEY = 60
LEN_TURN_ORDER = 2500
Base = sqlalchemy.ext.declarative.declarative_base()


@total_ordering
class DUser(Base):
    """
    Table to store discord users and their permanent preferences.
    """
    __tablename__ = 'discord_users'

    id = sqla.Column(sqla.String(LEN_DID), primary_key=True)  # Discord id
    display_name = sqla.Column(sqla.String(LEN_NAME))

    def __repr__(self):
        keys = ['id', 'display_name']
        kwargs = ['{}={!r}'.format(key, getattr(self, key)) for key in keys]

        return "DUser({})".format(', '.join(kwargs))

    def __str__(self):
        return repr(self)

    def __eq__(self, other):
        return isinstance(other, DUser) and self.id == other.id

    def __lt__(self, other):
        return self.id < other.id

    @property
    def mention(self):
        """ Mention this user in a response. """
        return "<@" + self.id + ">"


@total_ordering
class SavedRoll(Base):
    """
    Represents a saved dice roll associated to a name.
    """
    __tablename__ = 'saved_rolls'

    id = sqla.Column(sqla.Integer, primary_key=True)
    name = sqla.Column(sqla.String(LEN_NAME))
    roll_str = sqla.Column(sqla.String(LEN_ROLLSTR))
    user_id = sqla.Column(sqla.String(LEN_DID), sqla.ForeignKey('discord_users.id'), nullable=False)

    def __repr__(self):
        keys = ['id', 'user_id', 'name', 'roll_str']
        kwargs = ['{}={!r}'.format(key, getattr(self, key)) for key in keys]

        return "SavedRoll({})".format(', '.join(kwargs))

    def __str__(self):
        return repr(self)

    def __eq__(self, other):
        return isinstance(other, SavedRoll) and (
            self.user_id, self.name, self.roll_str) == (other.user_id, other.name, other.roll_str)

    def __lt__(self, other):
        return (self.user_id, self.name) < (other.user_id, other.name)


@total_ordering
class Pun(Base):
    """
    Stores a single pun with a hit counter.
    """
    __tablename__ = 'puns'

    id = sqla.Column(sqla.Integer, primary_key=True)
    text = sqla.Column(sqla.String(LEN_PUN))
    hits = sqla.Column(sqla.Integer, default=0)

    def __repr__(self):
        keys = ['id', 'text', 'hits']
        kwargs = ['{}={!r}'.format(key, getattr(self, key)) for key in keys]

        return "Pun({})".format(', '.join(kwargs))

    def __str__(self):
        return repr(self)

    def __eq__(self, other):
        return isinstance(other, Pun) and self.text == other.text

    def __hash__(self):
        return hash(self.text)

    def __lt__(self, other):
        return self.id < other.id


class TurnChar(Base):
    """
    """
    __tablename__ = 'turn_chars'

    user_key = sqla.Column(sqla.String(LEN_DID), sqla.ForeignKey('discord_users.id'),
                           primary_key=True)
    turn_key = sqla.Column(sqla.String(LEN_TURN_KEY), primary_key=True)
    name = sqla.Column(sqla.String(100))
    init = sqla.Column(sqla.Integer)

    def __repr__(self):
        keys = ['user_key', 'turn_key', 'name', 'init']
        kwargs = ['{}={!r}'.format(key, getattr(self, key)) for key in keys]

        return "TurnChar({})".format(', '.join(kwargs))

    def __str__(self):
        return '{}/{}'.format(self.name, self.init)

    def __eq__(self, other):
        return isinstance(other, TurnChar) and self.text == other.text


class TurnOrder(Base):
    """
    Store a serialized TurnOrder completely into the database.
    """
    __tablename__ = 'turn_orders'

    id = sqla.Column(sqla.String(LEN_TURN_KEY), primary_key=True)
    text = sqla.Column(sqla.String(LEN_TURN_ORDER), default='')

    def __repr__(self):
        keys = ['id', 'text']
        kwargs = ['{}={!r}'.format(key, getattr(self, key)) for key in keys]

        return "TurnOrder({})".format(', '.join(kwargs))

    def __str__(self):
        return repr(self)

    def __eq__(self, other):
        return isinstance(other, TurnOrder) and self.id == other.id


class Song(Base):
    """
    A song to play for users of the bot.
    """
    __tablename__ = 'songs'

    id = sqla.Column(sqla.Integer, primary_key=True)
    url = sqla.Column(sqla.String(LEN_SONG_URL), nullable=False)
    name = sqla.Column(sqla.String(LEN_SONG_NAME), nullable=False, unique=True)

    def __repr__(self):
        keys = ['id', 'name', 'url', 'tags']
        kwargs = ['{}={!r}'.format(key, getattr(self, key)) for key in keys]

        return "Song({})".format(', '.join(kwargs))

    def __str__(self):
        return repr(self)

    def __eq__(self, other):
        return isinstance(other, Song) and self.id == other.id

    @property
    def is_youtube(self):
        dice.util.IS_YT.match(self.url)


class SongTag(Base):
    """
    A tag for a song.
    """
    __tablename__ = 'song_tags'

    id = sqla.Column(sqla.Integer, primary_key=True)
    song_key = sqla.Column(sqla.Integer, sqla.ForeignKey('songs.id'))
    name = sqla.Column(sqla.String(LEN_SONG_TAG), nullable=False)

    def __repr__(self):
        keys = ['id', 'name', 'song_key']
        kwargs = ['{}={!r}'.format(key, getattr(self, key)) for key in keys]

        return "SongTag({})".format(', '.join(kwargs))

    def __str__(self):
        return repr(self)

    def __eq__(self, other):
        return isinstance(other, SongTag) and self.id == other.id


def parse_int(word):
    """ Parse into int, on failure return 0 """
    try:
        return int(word)
    except ValueError:
        return 0


def parse_float(word):
    """ Parse into float, on failure return 0.0 """
    try:
        return float(word)
    except ValueError:
        return 0.0


def empty_tables(session):
    """
    Drop all tables.
    """
    for cls in DB_CLASSES:
        for matched in session.query(cls):
            session.delete(matched)
    session.commit()


def recreate_tables(engine=dicedb.engine):
    """
    Recreate all tables in the database, mainly for schema changes and testing.
    """
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


# Relationships
DUser.rolls = sqla_orm.relationship('SavedRoll',
                                    cascade='all, delete, delete-orphan',
                                    back_populates='user',
                                    lazy='select')
SavedRoll.user = sqla_orm.relationship('DUser', uselist=False, back_populates='rolls',
                                       lazy='select')

Song.tags = sqla_orm.relationship('SongTag', back_populates='song', lazy='select')
SongTag.song = sqla_orm.relationship('Song', back_populates='tags', lazy='select')


if dicedb.TEST_DB:
    recreate_tables()
else:
    Base.metadata.create_all(dicedb.engine)


def main():  # pragma: no cover
    """
    This continues to exist only as a sanity test for schema and relations.
    """
    print('Schema Main: Forcing DB to use \'test\'')
    creds = dice.util.get_config('dbs', 'main')
    creds['db'] = 'test_dice'
    engine = sqla.create_engine(dicedb.MYSQL_SPEC.format(**creds), echo=False, pool_recycle=3600)
    session = sqla_orm.sessionmaker(bind=engine)()

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    dusers = (
        DUser(id='1234', display_name='User1'),
        DUser(id='2345', display_name='User2'),
        DUser(id='3456', display_name='User3'),
    )
    session.add_all(dusers)
    session.commit()

    rolls = (
        SavedRoll(name='Bow', roll_str='d20 + 7, d8', user_id=dusers[0].id),
        SavedRoll(name='Staff', roll_str='d20 + 2, d6', user_id=dusers[0].id),
        SavedRoll(name='LongSword', roll_str='d20 + 7, d8+4', user_id=dusers[1].id),
    )
    session.add_all(rolls)
    session.commit()

    puns = (
        Pun(text='First pun.'),
        Pun(text='Another pun here.'),
        Pun(text='The last pun that is here.'),
    )
    session.add_all(puns)
    session.commit()

    turns = (
        TurnOrder(id='server1-chan1', text="TurnOrder"),
    )
    session.add_all(turns)
    session.commit()

    turns = (
        TurnChar(user_key=dusers[0].id, turn_key=turns[0].id, name='user', init=7),
    )
    session.add_all(turns)
    session.commit()

    songs = (
        Song(name='song1', url='/music/song1'),
        Song(name='song2', url='/music/song2'),
        Song(name='song3', url='youtube.com/song3'),
    )
    session.add_all(songs)
    session.commit()

    song_tags = (
        SongTag(song_key=songs[0].id, tag='quiet'),
        SongTag(song_key=songs[0].id, tag='classical'),
        SongTag(song_key=songs[0].id, tag='violin'),
        SongTag(song_key=songs[1].id, tag='dramatic'),
        SongTag(song_key=songs[1].id, tag='battle'),
        SongTag(song_key=songs[2].id, tag='looking'),
        SongTag(song_key=songs[2].id, tag='creepy'),
    )
    session.add_all(song_tags)
    session.commit()

    def mprint(*args):
        """ Padded print. """
        args = [str(x) for x in args]
        print(*args)

    pad = ' ' * 3

    print('DiscordUsers----------')
    for obj in session.query(DUser):
        mprint(obj)
        mprint(pad, obj.rolls)

    print('SavedRolls----------')
    for obj in session.query(SavedRoll):
        mprint(obj)
        mprint(pad, obj.user)

    print('Puns----------')
    for obj in session.query(Pun):
        mprint(obj)
    session.close()

    print('TurnOrders----------')
    for obj in session.query(TurnOrder):
        mprint(obj)
    session.close()

    print('TurnChars----------')
    for obj in session.query(TurnChar):
        mprint(obj)
    session.close()

    print('Songs----------')
    for obj in session.query(Song):
        mprint(obj)
    session.close()

    print('SongTags----------')
    for obj in session.query(SongTag):
        mprint(obj)
    session.close()
    Base.metadata.drop_all(engine)


DB_CLASSES = [TurnChar, TurnOrder, Pun, SavedRoll, DUser]

if __name__ == "__main__":  # pragma: no cover
    main()
