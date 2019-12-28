"""
Define the database schema and some helpers.

N.B. Schema defaults only applied once object commited.
"""
from __future__ import absolute_import, print_function
from functools import total_ordering
import os
import subprocess
import shlex
import time

import discord
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
LEN_SONG_NAME = 60
LEN_SONG_URL = 36
LEN_SONG_TAG = 60
LEN_TURN_KEY = 60
LEN_MOVIE = 200
LEN_TURN_ORDER = 2500
Base = sqlalchemy.ext.declarative.declarative_base()


@total_ordering
class DUser(Base):
    """
    Table to store discord users and their permanent preferences.

    N.B. discord.py treats id as integer interally, continue storing as string
         due to integer length
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
    modifier = sqla.Column(sqla.Integer)

    def __repr__(self):
        keys = ['user_key', 'turn_key', 'name', 'modifier']
        kwargs = ['{}={!r}'.format(key, getattr(self, key)) for key in keys]

        return "TurnChar({})".format(', '.join(kwargs))

    def __str__(self):
        return '{}/{}'.format(self.name, self.modifier)

    def __eq__(self, other):
        return isinstance(other, TurnChar) and (self.user_key, self.turn_key) == (other.user_key, other.turn_key)


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


@total_ordering
class Song(Base):
    """
    Song object that represents a local or remote video from youtube.
    The contents of this class serialize to the db.
    For local videos, url is None. Otherwise a youtube url.
    """
    __tablename__ = 'songs'

    id = sqla.Column(sqla.Integer, primary_key=True)
    name = sqla.Column(sqla.String(LEN_SONG_NAME), unique=True, nullable=False)
    folder = sqla.Column(sqla.String(LEN_SONG_NAME), nullable=False)
    url = sqla.Column(sqla.String(LEN_SONG_URL), nullable=True)
    repeat = sqla.Column(sqla.Boolean, default=False)
    volume_int = sqla.Column(sqla.Integer, default=50)

    def __str__(self):
        url = ''
        if self.url:
            url = "    __<" + self.url + ">__"

        return "**{}**{}\n        Volume: {}/100 Repeat: {}".format(
            self.name, url, self.volume_int, self.repeat)

    def __repr__(self):
        keys = ['id', 'name', 'folder', 'url', 'repeat', 'volume_int']
        kwargs = ['{}={!r}'.format(key, getattr(self, key)) for key in keys]

        return "Song({})".format(', '.join(kwargs))

    def __hash__(self):
        return hash("{}_{}_{}".format(self.folder, self.name, self.url))

    def __eq__(self, other):
        return isinstance(other, Song) and self.name == other.name

    def __lt__(self, other):
        return self.name < other.name

    @property
    def fname(self):
        """ The filename of the Song. """
        return os.path.join(self.folder, self.name + '.opus')

    @property
    def ready(self):
        """ The filename exists and is ready to play. """
        return os.path.exists(self.fname)

    def format_menu(self, cnt):
        """ Format a song for presentation in a menu with a number to select. """
        tags = ', '.join([x.name for x in self.tags])
        url = ''
        if self.url:
            url = "     __<" + self.url + ">__"

        return """     **{cnt}**)  __{name}__
            URL:{url}
            Tags: {tags}

""".format(cnt=cnt, name=self.name, url=url, tags=tags)

    @property
    def volume(self):
        return float(self.volume_int) / 100

    @volume.setter
    def volume(self, new_volume):
        try:
            new_volume = int(new_volume)
            if new_volume < 0 or new_volume > 100:
                raise ValueError

            self.volume_int = new_volume
        except (TypeError, ValueError):
            raise dice.exc.InvalidCommandArgs("Volume must be between [0, 100]")

    def update(self, other):
        """ Update values based on other object. """
        assert isinstance(other, self.__class__)

        self.id == other.id
        self.name = other.name
        self.folder = other.folder
        self.url = other.url
        self.repeat = other.repeat
        self.volume_int = other.volume_int

    def stream(self):
        """
        Create a compatible AudioStream to use with the discord.py player.

        If a video is local, the local files timestamp is updated and a simple stream is made.
        If the video is remote, stream it via a subprocess and pipe it into the player.

        Returns:
            discord.AudioStream object wrapped in PCMVolumeTransformer to control volume.
        """
        pcmd = None
        if self.url:
            args = shlex.split("youtube-dl -f bestaudio {} -o -".format(self.url))
            pcmd = subprocess.Popen(args, stdout=subprocess.PIPE)

            stream = discord.FFmpegPCMAudio(pcmd.stdout, pipe=True)
        else:
            now = time.time()
            os.utime(self.fname, (now, now))

            stream = discord.FFmpegPCMAudio(self.fname)

        trans = discord.PCMVolumeTransformer(stream, self.volume)
        trans.pcmd = pcmd
        return trans


@total_ordering
class SongTag(Base):
    """
    A tag for a song. Each song can have n tags.
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

    def __lt__(self, other):
        return self.name < other.name


class Googly(Base):
    """
    Track googly eyes ???
    """
    __tablename__ = 'googly'

    id = sqla.Column(sqla.String(LEN_DID), primary_key=True)  # Discord id
    total = sqla.Column(sqla.Integer, default=0)
    used = sqla.Column(sqla.Integer, default=0)

    def __repr__(self):
        keys = ['id', 'total', 'used']
        kwargs = ['{}={!r}'.format(key, getattr(self, key)) for key in keys]

        return "Googly({})".format(', '.join(kwargs))

    def __str__(self):
        return """__**Googly Counter**__

    Total: {}
    Used: {}""".format(self.total, self.used)

    def __eq__(self, other):
        return (self.total, self.used) == (other.total, other.used)

    def __add__(self, num):
        new_total = max(self.total + num, 0)
        new_used = self.used
        if num < 0:
            new_used = self.used + min(self.total, -num)

        return Googly(id=self.id, total=new_total, used=new_used)

    def __sub__(self, num):
        return self + -num

    def __radd__(self, num):
        return self + num

    def __iadd__(self, num):
        if num < 0:
            self.used = self.used + min(self.total, -num)

        self.total = max(self.total + num, 0)
        return self

    def __isub__(self, num):
        self += -num
        return self


@total_ordering
class LastRoll(Base):
    """
    Roll history, keep the last N rolls a user makes.
    """
    __tablename__ = 'last_rolls'

    id = sqla.Column(sqla.String(LEN_DID), primary_key=True)
    id_num = sqla.Column(sqla.Integer, primary_key=True)
    roll_str = sqla.Column(sqla.String(LEN_ROLLSTR), nullable=False)

    def __repr__(self):
        keys = ['id', 'id_num', 'roll_str']
        kwargs = ['{}={!r}'.format(key, getattr(self, key)) for key in keys]

        return "LastRoll({})".format(', '.join(kwargs))

    def __str__(self):
        return repr(self)

    def __eq__(self, other):
        return isinstance(other, self.__class__) and self.roll_str == other.roll_str

    def __lt__(self, other):
        return isinstance(other, self.__class__) and \
            (self.id, self.id_num) < (other.id, other.id_num)


@total_ordering
class Movie(Base):
    """
    A movie someone might want to see.
    """
    __tablename__ = 'movies'

    id = sqla.Column(sqla.String(LEN_DID), primary_key=True)
    id_num = sqla.Column(sqla.Integer, primary_key=True)
    name = sqla.Column(sqla.String(LEN_ROLLSTR))

    def __repr__(self):
        keys = ['id', 'id_num', 'name']
        kwargs = ['{}={!r}'.format(key, getattr(self, key)) for key in keys]

        return "Movie({})".format(', '.join(kwargs))

    def __str__(self):
        return repr(self)

    def __eq__(self, other):
        return isinstance(other, self.__class__) and self.name == other.name

    def __lt__(self, other):
        return isinstance(other, self.__class__) and \
            (self.id, self.name) < (other.id, other.name)


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

Song.tags = sqla_orm.relationship('SongTag', back_populates='song', lazy='select', order_by=SongTag.name)
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
        TurnChar(user_key=dusers[0].id, turn_key=turns[0].id, name='user', modifier=7),
    )
    session.add_all(turns)
    session.commit()

    songs = (
        Song(name='song1', url='/music/song1', folder='/'),
        Song(name='song2', url='/music/song2', folder='/'),
        Song(name='song3', url='youtube.com/song3', folder='/'),
    )
    session.add_all(songs)
    session.commit()

    song_tags = (
        SongTag(song_key=songs[0].id, name='quiet'),
        SongTag(song_key=songs[0].id, name='classical'),
        SongTag(song_key=songs[0].id, name='violin'),
        SongTag(song_key=songs[1].id, name='dramatic'),
        SongTag(song_key=songs[1].id, name='battle'),
        SongTag(song_key=songs[2].id, name='looking'),
        SongTag(song_key=songs[2].id, name='creepy'),
    )
    session.add_all(song_tags)
    session.commit()

    movies = (
        Movie(id=dusers[1].id, id_num=1, name='Matrix'),
        Movie(id=dusers[2].id, id_num=1, name='Pokemon'),
        Movie(id=dusers[2].id, id_num=2, name='Final Space (TV)'),
    )
    session.add_all(movies)
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

    print('Movies----------')
    for obj in session.query(Movie):
        mprint(obj)
    session.close()

    Base.metadata.drop_all(engine)


DB_CLASSES = [SongTag, Song, TurnChar, TurnOrder, Pun, SavedRoll, DUser, Googly, LastRoll]

if __name__ == "__main__":  # pragma: no cover
    main()
